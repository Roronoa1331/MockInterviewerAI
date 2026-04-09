from typing import List

DEFAULT_PERSONA = (
    "You are a senior technical interviewer. Be firm but fair, concise, and structured. "
    "Keep the conversation focused on engineering depth and clarity."
)

INTRO_STEPS = [
    "Introduce yourself as the interviewer and ask for a concise self-introduction.",
    "Set expectations: a short technical and behavioral loop, then feedback.",
]

TECH_GUIDELINES = (
    "Ask 3-5 technical questions. Mix coding logic, system design, and framework depth. "
    "Prefer resume-grounded questions first. Tailor difficulty to the candidate's stack."
)

BEHAVIORAL_GUIDELINES = "Ask 1-2 behavioral questions (failure, conflict, ownership)."

CLOSING = "Close politely and mention that an evaluation will follow."


def build_system_prompt(persona: str | None, stack_summary: str, resume_projects: List[str], candidate_name: str = "Candidate", language: str = "en") -> str:
    persona_text = persona.strip() if persona else DEFAULT_PERSONA
    project_hint = "\n".join(f"- {p}" for p in resume_projects[:3]) or "- No projects found"
    language_instruction = (
        "Respond in simplified Chinese. Use Chinese for all candidate-facing questions and summaries."
        if language == "zh"
        else "Respond in English. Use English for all candidate-facing questions and summaries."
    )
    return (
        f"{persona_text}\n"
        f"You are interviewing {candidate_name}.\n"
        f"Introduce yourself as JobMatchAI, a technical interviewer.\n"
        "Follow a structured interview flow: introduction, technical deep dive, behavioral, conclusion.\n"
        f"Technical guidance: {TECH_GUIDELINES}\n"
        f"Behavioral guidance: {BEHAVIORAL_GUIDELINES}\n"
        f"Closing guidance: {CLOSING}\n"
        "Always remember prior answers to ask relevant follow-ups (maintain memory).\n"
        "Keep replies concise (<=120 words) unless explicitly asked to expand.\n"
        "If you are provided a specific technical question from the question bank, ask that exact question and do not invent another question.\n"
        "Ground the first technical questions in the candidate projects below.\n"
        f"{language_instruction}\n"
        "Candidate stack summary (use to tune depth):\n"
        f"{stack_summary}\n"
        "Candidate projects (prioritize for initial questions):\n"
        f"{project_hint}\n"
        "Respond in markdown-friendly text."
    )


def evaluation_prompt(transcript: List[dict]) -> str:
    # transcript: list of {role, content}
    return (
        "You are grading a mock interview. Create a Markdown report with the following sections:\n"
        "- Score: integer out of 100.\n"
        "- Strengths: bullet list.\n"
        "- Weaknesses: bullet list.\n"
        "- Sample Answers: improved answers for missed/weak questions.\n"
        "Base your judgment only on the transcript below. Be specific and actionable, avoid generic advice.\n"
        "Transcript:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
    )
