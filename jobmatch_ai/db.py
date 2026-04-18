import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone
import random

from supabase import Client, create_client


class DBConfigError(RuntimeError):
    pass


def _get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if (not url or not key) and os.getenv("STREAMLIT_SERVER_RUNNING"):
        # Streamlit Cloud typically uses Secrets, not .env files.
        try:
            import streamlit as st  # type: ignore

            url = url or st.secrets.get("SUPABASE_URL")
            key = key or st.secrets.get("SUPABASE_ANON_KEY")
        except Exception:
            pass
    if not url or not key:
        raise DBConfigError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def sign_up(email: str, password: str) -> Dict[str, Any]:
    sb = _get_supabase()
    res = sb.auth.sign_up({"email": email, "password": password})
    return {"user": res.user, "session": res.session}


def sign_in(email: str, password: str) -> Dict[str, Any]:
    sb = _get_supabase()
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    return {"user": res.user, "session": res.session}


def sign_out(access_token: str) -> None:
    sb = _get_supabase()
    sb.auth.set_session(access_token, "")
    sb.auth.sign_out()


def create_interview(access_token: str, meta: Dict[str, Any]) -> str:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    row = sb.table("interviews").insert({"meta": meta}).execute().data[0]
    return row["id"]


def set_interview_score(access_token: str, interview_id: str, score: int) -> None:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    sb.table("interviews").update({"score": int(score)}).eq("id", interview_id).execute()


def list_scores(access_token: str) -> List[Dict[str, Any]]:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    return (
        sb.table("interviews")
        .select("created_at,score")
        .not_.is_("score", "null")
        .order("created_at")
        .execute()
        .data
    )


def add_message(access_token: str, interview_id: str, role: str, content: str) -> None:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    sb.table("messages").insert(
        {"interview_id": interview_id, "role": role, "content": content}
    ).execute()


def list_messages(access_token: str, interview_id: str) -> List[Dict[str, Any]]:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    return (
        sb.table("messages")
        .select("role,content,created_at")
        .eq("interview_id", interview_id)
        .order("created_at")
        .execute()
        .data
    )


def stats_daily_counts(access_token: str) -> List[Dict[str, Any]]:
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    # Requires a view `v_daily_message_counts` (see schema.sql)
    return sb.table("v_daily_message_counts").select("day,count").order("day").execute().data


def seed_demo_history(
    access_token: str,
    *,
    days: int = 45,
    interviews: int = 10,
    start_score: int = 55,
    end_score: int = 84,
    seed: int = 42,
) -> None:
    """
    Seed the current logged-in user with demo interviews/messages/scores.
    Writes to the hosted DB under auth.uid() via RLS.
    """
    sb = _get_supabase()
    sb.postgrest.auth(access_token)
    rng = random.Random(seed)

    now = datetime.now(timezone.utc)
    days = max(7, int(days))
    interviews = max(3, int(interviews))

    def lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    for i in range(interviews):
        t = i / max(1, interviews - 1)
        score = int(round(lerp(start_score, end_score, t) + rng.uniform(-2.5, 2.5)))
        score = max(0, min(100, score))

        day_offset = int(round(lerp(days - 1, 0, t)))
        created_at = now - timedelta(days=day_offset, hours=rng.randint(0, 10), minutes=rng.randint(0, 59))

        interview_row = (
            sb.table("interviews")
            .insert(
                {
                    "meta": {"demo": True, "seed": seed, "index": i + 1},
                    "score": score,
                    "created_at": created_at.isoformat(),
                }
            )
            .execute()
            .data[0]
        )

        interview_id = interview_row["id"]
        # Insert a handful of messages so daily activity charts move too.
        msg_count = rng.randint(8, 18)
        messages = []
        for m in range(msg_count):
            role = "assistant" if m % 2 == 0 else "user"
            messages.append(
                {
                    "interview_id": interview_id,
                    "role": role,
                    "content": "[demo] message",
                    "created_at": (created_at + timedelta(minutes=m * rng.randint(2, 6))).isoformat(),
                }
            )
        sb.table("messages").insert(messages).execute()

