from __future__ import annotations

import json
from dataclasses import dataclass

import requests


@dataclass
class LlmResponse:
    text: str


class LlmClient:
    def __init__(self, provider: str, api_key: str, model: str) -> None:
        self.provider = provider.lower().strip()
        self.api_key = api_key
        self.model = model

    def enabled(self) -> bool:
        return bool(self.provider and self.api_key)

    def chat(self, system: str, user: str) -> LlmResponse | None:
        if not self.enabled():
            return None
        if self.provider == "openai":
            return self._openai_chat(system, user)
        if self.provider == "yandex":
            return self._yandex_chat(system, user)
        return None

    def _openai_chat(self, system: str, user: str) -> LlmResponse | None:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            return None
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return LlmResponse(text=content)

    def _yandex_chat(self, system: str, user: str) -> LlmResponse | None:
        # Uses YandexGPT compatible chat endpoint if provided.
        # Expect env model like "gpt://<folder-id>/yandexgpt/latest".
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "modelUri": self.model,
            "completionOptions": {"stream": False, "temperature": 0.2, "maxTokens": 2000},
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        try:
            resp.raise_for_status()
        except requests.HTTPError:
            return None
        data = resp.json()
        content = data["result"]["alternatives"][0]["message"]["text"]
        return LlmResponse(text=content)
