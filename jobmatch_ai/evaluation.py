from __future__ import annotations

import logging
from typing import List, Dict, Optional

from .llm import LLMConfig, complete
from .prompts import evaluation_prompt

logger = logging.getLogger(__name__)


def generate_evaluation(cfg: LLMConfig, transcript: List[Dict[str, str]]) -> str:
    prompt = evaluation_prompt(transcript)
    messages = [
        {"role": "system", "content": "You create concise, actionable interview evaluations."},
        {"role": "user", "content": prompt},
    ]
    return complete(cfg, messages, temperature=0.2)


def generate_comprehensive_evaluation(
    cfg: LLMConfig,
    transcript: List[Dict[str, str]],
    tech_stack: Optional[List[str]] = None,
) -> str:
    """
    按多个维度逐一分析候选人表现，生成综合评估报告。

    Args:
        cfg:        LLM 配置
        transcript: 完整面试对话记录
        tech_stack: 候选人技术栈（用于推断岗位 role，进而做 RAG 检索）
    """
    aspects = {
        "technical_knowledge": "Technical Knowledge & Accuracy",
        "communication": "Communication & Clarity",
        "problem_solving": "Problem-Solving Approach",
        "code_quality": "Code Quality & Best Practices",
        "overall_competence": "Overall Competence & Fit",
    }

    # 推断岗位 role
    from .interview_flow import _detect_role
    role = _detect_role(tech_stack or [])

    scores: Dict[str, int] = {}
    feedback: Dict[str, str] = {}
    all_retrieved: list[dict] = []

    for aspect_key, aspect_name in aspects.items():
        score, aspect_feedback, retrieved = analyze_aspect(
            cfg, transcript, aspect_key, aspect_name, role=role
        )
        scores[aspect_key] = score
        feedback[aspect_key] = aspect_feedback
        all_retrieved.extend(retrieved)

    # 加权总分
    weights = {
        "technical_knowledge": 0.35,
        "communication": 0.20,
        "problem_solving": 0.25,
        "code_quality": 0.10,
        "overall_competence": 0.10,
    }
    overall_score = sum(scores[a] * weights[a] for a in scores)

    report = f"""# Comprehensive Interview Evaluation

## Overall Score: {overall_score:.1f}/100

### Component Scores:
"""
    for aspect_key, aspect_name in aspects.items():
        report += f"- **{aspect_name}**: {scores[aspect_key]}/100\n"

    report += "\n### Detailed Feedback:\n\n"
    for aspect_key, aspect_name in aspects.items():
        report += f"#### {aspect_name}\n{feedback[aspect_key]}\n\n"

    strengths = extract_strengths(cfg, transcript, scores)
    weaknesses = extract_weaknesses(cfg, transcript, scores)
    recommendations = generate_recommendations(cfg, transcript, scores)

    report += f"### Key Strengths:\n{strengths}\n\n"
    report += f"### Areas for Improvement:\n{weaknesses}\n\n"
    report += f"### Recommendations:\n{recommendations}\n"

    # --- RAG 透明度附录 ---
    if all_retrieved:
        unique_retrieved = _dedupe_retrieved(all_retrieved)[:3]
        report += "\n---\n### Retrieved Knowledge (for transparency)\n\n"
        report += (
            "_以下是本次评估中检索到的最相关题库条目与岗位知识，用于辅助 LLM 给出更贴近标准答案的评分：_\n\n"
        )
        for idx, item in enumerate(unique_retrieved, 1):
            chunk_type = item.get("chunk_type", "")
            role_label = item.get("role", "")
            score_val = item.get("score", 0)
            if chunk_type == "question":
                q = item.get("question", "")[:120]
                a = item.get("answer_key_points", "")[:200]
                report += (
                    f"**[{idx}]** `{role_label} | question`  score={score_val:.3f}\n\n"
                    f"- 题目：{q}\n"
                    f"- 答案要点：{a}\n\n"
                )
            else:
                title = item.get("title", item.get("topic", ""))
                body = item.get("answer_key_points", "")[:300]
                report += (
                    f"**[{idx}]** `{role_label} | knowledge`  score={score_val:.3f}\n\n"
                    f"- 主题：{title}\n"
                    f"- 摘要：{body}\n\n"
                )

    return report


def _dedupe_retrieved(items: list[dict]) -> list[dict]:
    """按 document 内容去重，保留分数最高的。"""
    seen: dict[str, dict] = {}
    for item in items:
        key = item.get("id", item.get("document", ""))[:80]
        if key not in seen or item.get("score", 0) > seen[key].get("score", 0):
            seen[key] = item
    return sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)


def analyze_aspect(
    cfg: LLMConfig,
    transcript: List[Dict[str, str]],
    aspect_key: str,
    aspect_name: str,
    role: str = "frontend",
) -> tuple[int, str, list[dict]]:
    """
    评估面试对话的某一维度。

    对 technical_knowledge 维度会先做 RAG 检索，
    把标准答案要点 / 岗位评分规则注入 prompt，使评分更客观准确。

    Returns:
        (score: int, feedback: str, retrieved_chunks: list[dict])
    """
    aspect_prompts = {
        "technical_knowledge": (
            "Evaluate the candidate's technical knowledge and accuracy in their answers. "
            "Consider correctness of technical concepts, depth of understanding, and accuracy of explanations. "
            "Score from 0-100 and provide specific feedback."
        ),
        "communication": (
            "Evaluate the candidate's communication skills and clarity of expression. "
            "Consider how well they articulate ideas, use appropriate terminology, and explain complex concepts. "
            "Score from 0-100 and provide specific feedback."
        ),
        "problem_solving": (
            "Evaluate the candidate's problem-solving approach and analytical thinking. "
            "Consider how they break down problems, think step-by-step, and demonstrate logical reasoning. "
            "Score from 0-100 and provide specific feedback."
        ),
        "code_quality": (
            "Evaluate the quality of any code provided by the candidate. "
            "Consider code structure, best practices, efficiency, and readability. "
            "If no code was provided, evaluate based on coding concepts discussed. "
            "Score from 0-100 and provide specific feedback."
        ),
        "overall_competence": (
            "Evaluate the candidate's overall competence and job fit. "
            "Consider their experience level, confidence, and ability to handle the role's requirements. "
            "Score from 0-100 and provide specific feedback."
        ),
    }

    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    retrieved_chunks: list[dict] = []
    reference_block = ""

    # 仅对 technical_knowledge 维度做 RAG 增强
    if aspect_key == "technical_knowledge":
        try:
            from jobmatch_ai import retriever  # 延迟导入

            # 把候选人的回答片段拼成 query
            candidate_answers = [
                m["content"]
                for m in transcript
                if m.get("role") == "user" and m.get("content", "").strip()
            ]
            query = " ".join(candidate_answers)[:600]

            if query.strip():
                # 检索相关题目 + 岗位知识
                results = retriever.search(
                    query=query,
                    k=5,
                    filter={"role": role},
                )
                retrieved_chunks = results[:3]

                if retrieved_chunks:
                    ref_lines = ["REFERENCE KNOWLEDGE (from question bank and role guidelines):"]
                    for i, item in enumerate(retrieved_chunks, 1):
                        chunk_type = item.get("chunk_type", "")
                        if chunk_type == "question":
                            q = item.get("question", "")[:100]
                            a = item.get("answer_key_points", "")[:250]
                            ref_lines.append(
                                f"[{i}] Question: {q}\n    Answer key points: {a}"
                            )
                        else:
                            title = item.get("title", item.get("topic", ""))
                            body = item.get("answer_key_points", "")[:300]
                            ref_lines.append(f"[{i}] Knowledge ({title}): {body}")
                    reference_block = "\n".join(ref_lines)
                    logger.debug(
                        f"RAG: injected {len(retrieved_chunks)} chunks for technical_knowledge"
                    )

        except RuntimeError as exc:
            logger.warning(f"RAG unavailable for evaluation: {exc}")
        except Exception as exc:
            logger.warning(f"RAG search failed during evaluation: {exc}")

    prompt = f"""
You are evaluating a candidate's interview performance for the aspect: {aspect_name}.

{aspect_prompts[aspect_key]}
"""

    if reference_block:
        prompt += f"""
{reference_block}

Use the above reference knowledge to ground your evaluation against industry-standard answer criteria.
"""

    prompt += f"""
Transcript:
{transcript_text}

Provide your response in this format:
SCORE: [number from 0-100]
FEEDBACK: [detailed feedback paragraph]
"""

    messages = [
        {
            "role": "system",
            "content": f"You are an expert interviewer evaluating {aspect_name.lower()}.",
        },
        {"role": "user", "content": prompt},
    ]

    response = complete(cfg, messages, temperature=0.3)

    lines = response.strip().split("\n")
    score = 50
    feedback = "Unable to analyze this aspect."

    for line in lines:
        if line.startswith("SCORE:"):
            try:
                score = int(float(line.split(":", 1)[1].strip()))
                score = max(0, min(100, score))
            except Exception:
                pass
        elif line.startswith("FEEDBACK:"):
            feedback = line.split(":", 1)[1].strip()

    return score, feedback, retrieved_chunks


def extract_strengths(
    cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]
) -> str:
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    prompt = f"""
Based on the component scores and transcript, identify the candidate's key strengths.
Focus on the highest-scoring areas and specific positive examples from the interview.

Component Scores: {scores}

Transcript:
{transcript_text}

List 3-5 key strengths as bullet points.
"""
    messages = [
        {
            "role": "system",
            "content": "You identify candidate strengths from interview evaluations.",
        },
        {"role": "user", "content": prompt},
    ]
    return complete(cfg, messages, temperature=0.2)


def extract_weaknesses(
    cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]
) -> str:
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    prompt = f"""
Based on the component scores and transcript, identify areas where the candidate needs improvement.
Focus on the lowest-scoring areas and specific examples from the interview.

Component Scores: {scores}

Transcript:
{transcript_text}

List 3-5 key weaknesses as bullet points with actionable improvement suggestions.
"""
    messages = [
        {
            "role": "system",
            "content": "You identify candidate weaknesses from interview evaluations.",
        },
        {"role": "user", "content": prompt},
    ]
    return complete(cfg, messages, temperature=0.2)


def generate_recommendations(
    cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]
) -> str:
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    prompt = f"""
Based on the component scores and transcript, provide specific recommendations for the candidate's development.

Component Scores: {scores}

Transcript:
{transcript_text}

Provide 3-5 actionable recommendations as bullet points, focusing on the areas that need most improvement.
"""
    messages = [
        {
            "role": "system",
            "content": "You provide career development recommendations based on interview performance.",
        },
        {"role": "user", "content": prompt},
    ]
    return complete(cfg, messages, temperature=0.2)
