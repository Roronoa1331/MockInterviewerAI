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

    def next_directive(self) -> str:
        if self.stage == "intro" and self.tech_count == 0:
            self.stage = "technical"
            return "Begin with a concise introduction and ask the candidate for a self-intro."

        if self.stage == "technical":
            self.tech_count += 1
            if self.tech_count < TECH_MAX:
                return self._get_technical_question()
            self.stage = "behavioral"

        if self.stage == "behavioral":
            self.behavior_count += 1
            if self.behavior_count < BEHAVIORAL_MIN:
                return "Ask a behavioral question (failure, conflict, ownership)."
            self.stage = "conclusion"

        return "Politely conclude the interview."
    
    def _get_technical_question(self) -> str:
        """Get a technical question from the question bank."""
        if not self.available_questions:
            return "Ask a technical question. Prefer resume-grounded for the first 2-3."
        
        # Find an unused question
        for i, q in enumerate(self.available_questions):
            if i not in self.used_questions:
                self.used_questions.add(i)
                question_text = q.get("Question", q.get("题目", ""))
                if question_text:
                    question_text = translate_text(question_text, self.language)
                    return (
                        "CRITICAL INSTRUCTION: You MUST ask the following exact question word-for-word. "
                        "Do NOT modify, rephrase, or invent a different question. "
                        "Do NOT ask follow-up questions in this response. "
                        "Only ask this one question and then stop speaking.\n\n"
                        f"Question: {question_text}"
                    )
        
        return "Ask a technical question. Prefer resume-grounded for the first 2-3."
    
    def set_questions(self, questions: List[Dict]) -> None:
        """Set available questions for this interview session."""
        self.available_questions = questions
        self.used_questions = set()


def build_chat(system_prompt: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [{"role": "system", "content": system_prompt}, *history]
