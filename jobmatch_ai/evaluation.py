from typing import List, Dict

from .llm import LLMConfig, complete
from .prompts import evaluation_prompt


def generate_evaluation(cfg: LLMConfig, transcript: List[Dict[str, str]]) -> str:
    prompt = evaluation_prompt(transcript)
    messages = [
        {"role": "system", "content": "You create concise, actionable interview evaluations."},
        {"role": "user", "content": prompt},
    ]
    return complete(cfg, messages, temperature=0.2)


def generate_comprehensive_evaluation(cfg: LLMConfig, transcript: List[Dict[str, str]]) -> str:
    """
    Generate a comprehensive evaluation by analyzing different aspects of the candidate's performance.
    This method provides a more natural and detailed analysis with component scores.
    """
    aspects = {
        "technical_knowledge": "Technical Knowledge & Accuracy",
        "communication": "Communication & Clarity",
        "problem_solving": "Problem-Solving Approach",
        "code_quality": "Code Quality & Best Practices",
        "overall_competence": "Overall Competence & Fit"
    }

    scores = {}
    feedback = {}

    # Analyze each aspect separately
    for aspect_key, aspect_name in aspects.items():
        score, aspect_feedback = analyze_aspect(cfg, transcript, aspect_key, aspect_name)
        scores[aspect_key] = score
        feedback[aspect_key] = aspect_feedback

    # Calculate weighted overall score
    weights = {
        "technical_knowledge": 0.35,
        "communication": 0.20,
        "problem_solving": 0.25,
        "code_quality": 0.10,
        "overall_competence": 0.10
    }

    overall_score = sum(scores[aspect] * weights[aspect] for aspect in scores)

    # Generate comprehensive report
    report = f"""# Comprehensive Interview Evaluation

## Overall Score: {overall_score:.1f}/100

### Component Scores:
"""

    for aspect_key, aspect_name in aspects.items():
        report += f"- **{aspect_name}**: {scores[aspect_key]}/100\n"

    report += "\n### Detailed Feedback:\n\n"

    for aspect_key, aspect_name in aspects.items():
        report += f"#### {aspect_name}\n"
        report += f"{feedback[aspect_key]}\n\n"

    # Add strengths and weaknesses summary
    strengths = extract_strengths(cfg, transcript, scores)
    weaknesses = extract_weaknesses(cfg, transcript, scores)

    report += f"### Key Strengths:\n{strengths}\n\n"
    report += f"### Areas for Improvement:\n{weaknesses}\n\n"

    # Add recommendations
    recommendations = generate_recommendations(cfg, transcript, scores)
    report += f"### Recommendations:\n{recommendations}\n"

    return report


def analyze_aspect(cfg: LLMConfig, transcript: List[Dict[str, str]], aspect_key: str, aspect_name: str) -> tuple[int, str]:
    """Analyze a specific aspect of the candidate's performance."""
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
        )
    }

    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)

    prompt = f"""
You are evaluating a candidate's interview performance for the aspect: {aspect_name}.

{aspect_prompts[aspect_key]}

Transcript:
{transcript_text}

Provide your response in this format:
SCORE: [number from 0-100]
FEEDBACK: [detailed feedback paragraph]
"""

    messages = [
        {"role": "system", "content": f"You are an expert interviewer evaluating {aspect_name.lower()}."},
        {"role": "user", "content": prompt},
    ]

    response = complete(cfg, messages, temperature=0.3)

    # Parse the response
    lines = response.strip().split('\n')
    score = 50  # default
    feedback = "Unable to analyze this aspect."

    for line in lines:
        if line.startswith('SCORE:'):
            try:
                score = int(line.split(':', 1)[1].strip())
                score = max(0, min(100, score))  # clamp to 0-100
            except:
                pass
        elif line.startswith('FEEDBACK:'):
            feedback = line.split(':', 1)[1].strip()

    return score, feedback


def extract_strengths(cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]) -> str:
    """Extract key strengths from the evaluation."""
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
        {"role": "system", "content": "You identify candidate strengths from interview evaluations."},
        {"role": "user", "content": prompt},
    ]

    return complete(cfg, messages, temperature=0.2)


def extract_weaknesses(cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]) -> str:
    """Extract key weaknesses from the evaluation."""
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
        {"role": "system", "content": "You identify candidate weaknesses from interview evaluations."},
        {"role": "user", "content": prompt},
    ]

    return complete(cfg, messages, temperature=0.2)


def generate_recommendations(cfg: LLMConfig, transcript: List[Dict[str, str]], scores: Dict[str, int]) -> str:
    """Generate recommendations for the candidate."""
    transcript_text = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)

    prompt = f"""
Based on the component scores and transcript, provide specific recommendations for the candidate's development.

Component Scores: {scores}

Transcript:
{transcript_text}

Provide 3-5 actionable recommendations as bullet points, focusing on the areas that need most improvement.
"""

    messages = [
        {"role": "system", "content": "You provide career development recommendations based on interview performance."},
        {"role": "user", "content": prompt},
    ]

    return complete(cfg, messages, temperature=0.2)
