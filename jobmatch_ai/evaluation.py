from __future__ import annotations

import json
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
    return_scores: bool = False,
) -> str | tuple[str, Dict[str, int]]:
    """
    按赛题 5 大维度逐一分析候选人表现，生成综合评估报告。

    维度口径对齐赛题「任务三：面试表现多维度分析」：
      内容分析：technical_correctness / knowledge_depth / logical_rigor / position_match
      表达分析：expression_clarity

    Args:
        cfg:           LLM 配置
        transcript:    完整面试对话记录
        tech_stack:    候选人技术栈（用于推断岗位 role，进而做 RAG 检索）
        return_scores: 是否额外返回 {aspect_key: score} 字典，便于 UI 画雷达图

    Returns:
        return_scores=False -> report_markdown (str)     # 向后兼容
        return_scores=True  -> (report_markdown, scores_dict)
    """
    aspects = {
        "technical_correctness": "Technical Correctness",
        "knowledge_depth": "Knowledge Depth",
        "logical_rigor": "Logical Rigor",
        "position_match": "Position Match",
        "expression_clarity": "Expression Clarity",
    }
    weights = {
        "technical_correctness": 0.25,
        "knowledge_depth": 0.20,
        "logical_rigor": 0.20,
        "position_match": 0.20,
        "expression_clarity": 0.15,
    }

    # 推断岗位 role，并做一次 RAG 检索作为参考上下文
    from .interview_flow import _detect_role

    role = _detect_role(tech_stack or [])
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    candidate_answers = [
        m["content"]
        for m in transcript
        if m.get("role") == "user" and m.get("content", "").strip()
    ]
    query = " ".join(candidate_answers)[:800].strip() or transcript_text[:800]

    retrieved_chunks: list[dict] = []
    reference_block = ""
    if query:
        try:
            from jobmatch_ai import retriever  # delayed import

            results = retriever.search(query=query, k=5, filter={"role": role})
            retrieved_chunks = results[:3]
            if retrieved_chunks:
                ref_lines = ["REFERENCE KNOWLEDGE (from question bank and role guidelines):"]
                for i, item in enumerate(retrieved_chunks, 1):
                    chunk_type = item.get("chunk_type", "")
                    if chunk_type == "question":
                        q = item.get("question", "")[:100]
                        a = item.get("answer_key_points", "")[:250]
                        ref_lines.append(f"[{i}] Question: {q}\n    Answer key points: {a}")
                    else:
                        title = item.get("title", item.get("topic", ""))
                        body = item.get("answer_key_points", "")[:300]
                        ref_lines.append(f"[{i}] Knowledge ({title}): {body}")
                reference_block = "\n".join(ref_lines)
        except RuntimeError as exc:
            logger.warning(f"RAG unavailable for evaluation: {exc}")
        except Exception as exc:
            logger.warning(f"RAG search failed during evaluation: {exc}")

    prompt = f"""
You are evaluating a candidate's interview performance for five dimensions.

Dimensions and meaning:
- technical_correctness: factual correctness of technical claims, APIs, formulas, and code
- knowledge_depth: depth of technical understanding, internals, trade-offs, edge cases
- logical_rigor: consistency, decomposition, and step-by-step reasoning quality
- position_match: match to the target role's required competencies
- expression_clarity: clarity of written expression in the transcript only

Scoring rules:
- Give each dimension an integer score from 0 to 100.
- Be strict about factual mistakes.
- For expression_clarity, assess the transcript text only. Do not judge speech rate or confidence.
- If reference knowledge is provided, use it to ground technical_correctness, knowledge_depth, and position_match.

{reference_block}

Transcript:
{transcript_text}

Return ONLY a JSON object with this exact structure:
{{
  "scores": {{
    "technical_correctness": 0,
    "knowledge_depth": 0,
    "logical_rigor": 0,
    "position_match": 0,
    "expression_clarity": 0
  }},
  "feedback": {{
    "technical_correctness": "...",
    "knowledge_depth": "...",
    "logical_rigor": "...",
    "position_match": "...",
    "expression_clarity": "..."
  }},
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendations": ["...", "..."]
}}
"""

    messages = [
        {
            "role": "system",
            "content": "You are an expert interviewer that returns strict JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    response = complete(cfg, messages, temperature=0.2)
    payload = _extract_json_payload(response)

    scores = _coerce_scores(payload.get("scores", {}), weights)
    feedback = _coerce_feedback(payload.get("feedback", {}), aspects)
    strengths = _coerce_text_list(payload.get("strengths", []), fallback="No strengths provided.")
    weaknesses = _coerce_text_list(payload.get("weaknesses", []), fallback="No weaknesses provided.")
    recommendations = _coerce_text_list(payload.get("recommendations", []), fallback="No recommendations provided.")

    overall_score = sum(scores[a] * weights[a] for a in weights)
    report_lines = [
        "# Comprehensive Interview Evaluation",
        "",
        f"## Overall Score: {overall_score:.1f}/100",
        "",
        "### Component Scores:",
    ]
    for aspect_key, aspect_name in aspects.items():
        report_lines.append(f"- **{aspect_name}**: {scores[aspect_key]}/100")

    report_lines.extend(["", "### Detailed Feedback:", ""])
    for aspect_key, aspect_name in aspects.items():
        report_lines.append(f"#### {aspect_name}")
        report_lines.append(feedback[aspect_key])
        report_lines.append("")

    report_lines.append("### Key Strengths")
    for item in strengths:
        report_lines.append(f"- {item}")
    report_lines.append("")

    report_lines.append("### Areas for Improvement")
    for item in weaknesses:
        report_lines.append(f"- {item}")
    report_lines.append("")

    report_lines.append("### Recommendations")
    for item in recommendations:
        report_lines.append(f"- {item}")

    if retrieved_chunks:
        unique_retrieved = _dedupe_retrieved(retrieved_chunks)[:3]
        report_lines.extend(["", "---", "### Retrieved Knowledge (for transparency)", "", "_以下是本次评估中检索到的最相关题库条目与岗位知识，用于辅助 LLM 给出更贴近标准答案的评分：_", ""])
        for idx, item in enumerate(unique_retrieved, 1):
            chunk_type = item.get("chunk_type", "")
            role_label = item.get("role", "")
            score_val = item.get("score", 0)
            if chunk_type == "question":
                q = item.get("question", "")[:120]
                a = item.get("answer_key_points", "")[:200]
                report_lines.extend([
                    f"**[{idx}]** `{role_label} | question`  score={score_val:.3f}",
                    "",
                    f"- 题目：{q}",
                    f"- 答案要点：{a}",
                    "",
                ])
            else:
                title = item.get("title", item.get("topic", ""))
                body = item.get("answer_key_points", "")[:300]
                report_lines.extend([
                    f"**[{idx}]** `{role_label} | knowledge`  score={score_val:.3f}",
                    "",
                    f"- 主题：{title}",
                    f"- 摘要：{body}",
                    "",
                ])

    report = "\n".join(report_lines).strip() + "\n"
    if return_scores:
        return report, scores
    return report


def _dedupe_retrieved(items: list[dict]) -> list[dict]:
    """按 document 内容去重，保留分数最高的。"""
    seen: dict[str, dict] = {}
    for item in items:
        key = item.get("id", item.get("document", ""))[:80]
        if key not in seen or item.get("score", 0) > seen[key].get("score", 0):
            seen[key] = item
    return sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)


def _extract_json_payload(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("Evaluation model did not return a JSON object.")
    payload_text = text[start : end + 1]
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse evaluation JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Evaluation payload must be a JSON object.")
    return payload


def _coerce_scores(raw_scores: dict, weights: Dict[str, float]) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for key in weights:
        try:
            value = int(round(float(raw_scores.get(key, 50))))
        except Exception:
            value = 50
        scores[key] = max(0, min(100, value))
    return scores


def _coerce_feedback(raw_feedback: dict, aspects: Dict[str, str]) -> Dict[str, str]:
    feedback: Dict[str, str] = {}
    for key in aspects:
        value = raw_feedback.get(key, "")
        feedback[key] = value.strip() if isinstance(value, str) and value.strip() else "No feedback provided."
    return feedback


def _coerce_text_list(raw_value, fallback: str) -> list[str]:
    if isinstance(raw_value, list):
        items = [str(item).strip() for item in raw_value if str(item).strip()]
        return items or [fallback]
    if isinstance(raw_value, str) and raw_value.strip():
        return [line.strip("-• \t") for line in raw_value.splitlines() if line.strip().strip("-• \t")]
    return [fallback]


def analyze_aspect(
    cfg: LLMConfig,
    transcript: List[Dict[str, str]],
    aspect_key: str,
    aspect_name: str,
    role: str = "frontend",
) -> tuple[int, str, list[dict]]:
    """
    评估面试对话的某一维度。

    对技术正确性、知识深度、岗位匹配度维度会先做 RAG 检索，
    把标准答案要点 / 岗位评分规则注入 prompt，使评分更客观准确。

    Returns:
        (score: int, feedback: str, retrieved_chunks: list[dict])
    """
    aspect_prompts = {
        "technical_correctness": (
            "Evaluate the TECHNICAL CORRECTNESS of the candidate's answers. "
            "Focus ONLY on whether the technical claims, concepts, APIs, formulas and code "
            "are factually correct. Penalize factual mistakes heavily. "
            "Score from 0-100 and provide specific feedback with concrete evidence."
        ),
        "knowledge_depth": (
            "Evaluate the DEPTH of the candidate's technical knowledge. "
            "Beyond surface definitions, can they explain internals, trade-offs, edge cases, "
            "and connections between concepts? Shallow textbook answers should score lower. "
            "Score from 0-100 and provide specific feedback."
        ),
        "logical_rigor": (
            "Evaluate the LOGICAL RIGOR of the candidate's reasoning. "
            "Consider problem decomposition, step-by-step derivation, handling of edge cases, "
            "and self-consistency across turns. Vague or hand-wavy reasoning should score lower. "
            "Score from 0-100 and provide specific feedback."
        ),
        "position_match": (
            "Evaluate how well the candidate's skills, experience and answers MATCH the target "
            "role's required competencies. Use the reference knowledge (if present) as the "
            "role's competency bar. Score from 0-100 and provide specific feedback."
        ),
        "expression_clarity": (
            "Evaluate the CLARITY OF EXPRESSION shown in the transcript text. "
            "Judge wording precision, logical connectors, conciseness and whether a non-expert "
            "could follow. (Acoustic features such as speech rate and confidence are out of scope "
            "for text-only evaluation.) Score from 0-100 and provide specific feedback."
        ),
    }

    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    retrieved_chunks: list[dict] = []
    reference_block = ""

    # 仅对强技术/岗位匹配维度做 RAG 增强
    if aspect_key in ("technical_correctness", "knowledge_depth", "position_match"):
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
                    logger.debug(f"RAG: injected {len(retrieved_chunks)} chunks for {aspect_key}")

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
