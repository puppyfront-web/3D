"""OpenAI-compatible LLM provider using the openai Python SDK."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Default timeout for LLM calls (seconds).
# Prevents SSE streams from hanging indefinitely when the API is unreachable.
# 300s accommodates slow/heavy models (e.g. deepkey's gpt-5.4) whose chat
# completions can exceed the previous 120s read timeout and surface as a
# stream error after 3 retries.
_LLM_TIMEOUT = 300


class OpenAILLMService:
    """LLM service backed by an OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
            timeout=httpx.Timeout(_LLM_TIMEOUT, connect=10.0),
        )
        self._model = model

    def _extract_content(self, response: Any) -> str:
        """Extract text content from various OpenAI-compatible API response formats."""
        if isinstance(response, str):
            return response
        if hasattr(response, "choices") and response.choices:
            msg = response.choices[0].message
            return msg.content if hasattr(msg, "content") else str(msg)
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices and isinstance(choices[0], dict):
                return choices[0].get("message", {}).get("content", "")
        return ""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a text completion from a prompt.

        Includes retry logic for providers that occasionally return
        empty content or SSE chunk data instead of a complete response.
        """
        messages = self._build_messages(prompt, system_prompt)
        for attempt in range(1, 4):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = self._extract_content(response)

            # Detect SSE chunk data leaked into content
            if content and content.strip().startswith("data:"):
                logger.warning(
                    "generate() received SSE chunk data (attempt %d/3), retrying",
                    attempt,
                )
                continue

            if content and content.strip():
                return content

            logger.warning(
                "generate() received empty content (attempt %d/3), retrying",
                attempt,
            )

        return ""

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        *,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Generate a JSON-structured completion with automatic retry on empty/invalid response.

        Some OpenAI-compatible providers intermittently return empty content when
        ``response_format={"type": "json_object"}`` is used.  We retry up to
        *max_retries* times and fall back to a plain ``generate`` + JSON extraction
        on the last attempt.
        """
        messages = self._build_messages(
            prompt,
            system_prompt or "You are a helpful assistant that responds in JSON format.",
        )

        for attempt in range(1, max_retries + 1):
            try:
                # Last attempt: skip response_format — use plain text generation
                # as a fallback for providers that don't reliably support it.
                use_response_format = attempt < max_retries

                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    **({"response_format": {"type": "json_object"}} if use_response_format else {}),
                )
            except Exception as e:
                logger.error("OpenAI generate_json call failed (attempt %d/%d): %s", attempt, max_retries, e)
                if attempt == max_retries:
                    raise
                continue

            # Extract text content from the response
            content = self._extract_content(response)

            # Empty content — treat as failure and retry
            if not content or not content.strip():
                logger.warning("generate_json received empty content (attempt %d/%d), retrying", attempt, max_retries)
                if attempt == max_retries:
                    return {"raw_response": ""}
                continue

            # Try to parse the content as JSON
            result = self._try_parse_json(content)
            if result is not None:
                return result

            # JSON parse failed — retry unless this was the last attempt
            logger.warning("LLM returned invalid JSON (attempt %d/%d), retrying", attempt, max_retries)
            if attempt == max_retries:
                return {"raw_response": content}

        # Should not reach here, but safety net
        return {"raw_response": ""}

    @staticmethod
    def _try_parse_json(content: str) -> Optional[Dict[str, Any]]:
        """Attempt to parse content as JSON with multiple extraction strategies."""
        import re

        # 1. Direct parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 2. Markdown code blocks: ```json ... ```
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Try to find the first {...} or [...] in the text
        for pattern in [r'\{[\s\S]*\}', r'\[[\s\S]*\]']:
            match = re.search(pattern, content)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    continue

        return None

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Async generator yielding completion chunks."""
        messages = self._build_messages(prompt, system_prompt)
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Generate with full multi-turn message history."""
        api_messages = self._build_history_messages(messages, system_prompt)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._extract_content(response) or ""

    async def generate_with_history_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream with full multi-turn message history."""
        api_messages = self._build_history_messages(messages, system_prompt)
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=api_messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _build_history_messages(
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build message list from conversation history."""
        api_messages: List[Dict[str, str]] = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)
        return api_messages

    @staticmethod
    def _build_messages(
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Build the message list for the OpenAI API."""
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
