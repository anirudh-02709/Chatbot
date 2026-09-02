import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Any
import httpx

from app.config import Settings, get_settings
from app.models.chat import ChatMessage, ModelInfoResponse, HealthResponse

logger = logging.getLogger("chatbot.ollama")


class OllamaService:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def check_health(self) -> HealthResponse:
        """Check Ollama connectivity and whether the model is installed and loaded."""
        ollama_status = "unreachable"
        model_installed = False
        model_loaded = False

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # 1. Check tags / installed models
                tags_res = await client.get(f"{self.settings.ollama_base_url}/api/tags")
                if tags_res.status_code == 200:
                    ollama_status = "connected"
                    tags_data = tags_res.json()
                    models = [m.get("name", "") for m in tags_data.get("models", [])]
                    model_installed = any(
                        self.settings.model_name in m or m.startswith(self.settings.model_name)
                        for m in models
                    )

                # 2. Check running / loaded models via /api/ps
                try:
                    ps_res = await client.get(f"{self.settings.ollama_base_url}/api/ps")
                    if ps_res.status_code == 200:
                        ps_data = ps_res.json()
                        running_models = [m.get("name", "") for m in ps_data.get("models", [])]
                        model_loaded = any(
                            self.settings.model_name in m or m.startswith(self.settings.model_name)
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
            ollama=ollama_status,
            model_installed=model_installed,
            model_loaded=model_loaded,
        )

    async def get_model_info(self) -> ModelInfoResponse:
        """Get sanitized application-level model details."""
        health = await self.check_health()
        model_details: Optional[dict[str, Any]] = None

        if health.model_installed:
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    show_res = await client.post(
                        f"{self.settings.ollama_base_url}/api/show",
                        json={"name": self.settings.model_name},
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
                logger.debug(f"Could not fetch full model info: {e}")

        status_text = "ready" if health.model_installed else "missing"
        if health.ollama == "unreachable":
            status_text = "offline"

        return ModelInfoResponse(
            name=self.settings.model_name,
            architecture="4B Parameters",
            installed=health.model_installed,
            loaded=health.model_loaded,
            runtime="local",
            status=status_text,
            details=model_details,
        )

    def _format_sse(self, event: str, data: dict) -> str:
        """Format payload as an SSE event frame."""
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        rag_context: Optional[str] = None,
        rag_meta: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Ollama and normalize NDJSON into our SSE protocol.
        Optionally augments system prompt with grounded RAG context.
        """
        # 1. Build sanitized Ollama messages list
        system_content = self.settings.system_prompt
        if rag_context:
            system_content = f"{self.settings.system_prompt}\n\n{rag_context}"

        payload_messages = [{"role": "system", "content": system_content}]
        for msg in messages:
            if msg.role in ("user", "assistant"):
                payload_messages.append({"role": msg.role, "content": msg.content})

        ollama_payload = {
            "model": self.settings.model_name,
            "messages": payload_messages,
            "stream": True,
            "think": self.settings.enable_thinking,
        }

        # Yield initial start event with optional RAG diagnostics
        start_payload: dict[str, Any] = {"model": self.settings.model_name}
        if rag_meta:
            start_payload["rag"] = rag_meta
        yield self._format_sse("start", start_payload)

        client = httpx.AsyncClient(timeout=self.settings.request_timeout_seconds)
        try:
            async with client.stream(
                "POST",
                f"{self.settings.ollama_base_url}/api/chat",
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

                    # Check for mid-stream error from Ollama
                    if "error" in chunk_json:
                        yield self._format_sse(
                            "error", {"message": chunk_json["error"]}
                        )
                        return

                    msg_obj = chunk_json.get("message", {})

                    # Extract thinking if present (sent as thinking event, distinct from content)
                    thinking = msg_obj.get("thinking")
                    if thinking:
                        yield self._format_sse("thinking", {"chunk": thinking})

                    # Extract content chunk
                    content = msg_obj.get("content")
                    if content:
                        yield self._format_sse("content", {"chunk": content})

                    # Check if stream is complete
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
            # Let the stream end cleanly on disconnect
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
