import os
import urllib.parse
from typing import List, Dict

import streamlit as st
from dotenv import load_dotenv

from jobmatch_ai.llm import LLMConfig, complete
from jobmatch_ai.prompts import build_system_prompt
from jobmatch_ai.resume_parser import analyze_resume
from jobmatch_ai.interview_flow import InterviewState, build_chat
from jobmatch_ai.evaluation import generate_comprehensive_evaluation
from jobmatch_ai.sandbox import run_code_snippet
from jobmatch_ai.question_bank import QuestionBank, extract_tech_stack
from jobmatch_ai.translator import get_translator, translate_text

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
        "using_local": "Using local Hugging Face model. First run will download the model.",
        "openai_key": "OPENAI_API_KEY",
        "deepseek_key": "DEEPSEEK_API_KEY",
        "deepseek_url": "DeepSeek base URL",
        "gemini_key": "GEMINI_API_KEY",
        "gemini_url": "Gemini base URL",
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
        "using_local": "使用本地 Hugging Face 模型。首次运行将从 Hugging Face 下载模型。",
        "openai_key": "OPENAI_API_KEY",
        "deepseek_key": "DEEPSEEK_API_KEY",
        "deepseek_url": "DeepSeek 基础 URL",
        "gemini_key": "GEMINI_API_KEY",
        "gemini_url": "Gemini 基础 URL",
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


def sidebar_config() -> LLMConfig:
    st.sidebar.header(get_text("model_backend"))
    backend = st.sidebar.selectbox(get_text("backend"), ["transformers", "openai", "deepseek", "gemini", "ollama"], index=0)
    if backend == "transformers":
        default_model = "Qwen/Qwen2.5-3B-Instruct"
    elif backend == "openai":
        default_model = "gpt-4o-mini"
    elif backend == "deepseek":
        default_model = "deepseek-chat"
    elif backend == "gemini":
        default_model = "gemini-2.5-flash"
    else:
        default_model = "llama3"

    model = st.sidebar.text_input(get_text("model_name"), value=default_model)
    base_url = None
    api_key = None
    if backend == "transformers":
        st.sidebar.info(get_text("using_local"))
    elif backend == "openai":
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
    st.session_state.interview_state = InterviewState(tech_stack=tech_stack, available_questions=questions, language=st.session_state.language)
    st.session_state.system_prompt = build_system_prompt(
        persona=persona,
        stack_summary=st.session_state.stack_summary,
        resume_projects=st.session_state.projects,
        candidate_name=st.session_state.candidate_name,
        language=st.session_state.language,
    )
    st.session_state.evaluation = None
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


def candidate_reply(user_text: str) -> None:
    st.session_state.history.append({"role": "user", "content": user_text})
    st.session_state.transcript.append({"role": "user", "content": user_text})


def evaluation_section(cfg: LLMConfig) -> None:
    if st.button(get_text("generate_report")):
        with st.spinner(get_text("scoring")):
            st.session_state.evaluation = generate_comprehensive_evaluation(cfg, st.session_state.transcript)
    if st.session_state.evaluation:
        st.markdown(st.session_state.evaluation)


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
                with st.expander(get_text("voice_input"), expanded=False):
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
                st.iframe(src, height=260)

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
