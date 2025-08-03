import os
import json
import httpx
from typing import Any, Sequence, Generator, AsyncGenerator, Dict
from dotenv import load_dotenv

from llama_index.core.llms import CustomLLM, CompletionResponse, CompletionResponseGen
from llama_index.core.llms.callbacks import llm_completion_callback
from llama_index.core.base.llms.types import ChatMessage, MessageRole
import asyncio

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

class CustomLLMWrapper(CustomLLM):
    """LlamaIndex-compatible wrapper for your custom LLM"""
    
    model_name: str = "custom_llm"
    temperature: float = 0.1
    max_tokens: int = 4096
    system_message: str = ""
    
    def __init__(self):
        super().__init__()
        pass

    @property
    def metadata(self) -> dict:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {os.getenv('MODELS_API_KEY')}",
            "Content-Type": "application/json",
        }

    def _base_payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": "omega",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "deep_thinking": True,
            "stream": False,
        }

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        with llm_completion_callback():
            payload = self._base_payload(prompt)
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(os.getenv('LLM_ENDPOINT'), headers=self._get_headers(), json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    response_text = data["choices"][0]["message"]["content"]
                    return CompletionResponse(text=response_text)
            except Exception as e:
                # Robust error handling
                return CompletionResponse(text=f"Error: {str(e)}")

    def stream_complete(self, prompt: str, **kwargs) -> CompletionResponseGen:
        with llm_completion_callback():
            payload = self._base_payload(prompt)
            payload["stream"] = True

            def gen() -> Generator[CompletionResponse, None, None]:
                with httpx.stream("POST", os.getenv('LLM_ENDPOINT'), headers=self._get_headers(), json=payload, timeout=60.0) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:") :].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            piece = json.loads(chunk)
                            delta = piece.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            yield CompletionResponse(text="", delta=delta)
                        except json.JSONDecodeError:
                            continue
            return gen()

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        """Asynchronous completion with timeout handling."""
        return await self.process_with_timeout(prompt)

    async def process_with_timeout(self, prompt: str, timeout: int = 45):
        """Process with timeout to prevent Streamlit timeouts"""
        try:
            async def _complete():
                payload = self._base_payload(prompt)
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(os.getenv('LLM_ENDPOINT'), headers=self._get_headers(), json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    response_text = data["choices"][0]["message"]["content"]
                    return CompletionResponse(text=response_text)
            
            return await asyncio.wait_for(_complete(), timeout=timeout)

        except asyncio.TimeoutError:
            return CompletionResponse(text="Error: Processing timeout")
        except Exception as e:
            return CompletionResponse(text=f"Error: {str(e)}")
