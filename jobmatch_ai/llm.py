import os
import re
from typing import List, Dict, Optional

from openai import OpenAI, OpenAIError
from pydantic import BaseModel

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv() -> bool:  # type: ignore
        return False


load_dotenv()


_GEMINI_MODEL_ALIASES = {
    "gemini": "gemini-2.5-flash",
    "gemini-lite": "gemini-2.5-flash",
    "gemini-2.5": "gemini-2.5-flash",
}

class LLMConfig(BaseModel):
    backend: str = "gemini"  # "openai", "deepseek", "gemini", or "ollama"
    model: str = "gemini-2.5-flash"
    base_url: str | None = None
    api_key: str | None = None


def build_client(cfg: LLMConfig) -> OpenAI:
    if cfg.backend == "ollama":
        base_url = cfg.base_url or "http://localhost:11434/v1"
        api_key = cfg.api_key or "ollama"
    elif cfg.backend == "deepseek":
        base_url = cfg.base_url or "https://api.deepseek.com"
        api_key = cfg.api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek backend")
    elif cfg.backend == "gemini":
        base_url = cfg.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        api_key = cfg.api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini backend")
    else:  # openai
        base_url = cfg.base_url or None
        api_key = cfg.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI backend")
    return OpenAI(base_url=base_url, api_key=api_key)


def _normalize_gemini_model(model: str) -> str:
    return _GEMINI_MODEL_ALIASES.get(model.strip().lower(), model.strip())


def _format_gemini_rate_limit_error(exc: OpenAIError, model: str) -> RuntimeError:
    message = str(exc)
    retry_match = re.search(r"retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", message, flags=re.IGNORECASE)
    retry_hint = f" Please retry after about {retry_match.group(1)}s." if retry_match else ""
    return RuntimeError(
        f"Gemini quota or rate limit exceeded for model '{model}'. "
        f"Wait and retry, switch to a paid Gemini project, or choose another backend.{retry_hint}"
    )


def complete(cfg: LLMConfig, messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    client = build_client(cfg)
    model = _normalize_gemini_model(cfg.model) if cfg.backend == "gemini" else cfg.model
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content  # type: ignore[index]
    except OpenAIError as exc:
        message = str(exc)
        if cfg.backend == "gemini" and ("429" in message or "quota" in message.lower() or "rate limit" in message.lower()):
            raise _format_gemini_rate_limit_error(exc, model) from exc
        raise RuntimeError(f"LLM call failed: {exc}") from exc
