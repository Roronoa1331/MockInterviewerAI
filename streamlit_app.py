import os
from typing import List, Dict

import streamlit as st
from dotenv import load_dotenv

from jobmatch_ai.llm import LLMConfig, complete
from jobmatch_ai.prompts import build_system_prompt
from jobmatch_ai.resume_parser import analyze_resume
from jobmatch_ai.interview_flow import InterviewState, build_chat
from jobmatch_ai.evaluation import generate_evaluation
from jobmatch_ai.sandbox import run_code_snippet
import streamlit.components.v1 as components

load_dotenv()
st.set_page_config(page_title="JobMatch AI", layout="wide")


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


def sidebar_config() -> LLMConfig:
    st.sidebar.header("Model Backend")
    backend = st.sidebar.selectbox("Backend", ["transformers", "openai", "deepseek", "gemini", "ollama"], index=0)
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

    model = st.sidebar.text_input("Model name", value=default_model)
    base_url = None
    api_key = None
    if backend == "transformers":
        st.sidebar.info("Using local Hugging Face model. First run will download the model.")
    elif backend == "openai":
        api_key = st.sidebar.text_input(
            "OPENAI_API_KEY",
            value="",  # do not prefill from env to avoid accidental display
            placeholder="Enter your OpenAI key",
            type="password",
        )
    elif backend == "deepseek":
        api_key = st.sidebar.text_input(
            "DEEPSEEK_API_KEY",
            value="",  # do not prefill from env
            placeholder="Enter your DeepSeek key",
            type="password",
        )
        base_url = st.sidebar.text_input(
            "DeepSeek base URL",
            value=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    elif backend == "gemini":
        api_key = st.sidebar.text_input(
            "GEMINI_API_KEY",
            value="",  # do not prefill from env
            placeholder="Enter your Google AI Studio key",
            type="password",
        )
        base_url = st.sidebar.text_input(
            "Gemini base URL",
            value=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        )
    else:
        base_url = st.sidebar.text_input(
            "Ollama base URL",
            value=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )
    persona = st.sidebar.text_area("Interviewer persona", value=os.getenv("SYSTEM_PERSONA", ""), height=120)
    st.sidebar.caption("Keep persona concise. System prompt will include resume summary and projects.")
    return LLMConfig(backend=backend, model=model, base_url=base_url, api_key=api_key), persona


def resume_section() -> None:
    st.subheader("1) Upload Resume")
    uploaded = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    if uploaded:
        file_bytes = uploaded.read()
        text, stack_summary, projects, candidate_name = analyze_resume(file_bytes, uploaded.name)
        st.session_state.resume_text = text
        st.session_state.stack_summary = stack_summary
        st.session_state.projects = projects
        st.session_state.candidate_name = candidate_name
        st.success("Resume processed.")
        st.write("**Tech stack summary:**", stack_summary)
        if projects:
            st.write("**Detected projects:**")
            for p in projects:
                st.write(f"- {p}")
        else:
            st.info("No explicit projects found; questions may start broader.")


def start_interview(cfg: LLMConfig, persona: str) -> None:
    if not st.session_state.stack_summary:
        st.warning("Upload a resume first.")
        return
    st.session_state.history = []
    st.session_state.transcript = []
    st.session_state.interview_state = InterviewState()
    st.session_state.system_prompt = build_system_prompt(
        persona=persona,
        stack_summary=st.session_state.stack_summary,
        resume_projects=st.session_state.projects,
        candidate_name=st.session_state.candidate_name,
    )
    st.session_state.evaluation = None
    st.success("Interview initialized. Click 'Interviewer: next question' to begin.")


def interviewer_turn(cfg: LLMConfig) -> None:
    directive = st.session_state.interview_state.next_directive()
    messages = build_chat(st.session_state.system_prompt, st.session_state.history)
    messages.append({"role": "user", "content": directive})
    reply = complete(cfg, messages)
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.session_state.transcript.append({"role": "assistant", "content": reply})


def candidate_reply(user_text: str) -> None:
    st.session_state.history.append({"role": "user", "content": user_text})
    st.session_state.transcript.append({"role": "user", "content": user_text})


def evaluation_section(cfg: LLMConfig) -> None:
    if st.button("Generate evaluation report"):
        with st.spinner("Scoring interview..."):
            st.session_state.evaluation = generate_evaluation(cfg, st.session_state.transcript)
    if st.session_state.evaluation:
        st.markdown(st.session_state.evaluation)


def sandbox_section() -> None:
    st.subheader("Coding Sandbox ")
    st.caption("Paste a short Python snippet to run in a constrained sandbox. Avoid network or file access.")
    code = st.text_area("Code to execute", height=180)
    if st.button("Run code"):
        result = run_code_snippet(code)
        st.write("**Stdout:**")
        st.code(result.stdout or "<empty>")
        if result.error:
            st.error(result.error)
        else:
            st.success("Executed without runtime errors.")


def main() -> None:
    init_state()
    cfg, persona = sidebar_config()

    st.title("JobMatch AI – Mock Interviewer")
    st.write("Persona-driven interviewer with resume grounding and evaluation report.")

    resume_section()

    st.subheader("2) Interview Loop")
    cols = st.columns(3)
    with cols[0]:
        if st.button("Start / Reset interview"):
            start_interview(cfg, persona)
    with cols[1]:
        if st.button("Interviewer: next question"):
            if not st.session_state.system_prompt:
                st.warning("Start the interview first.")
            else:
                interviewer_turn(cfg)
    with cols[2]:
        user_input = st.text_input("Your reply (candidate)")
        if st.button("Submit reply"):
            if not user_input.strip():
                st.warning("Reply cannot be empty.")
            else:
                candidate_reply(user_input.strip())

        # Voice recorder component: records speech and inserts transcript into the reply input
        def voice_recorder_section() -> None:
                st.subheader("Voice input (beta)")
                st.caption("Click Record, speak your reply, then click Insert into reply. Chrome recommended.")
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
        <button id="insertBtn" class="ctrl primary">Insert</button>
        <button id="clearBtn" class="ctrl">Clear</button>
    </div>
</div>

<script>
    const recBtn = document.getElementById('recBtn');
    const insertBtn = document.getElementById('insertBtn');
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
        recognition.lang = 'en-US';

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

    insertBtn.onclick = () => {
        const text = transcriptEl.value.trim();
        if (!text) { status.innerText = 'Nothing to insert.'; return; }
        const labels = Array.from(document.querySelectorAll('label'));
        let targetInput = null;
        for (const lbl of labels) {
            if (lbl.innerText && lbl.innerText.trim().startsWith('Your reply')) {
                const forId = lbl.getAttribute('for');
                if (forId) { const el = document.getElementById(forId); if (el) { targetInput = el; break; } }
                let sibling = lbl.nextElementSibling;
                if (sibling && (sibling.tagName==='INPUT' || sibling.tagName==='TEXTAREA')) { targetInput = sibling; break; }
            }
        }
        if (!targetInput) { targetInput = document.querySelector('input[type=text], textarea'); }
        if (targetInput) {
            targetInput.value = text;
            targetInput.dispatchEvent(new Event('input', { bubbles: true }));
            status.innerText = 'Inserted transcript.';
        } else {
            status.innerText = 'Reply input not found; copy-paste instead.';
        }
    };
</script>
</div>
"""

                components.html(js, height=260)

        voice_recorder_section()

    if st.session_state.history:
        st.markdown("### Transcript")
        for msg in st.session_state.history:
            speaker = "Interviewer" if msg["role"] == "assistant" else "You"
            st.markdown(f"**{speaker}:** {msg['content']}")

    st.subheader("3) Evaluation")
    evaluation_section(cfg)

    sandbox_section()


if __name__ == "__main__":
    main()
