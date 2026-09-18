import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Any
import httpx

from app.config import Settings, get_settings
from app.models.chat import ChatMessage, ModelInfoResponse, HealthResponse

logger = logging.getLogger("chatbot.ollama")


class OllamaService:
    """Unified LLM service supporting both Local Gemma (Ollama) and OmniRoute gateway."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def resolve_mode(self, mode: Optional[str]) -> str:
        if mode in ("local_gemma", "omniroute"):
            return mode
        return self.settings.default_generation_mode

    async def check_health(self, mode: Optional[str] = None) -> HealthResponse:
        """Check connectivity for the requested generation backend."""
        target_mode = self.resolve_mode(mode)
        if target_mode == "local_gemma":
            return await self._check_health_ollama()
        return await self._check_health_omniroute()

    async def _check_health_ollama(self) -> HealthResponse:
        ollama_status = "unreachable"
        model_installed = False
        model_loaded = False
        base_url = self.settings.ollama_base_url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                tags_res = await client.get(f"{base_url}/api/tags")
                if tags_res.status_code == 200:
                    ollama_status = "connected"
                    tags_data = tags_res.json()
                    models = [m.get("name", "") for m in tags_data.get("models", [])]
                    model_installed = any(
                        self.settings.ollama_model_name in m or m.startswith(self.settings.ollama_model_name)
                        for m in models
                    )

                try:
                    ps_res = await client.get(f"{base_url}/api/ps")
                    if ps_res.status_code == 200:
                        ps_data = ps_res.json()
                        running_models = [m.get("name", "") for m in ps_data.get("models", [])]
                        model_loaded = any(
                            self.settings.ollama_model_name in m or m.startswith(self.settings.ollama_model_name)
                            for m in running_models
                        )
                except Exception:
                    model_loaded = False
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            ollama_status = "unreachable"

        overall_status = "ready" if (ollama_status == "connected" and model_installed) else "degraded"
        if ollama_status == "unreachable":
            overall_status = "offline"

        return HealthResponse(
            status=overall_status,
            backend_status=ollama_status,
            ollama=ollama_status,
            mode="local_gemma",
            model_installed=model_installed,
            model_loaded=model_loaded,
        )

    async def _check_health_omniroute(self) -> HealthResponse:
        omniroute_status = "unreachable"
        model_installed = False
        model_loaded = False
        base_url = self.settings.omniroute_base_url.rstrip("/")

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{base_url}/models")
                if res.status_code == 200:
                    omniroute_status = "connected"
                    data = res.json()
                    models = [m.get("id", "") for m in data.get("data", [])]
                    model_installed = any(
                        self.settings.omniroute_model_name == m or self.settings.omniroute_model_name in m
                        for m in models
                    )
                    model_loaded = model_installed
        except Exception as e:
            logger.warning(f"OmniRoute health check failed: {e}")
            omniroute_status = "unreachable"

        overall_status = "ready" if (omniroute_status == "connected" and model_installed) else "degraded"
        if omniroute_status == "unreachable":
            overall_status = "offline"

        return HealthResponse(
            status=overall_status,
            backend_status=omniroute_status,
            ollama=omniroute_status,
            mode="omniroute",
            model_installed=model_installed,
            model_loaded=model_loaded,
        )

    async def get_model_info(self, mode: Optional[str] = None) -> ModelInfoResponse:
        """Get sanitized application-level model details for the specified backend."""
        target_mode = self.resolve_mode(mode)
        health = await self.check_health(mode=target_mode)
        status_text = "ready" if health.model_installed else "missing"
        if health.backend_status == "unreachable":
            status_text = "offline"

        if target_mode == "local_gemma":
            model_details: Optional[dict[str, Any]] = None
            if health.model_installed:
                try:
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        show_res = await client.post(
                            f"{self.settings.ollama_base_url.rstrip('/')}/api/show",
                            json={"name": self.settings.ollama_model_name},
                        )
                        if show_res.status_code == 200:
                            show_data = show_res.json()
                            model_details = {
                                "format": show_data.get("details", {}).get("format"),
                                "family": show_data.get("details", {}).get("family"),
                                "parameter_size": show_data.get("details", {}).get("parameter_size"),
                                "quantization_level": show_data.get("details", {}).get("quantization_level"),
                            }
                except Exception as e:
                    logger.debug(f"Could not fetch full Ollama model info: {e}")

            return ModelInfoResponse(
                name=self.settings.ollama_model_name,
                architecture="Gemma 4B Parameters (Local Ollama)",
                installed=health.model_installed,
                loaded=health.model_loaded,
                runtime="local",
                status=status_text,
                mode="local_gemma",
                details=model_details or {"backend": "Ollama", "model": self.settings.ollama_model_name},
            )

        return ModelInfoResponse(
            name=self.settings.omniroute_model_name,
            architecture="Fallback Combo (Gemini -> Groq -> Cloudflare -> OpenRouter)",
            installed=health.model_installed,
            loaded=health.model_loaded,
            runtime="omniroute",
            status=status_text,
            mode="omniroute",
            details={
                "gateway": "OmniRoute",
                "route": "Gemini -> Groq -> Cloudflare Workers AI -> OpenRouter",
                "endpoint": "/v1/chat/completions",
            },
        )

    def _format_sse(self, event: str, data: dict) -> str:
        """Format payload as an SSE event frame."""
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        rag_context: Optional[str] = None,
        rag_meta: Optional[dict] = None,
        mode: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from the chosen backend and normalize into our SSE protocol.
        Optionally augments system prompt with grounded RAG context.
        """
        target_mode = self.resolve_mode(mode)
        if target_mode == "local_gemma":
            async for frame in self._stream_ollama(messages, rag_context, rag_meta):
                yield frame
        else:
            async for frame in self._stream_omniroute(messages, rag_context, rag_meta):
                yield frame

    async def _stream_ollama(
        self,
        messages: list[ChatMessage],
        rag_context: Optional[str] = None,
        rag_meta: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        system_content = self.settings.system_prompt
        if rag_context:
            system_content = f"{self.settings.system_prompt}\n\n{rag_context}"

        payload_messages = [{"role": "system", "content": system_content}]
        for msg in messages:
            if msg.role in ("user", "assistant"):
                payload_messages.append({"role": msg.role, "content": msg.content})

        ollama_payload = {
            "model": self.settings.ollama_model_name,
            "messages": payload_messages,
            "stream": True,
            "think": self.settings.enable_thinking,
        }

        start_payload: dict[str, Any] = {
            "model": self.settings.ollama_model_name,
            "mode": "local_gemma",
        }
        if rag_meta:
            start_payload["rag"] = rag_meta
        yield self._format_sse("start", start_payload)

        base_url = self.settings.ollama_base_url.rstrip("/")
        client = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        try:
            async with client.stream(
                "POST",
                f"{base_url}/api/chat",
                json=ollama_payload,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = f"Ollama returned HTTP {response.status_code}"
                    try:
                        parsed = json.loads(error_text)
                        if "error" in parsed:
                            error_msg = parsed["error"]
                    except Exception:
                        pass
                    yield self._format_sse("error", {"message": error_msg})
                    return

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        chunk_json = json.loads(line)
                    except Exception as parse_err:
                        logger.error(f"Error parsing Ollama NDJSON line: {parse_err}")
                        continue

                    if "error" in chunk_json:
                        yield self._format_sse("error", {"message": chunk_json["error"]})
                        return

                    msg_obj = chunk_json.get("message", {})
                    thinking = msg_obj.get("thinking")
                    if thinking:
                        yield self._format_sse("thinking", {"chunk": thinking})

                    content = msg_obj.get("content")
                    if content:
                        yield self._format_sse("content", {"chunk": content})

                    if chunk_json.get("done", False):
                        usage_data = {
                            "total_duration_ms": round(
                                chunk_json.get("total_duration", 0) / 1_000_000, 2
                            ),
                            "eval_count": chunk_json.get("eval_count", 0),
                            "prompt_eval_count": chunk_json.get("prompt_eval_count", 0),
                        }
                        yield self._format_sse("complete", {"usage": usage_data})
                        return

        except httpx.ConnectError:
            logger.error("Could not connect to Ollama.")
            yield self._format_sse(
                "error",
                {
                    "message": "Local Ollama service is unreachable. Please verify Ollama is running on localhost:11434."
                },
            )
        except httpx.TimeoutException:
            logger.error("Ollama request timed out.")
            yield self._format_sse(
                "error", {"message": "Request timed out waiting for response from Gemma."}
            )
        except asyncio.CancelledError:
            logger.info("Chat stream was cancelled by client.")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during Ollama chat stream: {e}")
            yield self._format_sse(
                "error",
                {
                    "message": "An error occurred while generating the assistant response."
                },
            )
        finally:
            await client.aclose()

    async def _stream_omniroute(
        self,
        messages: list[ChatMessage],
        rag_context: Optional[str] = None,
        rag_meta: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        system_content = self.settings.system_prompt
        if rag_context:
            system_content = f"{self.settings.system_prompt}\n\n{rag_context}"

        payload_messages = [{"role": "system", "content": system_content}]
        for msg in messages:
            if msg.role in ("user", "assistant"):
                payload_messages.append({"role": msg.role, "content": msg.content})

        omniroute_payload = {
            "model": self.settings.omniroute_model_name,
            "messages": payload_messages,
            "stream": True,
        }

        start_payload: dict[str, Any] = {
            "model": self.settings.omniroute_model_name,
            "mode": "omniroute",
        }
        if rag_meta:
            start_payload["rag"] = rag_meta
        yield self._format_sse("start", start_payload)

        base_url = self.settings.omniroute_base_url.rstrip("/")
        endpoint_url = f"{base_url}/chat/completions"

        client = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        has_completed = False
        try:
            async with client.stream(
                "POST",
                endpoint_url,
                json=omniroute_payload,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = f"OmniRoute returned HTTP {response.status_code}"
                    try:
                        parsed = json.loads(error_text)
                        if "error" in parsed:
                            err_val = parsed["error"]
                            error_msg = err_val.get("message", err_val) if isinstance(err_val, dict) else str(err_val)
                    except Exception:
                        pass
                    yield self._format_sse("error", {"message": error_msg})
                    return

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()
                    if not data_str:
                        continue

                    if data_str == "[DONE]":
                        if not has_completed:
                            yield self._format_sse("complete", {"usage": {}})
                            has_completed = True
                        return

                    try:
                        chunk_json = json.loads(data_str)
                    except Exception as parse_err:
                        logger.error(f"Error parsing OmniRoute SSE line: {parse_err}")
                        continue

                    if "error" in chunk_json:
                        err_val = chunk_json["error"]
                        error_msg = err_val.get("message", err_val) if isinstance(err_val, dict) else str(err_val)
                        yield self._format_sse("error", {"message": error_msg})
                        return

                    choices = chunk_json.get("choices", [])
                    if choices:
                        choice = choices[0]
                        delta = choice.get("delta", {})

                        thinking = delta.get("reasoning_content") or delta.get("reasoning") or delta.get("thinking")
                        if thinking:
                            yield self._format_sse("thinking", {"chunk": thinking})

                        content = delta.get("content")
                        if content:
                            yield self._format_sse("content", {"chunk": content})

                        if choice.get("finish_reason") is not None:
                            usage_data = chunk_json.get("usage", {})
                            if not has_completed:
                                yield self._format_sse("complete", {"usage": usage_data})
                                has_completed = True
                            return

                if not has_completed:
                    yield self._format_sse("complete", {"usage": {}})
                    has_completed = True

        except httpx.ConnectError:
            logger.error("Could not connect to OmniRoute gateway.")
            yield self._format_sse(
                "error",
                {
                    "message": "Local OmniRoute gateway is unreachable. Please verify OmniRoute is running on http://127.0.0.1:20128."
                },
            )
        except httpx.TimeoutException:
            logger.error("OmniRoute request timed out.")
            yield self._format_sse(
                "error", {"message": "Request timed out waiting for response from OmniRoute gateway."}
            )
        except asyncio.CancelledError:
            logger.info("Chat stream was cancelled by client.")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during chat stream: {e}")
            yield self._format_sse(
                "error",
                {
                    "message": "An error occurred while generating the assistant response."
                },
            )
        finally:
            await client.aclose()
