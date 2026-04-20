from __future__ import annotations

import logging
from typing import List, Dict, Optional
import random
from jobmatch_ai.translator import translate_text

logger = logging.getLogger(__name__)

INTRO_TARGET = 1
TECH_MIN, TECH_MAX = 3, 5
BEHAVIORAL_MIN = 1

# Unity 相关关键词，用于推断岗位 role
_UNITY_KEYWORDS: set[str] = {
    "csharp", "c#", "cpp", "c++", "lua", "unity", "shader", "networking",
    "hlsl", "glsl", "urp", "hdrp", "monobehaviour", "assetbundle",
}


def _detect_role(tech_stack: List[str]) -> str:
    """根据 tech_stack 推断岗位角色（frontend / unity）。"""
    stack_lower = {t.lower().strip() for t in tech_stack}
    if stack_lower & _UNITY_KEYWORDS:
        return "unity"
    return "frontend"


class InterviewState:
    def __init__(
        self,
        tech_stack: Optional[List[str]] = None,
        available_questions: Optional[List[Dict]] = None,
        language: str = "en",
    ) -> None:
        self.stage = "intro"
        self.tech_count = 0
        self.behavior_count = 0
        self.tech_stack = tech_stack or []
        self.available_questions = available_questions or []
        self.used_questions: set = set()  # 已使用的问题索引（fallback 路径）
        self.used_question_texts: set = set()  # 已使用的问题文本（RAG 路径去重）
        self.language = language
        self.followups_per_answer = 1
        self.pending_followups = 0
        self.last_question: Optional[str] = None
        self.last_answer: Optional[str] = None
        # 岗位 role，供检索时过滤
        self.role: str = _detect_role(self.tech_stack)
        # 供 UI 展示的最近一次检索结果写到外部 session_state，这里只暴露 hook
        self._last_retrieval_callback = None

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
            return (
                f"Begin with a concise introduction and ask the candidate for a self-intro.\n"
                f"IMPORTANT: You MUST respond entirely in {lang_str}."
            )

        if self.stage == "technical":
            self.tech_count += 1
            if self.tech_count < TECH_MAX:
                return self._get_technical_question()
            self.stage = "behavioral"

        if self.stage == "behavioral":
            self.behavior_count += 1
            if self.behavior_count < BEHAVIORAL_MIN:
                return (
                    f"Ask a behavioral question (failure, conflict, ownership).\n"
                    f"IMPORTANT: You MUST respond entirely in {lang_str}."
                )
            self.stage = "conclusion"

        return (
            f"Politely conclude the interview.\n"
            f"IMPORTANT: You MUST respond entirely in {lang_str}."
        )

    def _get_technical_question(self) -> str:
        """
        优先通过 RAG 检索一道题目；检索失败时退回 available_questions 随机抽取。
        """
        lang_str = self._get_lang_str()

        # --- RAG 路径 ---
        try:
            from jobmatch_ai import retriever  # 延迟导入，避免循环依赖

            # 用技术栈 + 已出过的题组合为 query
            query_parts = list(self.tech_stack) if self.tech_stack else ["技术面试"]
            query = " ".join(query_parts[:5])

            results = retriever.search(
                query=query,
                k=10,
                filter={"$and": [{"role": self.role}, {"chunk_type": "question"}]},
            )

            # 回调通知 UI（由 streamlit_app 注入）
            if self._last_retrieval_callback and results:
                self._last_retrieval_callback(
                    query=query, results=results, source="interview"
                )

            # 跳过已使用的题目，选 top-1 未用题
            for item in results:
                q_text = item.get("question", "")
                if q_text and q_text not in self.used_question_texts:
                    self.used_question_texts.add(q_text)
                    translated = translate_text(q_text, self.language)
                    logger.debug(f"RAG question retrieved from vector store: {q_text[:60]}")
                    return (
                        "CRITICAL INSTRUCTION: You MUST ask the following exact question. "
                        f"If the question is not already in {lang_str}, translate it to {lang_str}. "
                        "Only ask this one question and then stop speaking.\n\n"
                        f"[retrieved from vector store] Question: {translated}\n\n"
                        f"IMPORTANT: You MUST respond entirely in {lang_str}."
                    )

        except RuntimeError as exc:
            # 向量库尚未构建时静默退回 fallback，并打日志
            logger.warning(f"RAG unavailable, falling back to question bank: {exc}")
        except Exception as exc:
            logger.warning(f"RAG search error, falling back: {exc}")

        # --- Fallback 路径（原 random.sample 逻辑）---
        if not self.available_questions:
            return (
                f"Ask a technical question. Prefer resume-grounded for the first 2-3.\n"
                f"IMPORTANT: You MUST respond entirely in {lang_str}."
            )

        for i, q in enumerate(self.available_questions):
            if i not in self.used_questions:
                self.used_questions.add(i)
                question_text = q.get("Question", q.get("题目", ""))
                if question_text:
                    question_text = translate_text(question_text, self.language)
                    return (
                        "CRITICAL INSTRUCTION: You MUST ask the following exact question. "
                        f"If the question is not already in {lang_str}, you must translate it and ask it in {lang_str}. "
                        "Only ask this one question and then stop speaking.\n\n"
                        f"Question: {question_text}\n\n"
                        f"IMPORTANT: You MUST respond entirely in {lang_str}."
                    )

        return (
            f"Ask a technical question. Prefer resume-grounded for the first 2-3.\n"
            f"IMPORTANT: You MUST respond entirely in {lang_str}."
        )

    def set_questions(self, questions: List[Dict], language: Optional[str] = None) -> None:
        """设置本次面试的候选题目列表（fallback 路径使用）。"""
        self.available_questions = questions
        self.used_questions = set()
        if language:
            self.language = language


def build_chat(
    system_prompt: str, history: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    return [{"role": "system", "content": system_prompt}, *history]
