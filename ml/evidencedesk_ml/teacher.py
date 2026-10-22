"""Minimal client for an OpenAI-compatible teacher model (llama.cpp, vLLM, Workers AI)."""

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


class TeacherError(RuntimeError):
    pass


@dataclass
class Teacher:
    base_url: str
    model: str = "teacher"
    api_key: str = ""
    timeout: float = 300
    max_retries: int = 3
    usage: dict[str, int] = field(
        default_factory=lambda: {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any] | None = None,
        max_tokens: int = 1200,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if seed is not None:
            payload["seed"] = seed
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "strict": True, "schema": schema},
            }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = httpx.post(
                    self.base_url.rstrip("/") + "/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage") or {}
                self.usage["calls"] += 1
                self.usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                self.usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                if not content or not content.strip():
                    raise TeacherError("empty completion")
                return content
            except (httpx.HTTPError, KeyError, IndexError, TeacherError) as exc:
                last = exc
                time.sleep(2 * (attempt + 1))
        raise TeacherError(f"teacher failed after {self.max_retries} attempts: {last}")

    def chat_json(self, messages: list[dict[str, str]], schema: dict[str, Any], **kwargs) -> Any:
        return json.loads(self.chat(messages, schema=schema, **kwargs))
