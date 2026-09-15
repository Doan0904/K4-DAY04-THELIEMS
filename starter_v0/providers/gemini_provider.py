from __future__ import annotations

import json
import os
from typing import Any

from providers.base import ModelResponse, ToolCall
from providers.retry import call_with_retry


def _to_gemini_declarations(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    for item in tools or []:
        function = item.get("function", item)
        declarations.append({
            "name": function["name"],
            "description": function.get("description", ""),
            "parameters": function.get("parameters", {"type": "object", "properties": {}}),
        })
    return declarations


def _to_gemini_contents(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
    return ("\n\n".join(system_parts) if system_parts else None), contents


# Normalized tool_choice values (as passed by run_eval.py / agent.py) -> Gemini modes.
_FUNCTION_CALLING_MODES = {
    "required": "ANY",
    "auto": "AUTO",
    "none": "NONE",
}


def _function_calling_mode(tool_choice: Any | None) -> str | None:
    """Map a provider-neutral tool_choice to a Gemini FunctionCallingConfig mode.

    Returns None when the caller leaves the choice to the model (Gemini default).
    """
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str) and tool_choice.strip().lower() in _FUNCTION_CALLING_MODES:
        return _FUNCTION_CALLING_MODES[tool_choice.strip().lower()]
    raise ValueError(f"Unsupported tool_choice for Gemini: {tool_choice!r}. Use one of {sorted(_FUNCTION_CALLING_MODES)} or None.")


def _part_text(part: Any) -> str | None:
    if hasattr(part, "text"):
        return getattr(part, "text")
    if isinstance(part, dict):
        return part.get("text")
    return None


def _part_function_call(part: Any) -> Any | None:
    if hasattr(part, "function_call"):
        return getattr(part, "function_call")
    if isinstance(part, dict):
        return part.get("function_call")
    return None


def _function_call_name(call: Any) -> str | None:
    if hasattr(call, "name"):
        return getattr(call, "name")
    if isinstance(call, dict):
        return call.get("name")
    return None


def _function_call_args(call: Any) -> dict[str, Any]:
    if hasattr(call, "args"):
        return dict(getattr(call, "args") or {})
    if isinstance(call, dict):
        return dict(call.get("args") or {})
    return {}


class GeminiProvider:
    """Google Gemini API provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "GEMINI_API_KEY",
        default_model: str | None = None,
    ) -> None:
        self.api_key_env = api_key_env
        # Team-wide fixed model so v0-v3 runs stay comparable (paid tier, low cost).
        # gemini-2.5-flash-lite returns 404 for new users, so the team uses 3.5 Flash-Lite.
        self.default_model = default_model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install google-genai") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        system_instruction, contents = _to_gemini_contents(messages)
        declarations = _to_gemini_declarations(tools)
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if declarations:
            config_kwargs["tools"] = [types.Tool(function_declarations=declarations)]
            mode = _function_calling_mode(tool_choice)
            if mode is not None:
                config_kwargs["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode=mode)
                )

        client = genai.Client(api_key=api_key)
        selected_model = model or self.default_model
        config = types.GenerateContentConfig(**config_kwargs)
        resp = call_with_retry(
            lambda: client.models.generate_content(model=selected_model, contents=contents, config=config),
            label=selected_model,
        )

        text_parts: list[str] = []
        calls: list[ToolCall] = []

        def append_call(function_call: Any) -> None:
            name = _function_call_name(function_call)
            if name:
                calls.append(ToolCall(name=name, args=_function_call_args(function_call)))

        for candidate in getattr(resp, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                text = _part_text(part)
                if text:
                    text_parts.append(text)
                function_call = _part_function_call(part)
                if function_call:
                    append_call(function_call)

        # Some SDK versions expose function calls directly on the response.
        for function_call in getattr(resp, "function_calls", []) or []:
            append_call(function_call)

        deduped_calls: list[ToolCall] = []
        seen: set[tuple[str, str]] = set()
        for call in calls:
            key = (call.name, json.dumps(call.args, ensure_ascii=False, sort_keys=True))
            if key not in seen:
                seen.add(key)
                deduped_calls.append(call)

        return ModelResponse(text="\n".join(part for part in text_parts if part) or None, tool_calls=deduped_calls, raw=resp)
