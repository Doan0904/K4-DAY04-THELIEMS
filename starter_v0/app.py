"""Streamlit chat UI for the IT Helpdesk Agent.

Reuses chat.run_model_tool_loop so the CLI chat, eval evidence and this UI share one
agent loop. Every turn is appended to a transcript JSON with the same shape as chat.py.

Run from starter_v0/:
    streamlit run app.py
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import ARTIFACTS_DIR, ROOT, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


# The team's fixed provider (OpenAI gpt-4o-mini) comes first so it is the default.
PROVIDERS = ["openai", "openrouter", "anthropic", "gemini"]
TRANSCRIPTS_DIR = Path(os.getenv("HELPDESK_TRANSCRIPTS_DIR", ROOT / "transcripts"))
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"
STATUS_LABELS = {
    "answered": "✅ answered",
    "waiting_for_user": "❓ waiting_for_user",
    "max_tool_rounds": "⚠️ max_tool_rounds",
    "provider_error": "❌ provider_error",
}


def start_session(config: dict[str, Any], artifact_version: Any, selected_model: str | None) -> None:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(config["version"]), safe_slug(config["provider"]), "ui", timestamp])
    st.session_state.config = config
    st.session_state.history = []
    st.session_state.transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    st.session_state.transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": config["provider"],
        "model": selected_model,
        "system_prompt": str(SYSTEM_PROMPT_PATH),
        "tools": str(TOOLS_PATH),
        "history_window": config["history_window"],
        "max_tool_rounds": config["max_tool_rounds"],
        "client": "streamlit",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


def render_tool_event(event: dict[str, Any]) -> None:
    result = event.get("result")
    error = result.get("error") if isinstance(result, dict) else None
    marker = f"🔴 error: `{error}`" if error else "🟢 ok"
    st.markdown(f"**`{event.get('tool')}`** — {marker}")
    st.caption("args")
    st.json(event.get("args") or {}, expanded=True)
    st.caption("result")
    st.json(result if result is not None else {}, expanded=bool(error))


def render_turn(turn: dict[str, Any], artifact_label: str) -> None:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        st.markdown(turn.get("assistant_text") or "_(no text)_")
        status = STATUS_LABELS.get(turn.get("status", ""), turn.get("status", ""))
        rounds = turn.get("rounds") or []
        st.caption(f"{status} · rounds: {len(rounds)} · artifact: {artifact_label}")
        if turn.get("error"):
            st.error(turn["error"])
        for record in rounds:
            calls = record.get("tool_calls") or []
            with st.expander(f"Round {record.get('round')} — {len(calls)} tool call(s)", expanded=True):
                if record.get("assistant_text"):
                    st.markdown(f"_Model text:_ {record['assistant_text']}")
                if not calls:
                    st.write("No tool call — final answer.")
                for event in record.get("tool_results") or []:
                    render_tool_event(event)


st.set_page_config(page_title="IT Helpdesk Agent", page_icon="🛠️", layout="wide")

with st.sidebar:
    st.header("Configuration")
    provider_name = st.selectbox("Provider", PROVIDERS, index=0)
    version = st.text_input("Artifact version label", value="v3")
    model_override = st.text_input("Model override (optional)", value="").strip() or None
    history_window = int(st.number_input("History window (user/assistant pairs)", min_value=0, max_value=20, value=5))
    max_tool_rounds = int(st.number_input("Max tool rounds", min_value=1, max_value=8, value=4))

provider = make_provider(provider_name)
selected_model = model_override or getattr(provider, "default_model", None)
artifact_version = build_artifact_version(version, SYSTEM_PROMPT_PATH, TOOLS_PATH)
config = {
    "provider": provider_name,
    "version": version,
    "model": model_override,
    "history_window": history_window,
    "max_tool_rounds": max_tool_rounds,
    "artifact_version": artifact_version.artifact_version,
}
# Any config or artifact change starts a new transcript so evidence never mixes versions.
if st.session_state.get("config") != config:
    start_session(config, artifact_version, selected_model)

with st.sidebar:
    st.subheader("Artifact version")
    st.code(artifact_version.artifact_version, language=None)
    st.caption(f"prompt_hash: `{artifact_version.prompt_hash[:12]}` · tools_hash: `{artifact_version.tools_hash[:12]}`")
    st.caption(f"model: `{selected_model}`")
    st.caption(f"transcript: `{st.session_state.transcript_path.relative_to(ROOT) if st.session_state.transcript_path.is_relative_to(ROOT) else st.session_state.transcript_path}`")
    if st.button("New conversation"):
        start_session(config, artifact_version, selected_model)
        st.rerun()

st.title("🛠️ IT Helpdesk Agent")
st.caption("Northstar Labs (fictional) · all data is synthetic · tool calls, args and results are shown for audit")

for turn in st.session_state.transcript["turns"]:
    render_turn(turn, artifact_version.artifact_version)

user_text = st.chat_input("Nhập yêu cầu IT helpdesk…")
if user_text:
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    openai_tools = to_openai_tools(load_tool_declarations(TOOLS_PATH))
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, history_window),
        {"role": "user", "content": user_text},
    ]
    turn_record: dict[str, Any] = {
        "turn_index": len(st.session_state.transcript["turns"]) + 1,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }
    with st.spinner("Agent đang xử lý…"):
        try:
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=model_override,
                max_tool_rounds=max_tool_rounds,
            )
            turn_record.update(result)
            st.session_state.history.append({"role": "user", "content": user_text})
            st.session_state.history.append({"role": "assistant", "content": result["assistant_text"]})
        except Exception as exc:
            turn_record.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(st.session_state.transcript_path, st.session_state.transcript)
    st.rerun()
