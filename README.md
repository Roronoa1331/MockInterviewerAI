# JobMatch AI – Mock Interviewer Agent

JobMatch AI is a Streamlit-based mock interviewer that ingests a candidate’s resume, runs a structured interview loop with persona-driven prompts, and produces a Markdown evaluation report. The app supports OpenAI or Ollama backends and includes a coding sandbox for live code checks (Track B).

# YOU CAN TRY IT ONLINE !!!
https://jobmatchai-roroma.streamlit.app/

## Features
- **Default local model**: Uses Hugging Face transformers (GAD-GPT-5-Chat) by default—no API key needed.
- Persona-driven interviewer prompt with conversation memory.
- Resume upload (PDF or text) with tech stack summary and project-aware question seeding.
- Structured interview flow: intro, technical deep dive, behavioral, polite conclusion.
- Automated evaluation report (score, strengths, weaknesses, sample answers).
- Coding sandbox: execute candidate code for coding questions with stdout/error capture.
- Configurable model backend (OpenAI or Ollama) via environment variables.

## Quickstart
1) Install dependencies:
```
pip install -r requirements.txt
```
2) Configure secrets in a `.env` file (keep it out of git; see `.env.example`):
- **Transformers (default)**: No API key needed; downloads model from Hugging Face on first run.
- OpenAI: set `OPENAI_API_KEY`.
- DeepSeek: set `DEEPSEEK_API_KEY` (optionally `DEEPSEEK_BASE_URL`, default https://api.deepseek.com).
- Google Gemini: set `GEMINI_API_KEY` from Google AI Studio (optionally `GEMINI_BASE_URL`).
- Ollama: run `ollama serve` and optionally set `OLLAMA_BASE_URL` (defaults to http://localhost:11434).
3) Run the app:
```
python -m streamlit run streamlit_app.py
```

## Configuration
- `MODEL_BACKEND`: `transformers` (default), `openai`, `deepseek`, `gemini`, or `ollama`.
- `MODEL_NAME`: e.g., `Qwen/Qwen2.5-3B-Instruct` (default), `gpt-4o-mini`, `deepseek-chat`, `gemini-1.5-flash-latest`, or `llama3`.
- `SYSTEM_PERSONA`: optional override for the interviewer persona prompt.
- `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`, or `OLLAMA_BASE_URL`: set in `.env` for local dev.

## Repository Structure
- `streamlit_app.py` – UI entry point and session orchestration.
- `jobmatch_ai/`
  - `llm.py` – backend abstraction for OpenAI/Ollama.
  - `prompts.py` – persona/system prompts and evaluation templates.
  - `resume_parser.py` – PDF/text extraction and tech stack heuristics.
  - `interview_flow.py` – structured interview turn planning and memory handling.
  - `evaluation.py` – post-interview Markdown report generation.
  - `sandbox.py` – constrained code execution helper (Track B).

## Notes
- Keep interviews short for demos to control token usage.
- Do not run untrusted code outside the provided sandbox helper.
- For grading, ensure a short demo video records a full interview session.
