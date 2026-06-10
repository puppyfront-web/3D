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
_LLM_TIMEOUT = 60


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

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a text completion from a prompt."""
        messages = self._build_messages(prompt, system_prompt)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content or ""

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> Dict[str, Any]:
        """Generate a JSON-structured completion."""
        messages = self._build_messages(
            prompt,
            system_prompt or "You are a helpful assistant that responds in JSON format.",
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.error("OpenAI generate_json call failed: %s", e)
            raise
        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON, attempting extraction")
            # Try to extract JSON from markdown code blocks
            import re
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return {"raw_response": content}

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
        content = response.choices[0].message.content
        return content or ""

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
