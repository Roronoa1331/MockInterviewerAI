# JobMatch AI – Mock Interviewer Agent

JobMatch AI is a Streamlit-based mock interviewer that ingests a candidate’s resume, runs a structured interview loop with persona-driven prompts, and produces a Markdown evaluation report. The app supports OpenAI or Ollama backends and includes a coding sandbox for live code checks (Track B).

# YOU CAN TRY IT ONLINE !!!
https://jobmatchai-roroma.streamlit.app/

## Features
- Configurable model backend (OpenAI, DeepSeek, Gemini, or Ollama) via environment variables.
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
- OpenAI: set `OPENAI_API_KEY`.
- DeepSeek: set `DEEPSEEK_API_KEY` (optionally `DEEPSEEK_BASE_URL`, default https://api.deepseek.com).
- Google Gemini: set `GEMINI_API_KEY` from Google AI Studio (optionally `GEMINI_BASE_URL`).
- Ollama: run `ollama serve` and optionally set `OLLAMA_BASE_URL` (defaults to http://localhost:11434).
3) (Optional but recommended) Enable hosted accounts + database (NOT local):
   - Create a free Supabase project.
   - In Supabase SQL Editor, run the schema in `supabase_schema.sql`.
   - In `.env`, set:
     - `SUPABASE_URL`
     - `SUPABASE_ANON_KEY`
3) Run the app:
```
python -m streamlit run streamlit_app.py
```

## Configuration
- `MODEL_BACKEND`: `openai`, `deepseek`, `gemini`, or `ollama`.
- `MODEL_NAME`: e.g., `gpt-4o-mini`, `deepseek-chat`, `gemini-1.5-flash-latest`, or `llama3`.
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
  - `retriever.py` – RAG retrieval module over the Chroma vector store.
  - `kb_build.py` – one-shot build script to index CSV question banks + KB docs.
- `questionBank1/` – 前端岗位题库（17 个主题，~1260 道题）
- `questionBank2/` – Unity 游戏客户端岗位题库（13 个主题，~980 道题）
- `kb/` – 岗位知识文档（role_frontend.md / role_unity.md），按二级标题分段入库
- `vector_store/` – 预构建的 Chroma 向量库（2261 chunks，已 commit，无需重新构建）

## RAG 构建方式

本项目已集成简单而完整的 RAG（检索增强生成）系统，用于在**出题**和**评估**两处真正使用题库与岗位知识。

### 架构说明

```
questionBank1/ + questionBank2/ + kb/*.md
        ↓ python -m jobmatch_ai.kb_build
   vector_store/  (Chroma PersistentClient, cosine 距离)
        ↓ 运行时
   jobmatch_ai/retriever.py  →  interview_flow.py (出题)
                              →  evaluation.py (评分)
```

- **Embedding 模型**：`BAAI/bge-small-zh-v1.5`（本地、CPU 可运行、中文优化），通过 `sentence-transformers` 加载。
- **向量库**：`chromadb.PersistentClient`，存储于 `vector_store/`。
- **已预构建**：`vector_store/` 目录已 commit，直接克隆即可运行，无需重新嵌入。

### 重新构建向量库（可选，修改题库后需执行）

```bash
# 需要 Python 3.9+
pip install chromadb sentence-transformers
python -m jobmatch_ai.kb_build
```

输出示例：
```
INFO: Build complete!  Total chunks: 2261
INFO:   Role 'frontend': 1270 chunks
INFO:   Role 'unity': 991 chunks
INFO:   Type 'knowledge': 21 chunks
INFO:   Type 'question': 2240 chunks
```

### RAG 生效的两处

1. **出题（`interview_flow.py`）**：`_get_technical_question()` 用技术栈作为 query 调用 `retriever.search()`，按 role 过滤后取相似度最高的未用题目。出题来源会在 directive 中标注 `[retrieved from vector store]`，可通过侧栏"Show interview directives"开关查看。

2. **评估（`evaluation.py`）**：在 `technical_knowledge` 维度评分时，将候选人回答拼成 query，检索最相关的 3 条"标准答案要点"和"岗位评分规则"注入 prompt，生成的报告末尾附 `### Retrieved Knowledge (for transparency)` 节，列出实际使用的检索结果。

### 两种降级保护

- 若向量库文件不存在，`interview_flow.py` 自动退回原 `available_questions` 随机抽题逻辑（不报错）。
- 评估函数若检索失败，仍使用标准 LLM prompt 评分，不中断报告生成。

## Notes
- Keep interviews short for demos to control token usage.
- Do not run untrusted code outside the provided sandbox helper.
- For grading, ensure a short demo video records a full interview session.

## What’s new
- Follow-up questioning: after every candidate answer, the next interviewer turn asks exactly one targeted follow-up before moving on.
- Accounts + persistence: when logged in, interviews/messages are stored in Supabase (cloud Postgres) and a simple stats chart is shown.
