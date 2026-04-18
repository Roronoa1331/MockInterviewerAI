from __future__ import annotations

from typing import List, Dict, Optional
import random
from jobmatch_ai.translator import translate_text

INTRO_TARGET = 1
TECH_MIN, TECH_MAX = 3, 5
BEHAVIORAL_MIN = 1


class InterviewState:
    def __init__(self, tech_stack: Optional[List[str]] = None, available_questions: Optional[List[Dict]] = None, language: str = "en") -> None:
        self.stage = "intro"
        self.tech_count = 0
        self.behavior_count = 0
        self.tech_stack = tech_stack or []
        self.available_questions = available_questions or []
        self.used_questions = set()  # Track used question indices
        self.language = language
        self.followups_per_answer = 1
        self.pending_followups = 0
        self.last_question: Optional[str] = None
        self.last_answer: Optional[str] = None

    def _get_lang_str(self) -> str:
        return "simplified Chinese" if self.language == "zh" else "English"

    def register_interviewer_question(self, question_text: str) -> None:
        self.last_question = question_text.strip() if question_text else None

    def register_candidate_reply(self, answer_text: str) -> None:
        self.last_answer = answer_text.strip() if answer_text else None
        if self.last_answer:
            self.pending_followups = max(self.pending_followups, self.followups_per_answer)

    def _get_followup_directive(self) -> str:
        lang_str = self._get_lang_str()
        q = self.last_question or ""
        a = self.last_answer or ""
        self.pending_followups = max(0, self.pending_followups - 1)
        return (
            "Ask exactly ONE targeted follow-up question to dig deeper based on the candidate's last answer.\n"
            "The follow-up should clarify specifics, probe trade-offs, or ask for a concrete example. Do not add a second question.\n"
            "Do NOT move to a new topic yet. Do NOT give an evaluation.\n\n"
            f"Previous question (context): {q}\n"
            f"Candidate answer (context): {a}\n\n"
            f"IMPORTANT: You MUST respond entirely in {lang_str}."
        )

    def next_directive(self) -> str:
        lang_str = self._get_lang_str()
        if self.pending_followups > 0 and self.last_answer:
            return self._get_followup_directive()

        if self.stage == "intro" and self.tech_count == 0:
            self.stage = "technical"
            return f"Begin with a concise introduction and ask the candidate for a self-intro.\nIMPORTANT: You MUST respond entirely in {lang_str}."

        if self.stage == "technical":
            self.tech_count += 1
            if self.tech_count < TECH_MAX:
                return self._get_technical_question()
            self.stage = "behavioral"

        if self.stage == "behavioral":
            self.behavior_count += 1
            if self.behavior_count < BEHAVIORAL_MIN:
                return f"Ask a behavioral question (failure, conflict, ownership).\nIMPORTANT: You MUST respond entirely in {lang_str}."
            self.stage = "conclusion"

        return f"Politely conclude the interview.\nIMPORTANT: You MUST respond entirely in {lang_str}."
    
    def _get_technical_question(self) -> str:
        """Get a technical question from the question bank."""
        lang_str = self._get_lang_str()
        if not self.available_questions:
            return f"Ask a technical question. Prefer resume-grounded for the first 2-3.\nIMPORTANT: You MUST respond entirely in {lang_str}."
        
        # Find an unused question
        for i, q in enumerate(self.available_questions):
            if i not in self.used_questions:
                self.used_questions.add(i)
                question_text = q.get("Question", q.get("题目", ""))
                if question_text:
                    question_text = translate_text(question_text, self.language)
                    return (
                        f"CRITICAL INSTRUCTION: You MUST ask the following exact question. "
                        f"If the question is not already in {lang_str}, you must translate it and ask it in {lang_str}. "
                        f"Only ask this one question and then stop speaking.\n\n"
                        f"Question: {question_text}\n\n"
                        f"IMPORTANT: You MUST respond entirely in {lang_str}."
                    )
        
        return f"Ask a technical question. Prefer resume-grounded for the first 2-3.\nIMPORTANT: You MUST respond entirely in {lang_str}."
    
    def set_questions(self, questions: List[Dict], language: Optional[str] = None) -> None:
        """Set available questions for this interview session."""
        self.available_questions = questions
        self.used_questions = set()
        if language:
            self.language = language


def build_chat(system_prompt: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": "system", "content": system_prompt}, *history]
