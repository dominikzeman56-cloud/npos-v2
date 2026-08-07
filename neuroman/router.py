# neuroman/router.py
"""OmniRoute async client with retries, timeouts, and circuit breaker."""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from .resilience import (
    ErrorKind,
    NeuroError,
    get_breaker,
    retry_async,
)

log = logging.getLogger("neuroman.router")

_VALID_INTENTS = frozenset({"CODE", "ABLETON", "MUSIC", "GENERAL"})
_INTENT_FALLBACK_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\b(code|python|script|refactor|git|repo|bug|test|ci|deploy)\b"), "CODE"),
    (re.compile(r"(?i)\b(ableton|live\s*set|clip|track|daw|producer\s*pal|ppal)\b"), "ABLETON"),
    (re.compile(r"(?i)\b(mix|bass|kick|eq|compress|reese|neurofunk|tempo|bpm|melody)\b"), "MUSIC"),
]


class OmniRouteClient:
    """Klient pro lokalni OmniRoute gateway (OpenAI-compatible)."""

    def __init__(self) -> None:
        self.base_url = os.getenv("OMNIROUTE_URL", "http://localhost:20128/v1")
        self.api_key = os.getenv("OMNIROUTE_KEY", "omniroute-local-bypass")
        timeout = float(os.getenv("NEUROMAN_LLM_TIMEOUT", "60"))
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
            max_retries=0,  # we own retry policy
        )
        self.model_fast = os.getenv("NEUROMAN_MODEL_FAST", "auto/best-fast")
        self.model_strong = os.getenv("NEUROMAN_MODEL_STRONG", "auto/best-reasoning")
        self.model_coding = os.getenv("NEUROMAN_MODEL_CODING", "auto/best-coding")
        self._breaker = get_breaker("omniroute")

    @staticmethod
    def _heuristic_intent(prompt: str) -> str:
        for pattern, intent in _INTENT_FALLBACK_RULES:
            if pattern.search(prompt):
                return intent
        return "GENERAL"

    def _map_openai_error(self, exc: BaseException) -> NeuroError:
        if isinstance(exc, RateLimitError):
            return NeuroError(
                message="OmniRoute rate limit.",
                kind=ErrorKind.RATE_LIMIT,
                source="omniroute",
                detail=str(exc),
            )
        if isinstance(exc, APITimeoutError):
            return NeuroError(
                message="OmniRoute timeout.",
                kind=ErrorKind.TIMEOUT,
                source="omniroute",
                detail=str(exc),
            )
        if isinstance(exc, APIConnectionError):
            return NeuroError(
                message="Nelze se spojit s OmniRoute.",
                kind=ErrorKind.NETWORK,
                source="omniroute",
                detail=str(exc),
            )
        if isinstance(exc, APIStatusError):
            kind = ErrorKind.AUTH if exc.status_code in (401, 403) else ErrorKind.DEPENDENCY_DOWN
            return NeuroError(
                message=f"OmniRoute HTTP {exc.status_code}.",
                kind=kind,
                source="omniroute",
                detail=str(exc),
            )
        return NeuroError(
            message="OmniRoute neocekavana chyba.",
            kind=ErrorKind.INTERNAL,
            source="omniroute",
            detail=repr(exc),
        )

    async def _chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int] = None,
        label: str = "chat",
    ) -> str:
        async def _once() -> str:
            try:
                kwargs: dict = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    kwargs["max_tokens"] = max_tokens
                response = await self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content is None:
                    raise NeuroError(
                        message="Prazdna odpoved z modelu.",
                        kind=ErrorKind.MALFORMED,
                        source="omniroute",
                    )
                return content.strip()
            except NeuroError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise self._map_openai_error(exc) from exc

        return await retry_async(
            _once,
            attempts=3,
            base_delay=0.5,
            breaker=self._breaker,
            label=label,
        )

    async def get_intent(self, prompt: str) -> str:
        """Fast intent classification; heuristic fallback if OmniRoute is down."""
        system_prompt = (
            "Jsi binarni klasifikator systemu NeuroMan. Tvuj vystup musi byt "
            "vyhradne jedno slovo z mnoziny: [CODE, ABLETON, MUSIC, GENERAL]. "
            "CODE = programovani, repozitare, VS Code, skripty, refaktoring. "
            "ABLETON = ovladani Ableton Live, tracky, klipy, efekty, DAW akce. "
            "MUSIC = hudebni teorie, rady k mixazi/kompozici bez pozadavku na akci v DAW. "
            "GENERAL = vse ostatni."
        )
        try:
            raw = await self._chat(
                model=self.model_fast,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=10,
                label="intent",
            )
            token = raw.split()[0].upper().strip(".,:;!?") if raw else ""
            if token in _VALID_INTENTS:
                return token
            # model drifted — try to find a valid token inside
            for cand in _VALID_INTENTS:
                if cand in raw.upper():
                    return cand
            log.warning("intent parse miss %r -> heuristic", raw)
            return self._heuristic_intent(prompt)
        except NeuroError as exc:
            log.warning("intent via OmniRoute failed: %s — heuristic", exc)
            return self._heuristic_intent(prompt)

    async def generate_completion(
        self,
        prompt: str,
        system_message: str = "",
        model: str | None = None,
        *,
        temperature: float = 0.7,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        return await self._chat(
            model=model or self.model_strong,
            messages=messages,
            temperature=temperature,
            label="completion",
        )

    async def aclose(self) -> None:
        await self.client.close()
