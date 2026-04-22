import os
import urllib.parse
from typing import List, Dict
from datetime import date, timedelta
import hashlib
import random
import re

import streamlit as st
import altair as alt
import plotly.graph_objects as go

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv() -> bool:  # type: ignore
        return False

from jobmatch_ai.llm import LLMConfig, complete
from jobmatch_ai.prompts import build_system_prompt
from jobmatch_ai.resume_parser import analyze_resume
from jobmatch_ai.interview_flow import InterviewState, build_chat
from jobmatch_ai.evaluation import generate_comprehensive_evaluation, generate_evaluation
from jobmatch_ai.sandbox import run_code_snippet
from jobmatch_ai.question_bank import QuestionBank, extract_tech_stack
from jobmatch_ai.translator import get_translator, translate_text
from jobmatch_ai import db

load_dotenv()
st.set_page_config(page_title="JobMatch AI", layout="wide")

# Translation dictionary
TRANSLATIONS = {
    "en": {
        "title": "JobMatch AI – Mock Interviewer",
        "subtitle": "Persona-driven interviewer with resume grounding and evaluation report.",
        "upload_resume": "1) Upload Resume",
        "upload_file": "Upload PDF or TXT",
        "resume_processed": "Resume processed.",
        "tech_stack": "Tech stack summary:",
        "detected_projects": "Detected projects:",
        "no_projects": "No explicit projects found; questions may start broader.",
        "interview_loop": "2) Interview Loop",
        "start_interview": "Start / Reset interview",
        "next_question": "Interviewer: next question",
        "your_reply": "Your reply (candidate)",
        "submit_reply": "Submit reply",
        "reply_empty": "Reply cannot be empty.",
        "start_first": "Start the interview first.",
        "interview_initialized": "Interview initialized. Click 'Interviewer: next question' to begin.",
        "upload_first": "Upload a resume first.",
        "transcript": "### Transcript",
        "evaluation": "3) Evaluation",
        "generate_report": "Generate evaluation report",
        "scoring": "Scoring interview...",
        "model_backend": "Model Backend",
        "backend": "Backend",
        "model_name": "Model name",
        "openai_key": "OPENAI_API_KEY",
        "deepseek_key": "DEEPSEEK_API_KEY",
        "deepseek_url": "DeepSeek base URL",
        "gemini_key": "GEMINI_API_KEY",
        "gemini_url": "Gemini base URL",
        "gemini_model_hint": "Gemini shorthand names are normalized to gemini-2.5-flash. The default is recommended.",
        "ollama_url": "Ollama base URL",
        "persona": "Interviewer persona",
        "persona_hint": "Keep persona concise. System prompt will include resume summary and projects.",
        "coding_sandbox": "Coding Sandbox",
        "sandbox_hint": "Paste a short Python snippet to run in a constrained sandbox. Avoid network or file access.",
        "code_to_execute": "Code to execute",
        "run_code": "Run code",
        "stdout": "Stdout:",
        "empty": "<empty>",
        "success_no_error": "Executed without runtime errors.",
        "interviewer": "Interviewer",
        "you": "You",
        "voice_input": "Voice input (beta)",
        "eval_radar_title": "Five-Dimension Evaluation",
        "radar_overall_score": "Overall Score",
        "aspect_technical_correctness": "Technical Correctness",
        "aspect_knowledge_depth": "Knowledge Depth",
        "aspect_logical_rigor": "Logical Rigor",
        "aspect_position_match": "Position Match",
        "aspect_expression_clarity": "Expression Clarity",
        "voice_hint": "Click Record, speak your reply, then click Insert into reply. Chrome recommended.",
        "detected_tech_title": "📚 Detected Tech Stack & Questions",
        "detected_technologies": "Detected Technologies:",
        "questions_loaded": "Questions Loaded:",
        "more_questions": "... and {count} more questions",
    },
    "zh": {
        "title": "JobMatch AI – 模拟面试官",
        "subtitle": "基于人物的面试官，具有简历基础和评估报告。",
        "upload_resume": "1) 上传简历",
        "upload_file": "上传 PDF 或 TXT",
        "resume_processed": "简历已处理。",
        "tech_stack": "技术栈摘要：",
        "detected_projects": "检测到的项目：",
        "no_projects": "未找到明确的项目；问题可能从更广的范围开始。",
        "interview_loop": "2) 面试循环",
        "start_interview": "开始/重置面试",
        "next_question": "面试官：下一个问题",
        "your_reply": "你的回复（候选人）",
        "submit_reply": "提交回复",
        "reply_empty": "回复不能为空。",
        "start_first": "请先开始面试。",
        "interview_initialized": "面试已初始化。点击'面试官：下一个问题'开始。",
        "upload_first": "请先上传简历。",
        "transcript": "### 对话记录",
        "evaluation": "3) 评估",
        "generate_report": "生成评估报告",
        "scoring": "正在评分面试...",
        "model_backend": "模型后端",
        "backend": "后端",
        "model_name": "模型名称",
        "openai_key": "OPENAI_API_KEY",
        "deepseek_key": "DEEPSEEK_API_KEY",
        "deepseek_url": "DeepSeek 基础 URL",
        "gemini_key": "GEMINI_API_KEY",
        "gemini_url": "Gemini 基础 URL",
        "gemini_model_hint": "Gemini 简写模型会自动归一化到 gemini-2.5-flash，默认值为推荐选项。",
        "ollama_url": "Ollama 基础 URL",
        "persona": "面试官人物设定",
        "persona_hint": "保持人物设定简洁。系统提示将包括简历摘要和项目。",
        "coding_sandbox": "代码沙箱",
        "sandbox_hint": "粘贴一个简短的 Python 代码片段以在受限沙箱中运行。避免网络或文件访问。",
        "code_to_execute": "要执行的代码",
        "run_code": "运行代码",
        "stdout": "标准输出：",
        "empty": "<空>",
        "success_no_error": "执行完毕，无运行时错误。",
        "interviewer": "面试官",
        "you": "你",
        "voice_input": "语音输入（测试版）",
        "eval_radar_title": "五维度能力评估",
        "radar_overall_score": "综合得分",
        "aspect_technical_correctness": "技术正确性",
        "aspect_knowledge_depth": "知识深度",
        "aspect_logical_rigor": "逻辑严谨性",
        "aspect_position_match": "岗位匹配度",
        "aspect_expression_clarity": "表达清晰度",
        "voice_hint": "点击录音，说出你的回复，然后点击插入到回复中。推荐使用 Chrome。",
        "detected_tech_title": "📚 检测到的技术栈和问题",
        "detected_technologies": "检测到的技术：",
        "questions_loaded": "已加载问题：",
        "more_questions": "... 还有 {count} 个问题",
    }
}

def get_text(key: str) -> str:
    """Get translated text based on current language."""
    lang = st.session_state.get("language", "en")
    return TRANSLATIONS.get(lang, {}).get(key, key)


def init_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []  # list of chat messages
    if "transcript" not in st.session_state:
        st.session_state.transcript = []  # same as history, preserved for evaluation
    if "system_prompt" not in st.session_state:
        st.session_state.system_prompt = None
    if "interview_state" not in st.session_state:
        st.session_state.interview_state = InterviewState()
    if "stack_summary" not in st.session_state:
        st.session_state.stack_summary = ""
    if "projects" not in st.session_state:
        st.session_state.projects = []
    if "resume_text" not in st.session_state:
        st.session_state.resume_text = ""
    if "candidate_name" not in st.session_state:
        st.session_state.candidate_name = "Candidate"
    if "evaluation" not in st.session_state:
        st.session_state.evaluation = None
    if "evaluation_scores" not in st.session_state:
        st.session_state.evaluation_scores = None
    if "evaluation_translations" not in st.session_state:
        st.session_state.evaluation_translations = None
    if "language" not in st.session_state:
        st.session_state.language = "zh"
    if "question_bank" not in st.session_state:
        st.session_state.question_bank = QuestionBank()
    if "tech_stack" not in st.session_state:
        st.session_state.tech_stack = []
    if "interview_questions" not in st.session_state:
        st.session_state.interview_questions = []
    if "original_questions" not in st.session_state:
        st.session_state.original_questions = []
    if "auth" not in st.session_state:
        st.session_state.auth = {"user": None, "access_token": None}
    if "active_interview_id" not in st.session_state:
        st.session_state.active_interview_id = None
    if "page" not in st.session_state:
        st.session_state.page = "app"  # "app" | "auth" | "stats"
    if "score_saved_for_interview" not in st.session_state:
        st.session_state.score_saved_for_interview = {}  # interview_id -> bool
    if "last_retrieval" not in st.session_state:
        # {"query": str, "results": list[dict], "source": str}
        st.session_state.last_retrieval = None


def top_nav() -> None:
    access_token = st.session_state.auth.get("access_token")
    user = st.session_state.auth.get("user")
    right = st.columns([6, 1, 1, 1])
    with right[2]:
        if st.button("📊", key="nav_stats", help="Statistics"):
            st.session_state.page = "stats"
            st.rerun()
    with right[3]:
        if access_token:
            if st.button("Sign out", key="nav_signout"):
                st.session_state.auth = {"user": None, "access_token": None}
                st.session_state.active_interview_id = None
                st.session_state.page = "app"
                st.rerun()
        else:
            if st.button("Log in / Sign up", key="nav_auth"):
                st.session_state.page = "auth"
                st.rerun()

    if access_token:
        email = getattr(user, "email", "") or ""
        st.caption(f"Signed in: {email}")
    else:
        st.info("Guest mode — log in to save data and view statistics.")


def auth_page() -> None:
    st.subheader("Account")
    access_token = st.session_state.auth.get("access_token")
    if access_token:
        st.success("You are already signed in.")
        if st.button("Back to app", key="auth_back_signed_in"):
            st.session_state.page = "app"
            st.rerun()
        return

    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        cols = st.columns([1, 1, 3])
        with cols[0]:
            if st.button("Log in", key="login_btn"):
                try:
                    res = db.sign_in(email=email.strip(), password=password)
                    sess = res["session"]
                    st.session_state.auth = {
                        "user": res["user"],
                        "access_token": sess.access_token if sess else None,
                    }
                    st.session_state.page = "app"
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")
        with cols[1]:
            if st.button("Back", key="auth_back_login"):
                st.session_state.page = "app"
                st.rerun()

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")
        cols = st.columns([1, 1, 3])
        with cols[0]:
            if st.button("Sign up", key="signup_btn"):
                try:
                    res = db.sign_up(email=email.strip(), password=password)
                    sess = res["session"]
                    st.session_state.auth = {
                        "user": res["user"],
                        "access_token": sess.access_token if sess else None,
                    }
                    st.info("Signup complete. Check your email if confirmation is enabled.")
                    st.session_state.page = "app"
                    st.rerun()
                except Exception as e:
                    st.error(f"Signup failed: {e}")
        with cols[1]:
            if st.button("Back", key="auth_back_signup"):
                st.session_state.page = "app"
                st.rerun()


def sidebar_config() -> LLMConfig:
    st.sidebar.header(get_text("model_backend"))
    backend = st.sidebar.selectbox(get_text("backend"), ["openai", "deepseek", "gemini", "ollama"], index=2)
    if backend == "openai":
        default_model = "gpt-4o-mini"
    elif backend == "deepseek":
        default_model = "deepseek-chat"
    elif backend == "gemini":
        default_model = "gemini-2.5-flash"
    else:
        default_model = "llama3"

    model = st.sidebar.text_input(get_text("model_name"), value=default_model)
    if backend == "gemini":
        st.sidebar.caption(get_text("gemini_model_hint"))
    base_url = None
    api_key = None
    if backend == "openai":
        api_key = st.sidebar.text_input(
            get_text("openai_key"),
            value="",  # do not prefill from env to avoid accidental display
            placeholder="Enter your OpenAI key",
            type="password",
        )
    elif backend == "deepseek":
        api_key = st.sidebar.text_input(
            get_text("deepseek_key"),
            value="",  # do not prefill from env
            placeholder="Enter your DeepSeek key",
            type="password",
        )
        base_url = st.sidebar.text_input(
            get_text("deepseek_url"),
            value=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    elif backend == "gemini":
        api_key = st.sidebar.text_input(
            get_text("gemini_key"),
            value="",  # do not prefill from env
            placeholder="Enter your Google AI Studio key",
            type="password",
        )
        base_url = st.sidebar.text_input(
            get_text("gemini_url"),
            value=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        )
    else:
        base_url = st.sidebar.text_input(
            get_text("ollama_url"),
            value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    persona = st.sidebar.text_area(get_text("persona"), value=os.getenv("SYSTEM_PERSONA", ""), height=120)
    st.sidebar.caption(get_text("persona_hint"))
    
    # Debug mode toggle
    st.sidebar.header("Debug")
    debug_mode = st.sidebar.checkbox("Show interview directives", value=False)
    st.session_state.debug_mode = debug_mode
    
    return LLMConfig(backend=backend, model=model, base_url=base_url, api_key=api_key), persona


def resume_section() -> None:
    st.subheader(get_text("upload_resume"))
    uploaded = st.file_uploader(get_text("upload_file"), type=["pdf", "txt"])
    if uploaded:
        file_bytes = uploaded.read()
        text, stack_summary, projects, candidate_name = analyze_resume(file_bytes, uploaded.name)
        st.session_state.resume_text = text
        st.session_state.stack_summary = stack_summary
        st.session_state.projects = projects
        st.session_state.candidate_name = candidate_name
        st.success(get_text("resume_processed"))
        
        # Translate stack summary and projects if in Chinese mode
        display_stack_summary = translate_text(stack_summary, st.session_state.language)
        display_projects = [translate_text(p, st.session_state.language) for p in projects]
        
        st.write(f"**{get_text('tech_stack')}**", display_stack_summary)
        if display_projects:
            st.write(f"**{get_text('detected_projects')}**")
            for p in display_projects:
                st.write(f"- {p}")
        else:
            st.info(get_text("no_projects"))


def start_interview(cfg: LLMConfig, persona: str) -> None:
    if not st.session_state.stack_summary:
        st.warning(get_text("upload_first"))
        return
    
    # Extract tech stack
    tech_stack = extract_tech_stack(
        st.session_state.resume_text,
        st.session_state.stack_summary,
        st.session_state.projects
    )
    st.session_state.tech_stack = tech_stack
    
    # Load questions from question banks
    raw_questions = st.session_state.question_bank.get_questions_for_stack(tech_stack, num_questions=10)
    if not raw_questions:
        raw_questions = st.session_state.question_bank.get_random_questions(num_questions=10)
    st.session_state.original_questions = raw_questions
    if st.session_state.language == "en":
        translator = get_translator()
        questions = translator.translate_questions(raw_questions, target_language="en")
    else:
        questions = raw_questions

    st.session_state.interview_questions = questions
    
    st.session_state.history = []
    st.session_state.transcript = []
    st.session_state.last_retrieval = None
    st.session_state.evaluation = None
    st.session_state.evaluation_scores = None
    interview_state = InterviewState(
        tech_stack=tech_stack,
        available_questions=questions,
        language=st.session_state.language,
    )

    # 注入检索回调，让 InterviewState 能把检索结果写入 session_state
    def _retrieval_callback(query: str, results: list, source: str) -> None:
        st.session_state.last_retrieval = {
            "query": query,
            "results": results,
            "source": source,
        }

    interview_state._last_retrieval_callback = _retrieval_callback
    st.session_state.interview_state = interview_state
    st.session_state.system_prompt = build_system_prompt(
        persona=persona,
        stack_summary=st.session_state.stack_summary,
        resume_projects=st.session_state.projects,
        candidate_name=st.session_state.candidate_name,
        language=st.session_state.language,
    )
    st.session_state.evaluation = None
    st.session_state.active_interview_id = None
    access_token = st.session_state.auth.get("access_token")
    if access_token:
        try:
            st.session_state.active_interview_id = db.create_interview(
                access_token,
                meta={
                    "language": st.session_state.language,
                    "tech_stack": tech_stack,
                    "candidate_name": st.session_state.candidate_name,
                },
            )
        except Exception:
            # If DB isn't configured, the interview can still run locally in session state.
            st.session_state.active_interview_id = None
    st.success(get_text("interview_initialized"))


def interviewer_turn(cfg: LLMConfig) -> None:
    directive = st.session_state.interview_state.next_directive()
    
    # Debug: Show current directive (can be removed later)
    if st.session_state.get('debug_mode', False):
        st.info(f"Current directive: {directive}")
    
    messages = build_chat(st.session_state.system_prompt, st.session_state.history)
    messages.append({"role": "user", "content": directive})
    reply = complete(cfg, messages)
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.session_state.transcript.append({"role": "assistant", "content": reply})
    st.session_state.interview_state.register_interviewer_question(reply)
    access_token = st.session_state.auth.get("access_token")
    interview_id = st.session_state.active_interview_id
    if access_token and interview_id:
        try:
            db.add_message(access_token, interview_id, role="assistant", content=reply)
        except Exception:
            pass

    # Auto-save a score when the interview concludes.
    if (
        directive.strip().lower().startswith("politely conclude the interview")
        and access_token
        and interview_id
        and not st.session_state.score_saved_for_interview.get(interview_id)
    ):
        try:
            quick_eval = generate_evaluation(cfg, st.session_state.transcript)
            score = _extract_overall_score(quick_eval or "")
            if score is not None:
                db.set_interview_score(access_token, interview_id, score)
                st.session_state.score_saved_for_interview[interview_id] = True
        except Exception:
            # Don't block UX if scoring fails; user can still generate report manually.
            pass


def candidate_reply(user_text: str) -> None:
    st.session_state.history.append({"role": "user", "content": user_text})
    st.session_state.transcript.append({"role": "user", "content": user_text})
    st.session_state.interview_state.register_candidate_reply(user_text)
    access_token = st.session_state.auth.get("access_token")
    interview_id = st.session_state.active_interview_id
    if access_token and interview_id:
        try:
            db.add_message(access_token, interview_id, role="user", content=user_text)
        except Exception:
            pass


def _extract_overall_score(md: str) -> int | None:
    # Handles e.g. "## Overall Score: 83.1/100" or "Overall Score: 83/100"
    m = re.search(r"Overall\s+Score\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*100", md, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"\bScore\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*100\b", md, flags=re.IGNORECASE)
    if not m:
        # Handles "Score: 78" / "SCORE: 78"
        m = re.search(r"^\s*Score\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", md, flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        # Handles "## Overall Score: 83.1" (without /100)
        m = re.search(r"Overall\s+Score\s*:\s*([0-9]+(?:\.[0-9]+)?)\b", md, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        val = float(m.group(1))
    except ValueError:
        return None
    val = max(0.0, min(100.0, val))
    return int(round(val))


_ASPECT_ORDER = [
    "technical_correctness",
    "knowledge_depth",
    "logical_rigor",
    "position_match",
    "expression_clarity",
]


def _render_aspect_radar(scores: dict) -> None:
    if not scores:
        return

    theta = [get_text(f"aspect_{key}") for key in _ASPECT_ORDER]
    r = [float(scores.get(key, 0)) for key in _ASPECT_ORDER]
    theta_closed = theta + [theta[0]]
    r_closed = r + [r[0]]

    fig = go.Figure(
        go.Scatterpolar(
            r=r_closed,
            theta=theta_closed,
            fill="toself",
            name=get_text("radar_overall_score"),
            line=dict(color="#22D3EE", width=2),
            fillcolor="rgba(34, 211, 238, 0.35)",
            hovertemplate="%{theta}: %{r:.1f}/100<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(text=get_text("eval_radar_title"), x=0.5, xanchor="center"),
        polar=dict(
            bgcolor="rgba(10, 30, 63, 0.25)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=10),
                gridcolor="rgba(59, 130, 246, 0.35)",
            ),
            angularaxis=dict(
                tickfont=dict(size=13),
                gridcolor="rgba(59, 130, 246, 0.35)",
            ),
        ),
        showlegend=False,
        height=460,
        margin=dict(l=40, r=40, t=60, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _get_display_evaluation(report_md: str) -> str:
    """Return evaluation markdown in the currently selected UI language.

    The source report is preserved in session state, and translated output is
    cached per report digest to avoid repeated translation requests.
    """
    if not report_md:
        return ""

    lang = st.session_state.get("language", "en")
    digest = hashlib.md5(report_md.encode("utf-8")).hexdigest()
    cache = st.session_state.get("evaluation_translations")

    if not isinstance(cache, dict) or cache.get("digest") != digest:
        cache = {"digest": digest, "values": {}}
        st.session_state.evaluation_translations = cache

    values = cache.setdefault("values", {})
    if lang in values:
        return values[lang]

    translated = translate_text(report_md, lang)
    values[lang] = translated if translated else report_md
    return values[lang]


def evaluation_section(cfg: LLMConfig) -> None:
    if st.button(get_text("generate_report")):
        with st.spinner(get_text("scoring")):
            try:
                report_md, scores = generate_comprehensive_evaluation(
                    cfg,
                    st.session_state.transcript,
                    tech_stack=st.session_state.get("tech_stack", []),
                    return_scores=True,
                )
                st.session_state.evaluation = report_md
                st.session_state.evaluation_scores = scores
                st.session_state.evaluation_translations = None
                score = _extract_overall_score(report_md or "")
                access_token = st.session_state.auth.get("access_token")
                interview_id = st.session_state.active_interview_id
                if score is not None and access_token and interview_id:
                    try:
                        db.set_interview_score(access_token, interview_id, score)
                    except Exception:
                        pass
            except RuntimeError as exc:
                st.session_state.evaluation = None
                st.session_state.evaluation_scores = None
                st.session_state.evaluation_translations = None
                st.error(str(exc))
            except Exception as exc:
                st.session_state.evaluation = None
                st.session_state.evaluation_scores = None
                st.session_state.evaluation_translations = None
                st.error(f"Evaluation failed: {exc}")
    if st.session_state.evaluation:
        _render_aspect_radar(st.session_state.get("evaluation_scores") or {})
        st.markdown(_get_display_evaluation(st.session_state.evaluation))


def sandbox_section() -> None:
    st.subheader(get_text("coding_sandbox"))
    st.caption(get_text("sandbox_hint"))
    code = st.text_area(get_text("code_to_execute"), height=180)
    if st.button(get_text("run_code")):
        result = run_code_snippet(code)
        st.write(f"**{get_text('stdout')}**")
        st.code(result.stdout or get_text("empty"))
        if result.error:
            st.error(result.error)
        else:
            st.success(get_text("success_no_error"))

def _format_int(n: int) -> str:
    return f"{n:,}"


def _demo_daily_counts(days: int, intensity: float, seed: int) -> List[Dict]:
    rng = random.Random(seed)
    today = date.today()
    data: List[Dict] = []
    base = max(2.0, intensity * 22.0)
    for i in range(days):
        d = today - timedelta(days=(days - 1 - i))
        # Weekly seasonality + noise
        weekly = 0.65 + 0.35 * (1.0 if d.weekday() in (1, 2, 3) else 0.6)
        noise = rng.uniform(0.55, 1.45)
        count = int(round(base * weekly * noise))
        # occasional "no usage" days
        if rng.random() < (0.08 if intensity > 0.35 else 0.14):
            count = 0
        data.append({"day": d.isoformat(), "count": count})
    return data


def stats_section() -> None:
    access_token = st.session_state.auth.get("access_token")
    if not access_token:
        st.info("Guest mode: this is a demo preview. Log in to see your real saved statistics.")

        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
            with c1:
                days = st.selectbox("Time range", [7, 14, 30, 60, 90], index=2, key="demo_days")
            with c2:
                intensity = st.slider("Activity level", min_value=0.2, max_value=1.0, value=0.55, step=0.05, key="demo_intensity")
            with c3:
                seed = st.number_input("Demo user id", min_value=1, max_value=9999, value=42, step=1, key="demo_seed")
            with c4:
                show_points = st.toggle("Show points", value=True, key="demo_points")

        daily = _demo_daily_counts(days=int(days), intensity=float(intensity), seed=int(seed))
        total_messages = sum(int(r.get("count", 0) or 0) for r in daily)
        active_days = len([r for r in daily if int(r.get("count", 0) or 0) > 0])
        avg_per_day = int(round(total_messages / active_days)) if active_days else 0

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Total saved messages (demo)", _format_int(total_messages))
        with k2:
            st.metric("Active days (demo)", _format_int(active_days))
        with k3:
            st.metric("Avg / active day (demo)", _format_int(avg_per_day))

        st.markdown("#### Activity over time (demo)")
        chart = (
            alt.Chart(alt.Data(values=daily))
            .mark_line(point=show_points)
            .encode(
                x=alt.X("day:T", title="Day"),
                y=alt.Y("count:Q", title="Messages saved"),
                tooltip=["day:T", "count:Q"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)

        st.markdown("#### Score over time (demo)")
        # Demo score series: loosely correlated with activity level
        demo_scores = []
        base_score = 55 + int(intensity * 35)
        rng = random.Random(int(seed) + 999)
        for r in daily:
            if int(r["count"]) == 0:
                continue
            drift = rng.uniform(-5, 6)
            base_score = max(40, min(95, base_score + (0.3 if intensity > 0.5 else 0.15) + drift * 0.08))
            demo_scores.append({"day": r["day"], "score": round(base_score, 1)})

        if demo_scores:
            first = float(demo_scores[0]["score"])
            last = float(demo_scores[-1]["score"])
            delta = round(last - first, 1)
            st.metric("Overall improvement (demo)", f"{delta:+.1f}", help="Last score minus first score in the selected range.")
            score_chart = (
                alt.Chart(alt.Data(values=demo_scores))
                .mark_line(point=True)
                .encode(
                    x=alt.X("day:T", title="Day"),
                    y=alt.Y("score:Q", title="Overall score (0–100)", scale=alt.Scale(domain=[0, 100])),
                    tooltip=["day:T", "score:Q"],
                )
                .properties(height=240)
            )
            st.altair_chart(score_chart, use_container_width=True)
        return

    with st.expander("Demo (logged-in)", expanded=False):
        st.caption("This will create demo interviews + improving scores in your cloud account for testing charts.")
        c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
        with c1:
            demo_days = st.selectbox("Range (days)", [30, 45, 60, 90], index=1, key="seed_days")
        with c2:
            demo_interviews = st.selectbox("Interviews", [5, 8, 10, 15], index=2, key="seed_interviews")
        with c3:
            start_score = st.slider("Start score", 30, 90, 55, 1, key="seed_start")
        with c4:
            end_score = st.slider("End score", 30, 100, 84, 1, key="seed_end")
        seed_val = st.number_input("Seed", min_value=1, max_value=9999, value=42, step=1, key="seed_val")
        if st.button("Generate demo history in my account", key="seed_btn"):
            try:
                db.seed_demo_history(
                    access_token,
                    days=int(demo_days),
                    interviews=int(demo_interviews),
                    start_score=int(start_score),
                    end_score=int(end_score),
                    seed=int(seed_val),
                )
                st.success("Demo history created. Refreshing charts…")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to seed demo data: {e}")
    try:
        daily = db.stats_daily_counts(access_token)
    except Exception as e:
        st.warning(f"Stats unavailable: {e}")
        return
    if not daily:
        st.info("No saved data yet. Start an interview while logged in.")
        return

    total_messages = sum(int(r.get("count", 0) or 0) for r in daily)
    active_days = len([r for r in daily if int(r.get("count", 0) or 0) > 0])
    avg_per_day = int(round(total_messages / active_days)) if active_days else 0

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Total saved messages", _format_int(total_messages))
    with k2:
        st.metric("Active days", _format_int(active_days))
    with k3:
        st.metric("Avg / active day", _format_int(avg_per_day))

    st.markdown("#### Activity over time")
    chart = (
        alt.Chart(alt.Data(values=daily))
        .mark_line(point=True)
        .encode(
            x=alt.X("day:T", title="Day"),
            y=alt.Y("count:Q", title="Messages saved"),
            tooltip=["day:T", "count:Q"],
        )
        .properties(height=240)
    )
    st.altair_chart(chart, use_container_width=True)

    st.markdown("#### Score over time")
    try:
        scores = db.list_scores(access_token)
    except Exception:
        scores = []

    if not scores:
        st.info("No scores saved yet. Finish an interview (auto-saves score at conclusion) or generate an evaluation report.")
        return

    # Convert to day-level average in Python (keeps DB simple)
    by_day: Dict[str, List[float]] = {}
    for r in scores:
        created_at = str(r.get("created_at", ""))[:10]
        s = r.get("score", None)
        if s is None:
            continue
        by_day.setdefault(created_at, []).append(float(s))
    score_daily = [{"day": d, "avg_score": round(sum(v) / len(v), 1), "n": len(v)} for d, v in sorted(by_day.items())]

    first = float(score_daily[0]["avg_score"])
    last = float(score_daily[-1]["avg_score"])
    delta = round(last - first, 1)
    st.metric("Overall improvement", f"{delta:+.1f}", help="Last daily average score minus first daily average score.")

    score_chart = (
        alt.Chart(alt.Data(values=score_daily))
        .mark_line(point=True)
        .encode(
            x=alt.X("day:T", title="Day"),
            y=alt.Y("avg_score:Q", title="Avg overall score (0–100)", scale=alt.Scale(domain=[0, 100])),
            tooltip=["day:T", "avg_score:Q", "n:Q"],
        )
        .properties(height=240)
    )
    st.altair_chart(score_chart, use_container_width=True)

def main() -> None:
    init_state()
    cfg, persona = sidebar_config()

    # Language toggle button in top right
    col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 0.5])
    with col5:
        if st.button("🌐 中/EN"):
            st.session_state.language = "zh" if st.session_state.language == "en" else "en"
            if st.session_state.original_questions:
                translator = get_translator()
                if st.session_state.language == "en":
                    questions = translator.translate_questions(st.session_state.original_questions, target_language="en")
                else:
                    questions = st.session_state.original_questions
                st.session_state.interview_questions = questions
                st.session_state.interview_state.set_questions(questions, language=st.session_state.language)
            if st.session_state.system_prompt:
                st.session_state.system_prompt = build_system_prompt(
                    persona=persona,
                    stack_summary=st.session_state.stack_summary,
                    resume_projects=st.session_state.projects,
                    candidate_name=st.session_state.candidate_name,
                    language=st.session_state.language,
                )
            st.rerun()

    st.title(get_text("title"))
    st.write(get_text("subtitle"))
    top_nav()

    if st.session_state.page == "auth":
        auth_page()
        return
    if st.session_state.page == "stats":
        header_left, header_right = st.columns([6, 1])
        with header_left:
            st.subheader("Statistics")
            st.caption("Your interview activity saved to the cloud.")
        with header_right:
            if st.button("Back", key="stats_back"):
                st.session_state.page = "app"
                st.rerun()

        st.divider()
        stats_section()
        return

    resume_section()

    st.subheader(get_text("interview_loop"))
    cols = st.columns(3)
    with cols[0]:
        if st.button(get_text("start_interview")):
            start_interview(cfg, persona)
    with cols[1]:
        if st.button(get_text("next_question")):
            if not st.session_state.system_prompt:
                st.warning(get_text("start_first"))
            else:
                interviewer_turn(cfg)
    with cols[2]:
        user_input = st.text_input(get_text("your_reply"))
        if st.button(get_text("submit_reply")):
            if not user_input.strip():
                st.warning(get_text("reply_empty"))
            else:
                candidate_reply(user_input.strip())

        # Voice recorder component: records speech and inserts transcript into the reply input
        def voice_recorder_section() -> None:
                if st.toggle(get_text("voice_input")):
                    st.caption(get_text("voice_hint"))
                    speech_lang = "zh-CN" if st.session_state.language == "zh" else "en-US"
                    js = """
<div style="font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<style>
    .vm-card{display:flex;flex-direction:column;align-items:center;gap:8px;padding:12px;border-radius:12px;background:linear-gradient(180deg,#ffffff,#fbfbfb);box-shadow:0 6px 18px rgba(20,20,30,0.06);}
    .rec-btn{width:72px;height:72px;border-radius:50%;border:none;background:#f2f2f2;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:all 160ms ease;box-shadow:0 6px 12px rgba(15,15,20,0.06)}
    .rec-btn.recording{background:linear-gradient(135deg,#ff6b6b,#ff3b3b);transform:scale(1.05);box-shadow:0 8px 20px rgba(255,59,59,0.18);}
    .rec-icon{width:28px;height:28px;fill:#333}
    .rec-btn.recording .rec-icon{fill:#fff}
    .status{font-size:13px;color:#6b7280}
    .transcript{width:100%;border-radius:8px;padding:8px;border:1px solid #e6e6e9;background:transparent;resize:none;color:#111;font-size:13px}
    .controls{display:flex;gap:8px}
    .ctrl{background:transparent;border:1px solid #ddd;border-radius:8px;padding:6px 10px;cursor:pointer;color:#333}
    .ctrl.primary{background:#111;color:#fff;border:none}
    @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,59,59,0.28)}70%{box-shadow:0 0 0 16px rgba(255,59,59,0)}100%{box-shadow:0 0 0 0 rgba(255,59,59,0)}}
    .rec-btn.recording{animation:pulse 1.6s infinite}
</style>
<div class="vm-card">
    <button id="recBtn" class="rec-btn" aria-label="Start/Stop recording">
        <svg class="rec-icon" viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 14 0h-2zM11 19h2v3h-2z"/></svg>
    </button>
    <div id="status" class="status">Tap microphone to speak</div>
    <textarea id="transcript" class="transcript" rows="3" placeholder="Transcript will appear here..."></textarea>
    <div class="controls">
        <button id="copyBtn" class="ctrl primary">Copy</button>
        <button id="clearBtn" class="ctrl">Clear</button>
    </div>
</div>

<script>
    const recBtn = document.getElementById('recBtn');
    const copyBtn = document.getElementById('copyBtn');
    const clearBtn = document.getElementById('clearBtn');
    const status = document.getElementById('status');
    const transcriptEl = document.getElementById('transcript');

    let recognition = null;
    let isRecording = false;
    let finalTranscript = '';

    function supportsSpeech(){ return ('SpeechRecognition' in window) || ('webkitSpeechRecognition' in window); }

    if (!supportsSpeech()){
        status.innerText = 'SpeechRecognition not supported. Use Chrome.';
    } else {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.interimResults = true;
        recognition.continuous = true;
        recognition.lang = '__SPEECH_LANG__';

        recognition.onstart = () => { status.innerText = 'Listening…'; recBtn.classList.add('recording'); }
        recognition.onend = () => { status.innerText = 'Stopped'; recBtn.classList.remove('recording'); isRecording = false; }
        recognition.onerror = (e) => { status.innerText = 'Error: ' + (e.error || 'unknown'); recBtn.classList.remove('recording'); }

        recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }
            transcriptEl.value = (finalTranscript + ' ' + interim).trim();
        };
    }

    recBtn.onclick = () => {
        if (!recognition) return;
        if (!isRecording) {
            finalTranscript = '';
            transcriptEl.value = '';
            try { recognition.start(); isRecording = true; } catch (e) { /* ignore double-start */ }
        } else {
            recognition.stop(); isRecording = false;
        }
    };

    clearBtn.onclick = () => { finalTranscript=''; transcriptEl.value=''; status.innerText='Cleared'; };

    copyBtn.onclick = () => {
        const text = transcriptEl.value.trim();
        if (!text) { status.innerText = 'Nothing to copy.'; return; }
        transcriptEl.select();
        document.execCommand('copy');
        status.innerText = 'Copied to clipboard. Paste into the reply input.';
    };
</script>
</div>
"""

                    js = js.replace('__SPEECH_LANG__', speech_lang)
                    src = "data:text/html;charset=utf-8," + urllib.parse.quote(js)
                    st.components.v1.iframe(src, height=260)

        voice_recorder_section()

    # Display detected tech stack and available questions
    if st.session_state.tech_stack:
        with st.expander(get_text("detected_tech_title")):
            st.write(f"**{get_text('detected_technologies')}** {', '.join(st.session_state.tech_stack)}")
            if st.session_state.interview_questions:
                st.write(f"**{get_text('questions_loaded')}** {len(st.session_state.interview_questions)}")
                for idx, q in enumerate(st.session_state.interview_questions[:5], 1):
                    question = q.get("Question", q.get("题目", ""))
                    if question:
                        st.write(f"{idx}. {translate_text(question, st.session_state.language)}")
                if len(st.session_state.interview_questions) > 5:
                    st.write(get_text('more_questions').format(count=len(st.session_state.interview_questions) - 5))

        # RAG 检索结果可视化
        last_retrieval = st.session_state.get("last_retrieval")
        if last_retrieval and last_retrieval.get("results"):
            with st.expander("🔍 最近一次检索结果 (RAG Debug)", expanded=False):
                st.caption(f"**Query**: `{last_retrieval.get('query', '')}`")
                st.caption(f"**来源**: {last_retrieval.get('source', '')}")
                results = last_retrieval["results"]
                for i, item in enumerate(results[:5], 1):
                    chunk_type = item.get("chunk_type", "")
                    score_val = item.get("score", 0)
                    role_label = item.get("role", "")
                    if chunk_type == "question":
                        q_text = item.get("question", "")
                        a_text = item.get("answer_key_points", "")[:120]
                        st.markdown(
                            f"**[{i}]** `{role_label}` | `{chunk_type}` | score=`{score_val:.3f}`\n\n"
                            f"- 📌 **题目**: {q_text}\n"
                            f"- 💡 **答案要点**: {a_text}…"
                        )
                    else:
                        title = item.get("title", item.get("topic", ""))
                        body = item.get("answer_key_points", "")[:150]
                        st.markdown(
                            f"**[{i}]** `{role_label}` | `{chunk_type}` | score=`{score_val:.3f}`\n\n"
                            f"- 📚 **主题**: {title}\n"
                            f"- 📝 **内容摘要**: {body}…"
                        )
                    st.divider()

    if st.session_state.history:
        st.markdown(get_text("transcript"))
        for msg in st.session_state.history:
            speaker = get_text("interviewer") if msg["role"] == "assistant" else get_text("you")
            st.markdown(f"**{speaker}:** {translate_text(msg['content'], st.session_state.language)}")

    st.subheader(get_text("evaluation"))
    evaluation_section(cfg)

    sandbox_section()


if __name__ == "__main__":
    main()
