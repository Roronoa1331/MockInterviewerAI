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
<div>
    <button id="recordBtn">Start Recording</button>
    <button id="stopBtn" disabled>Stop</button>
    <button id="insertBtn">Insert into reply</button>
    <div id="status" style="margin-top:8px;color:#444"></div>
    <textarea id="transcript" rows="4" style="width:100%; margin-top:8px;"></textarea>
    <script>
    const recordBtn = document.getElementById('recordBtn');
    const stopBtn = document.getElementById('stopBtn');
    const insertBtn = document.getElementById('insertBtn');
    const status = document.getElementById('status');
    const transcriptEl = document.getElementById('transcript');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        status.innerText = 'SpeechRecognition not supported in this browser. Use Chrome.';
    } else {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.interimResults = true;
        recognition.continuous = true;
        recognition.lang = 'en-US';

        recognition.onstart = () => { status.innerText = 'Listening...'; recordBtn.disabled = true; stopBtn.disabled = false; }
        recognition.onend = () => { status.innerText = 'Stopped.'; recordBtn.disabled = false; stopBtn.disabled = true; }
        let finalTranscript = '';
        recognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }
            transcriptEl.value = finalTranscript + interim;
        };
        recordBtn.onclick = () => { finalTranscript = ''; transcriptEl.value=''; recognition.start(); }
        stopBtn.onclick = () => { recognition.stop(); }
        insertBtn.onclick = () => {
            const text = transcriptEl.value;
            // find Streamlit input by label text
            const labels = Array.from(document.querySelectorAll('label'));
            let targetInput = null;
            for (const lbl of labels) {
                if (lbl.innerText && lbl.innerText.trim().startsWith('Your reply')) {
                    const forId = lbl.getAttribute('for');
                    if (forId) {
                        const el = document.getElementById(forId);
                        if (el) { targetInput = el; break; }
                    }
                    let sibling = lbl.nextElementSibling;
                    if (sibling && (sibling.tagName === 'INPUT' || sibling.tagName === 'TEXTAREA')) { targetInput = sibling; break; }
                }
            }
            if (!targetInput) {
                targetInput = document.querySelector('input[type=text], textarea');
            }
            if (targetInput) {
                targetInput.value = text;
                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
                status.innerText = 'Inserted transcript into input.';
            } else {
                status.innerText = 'Could not find the reply input. Please copy-paste manually.';
            }
        };
    }
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
