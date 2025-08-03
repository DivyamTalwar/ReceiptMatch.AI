from .llm import CustomLLMWrapper
from typing import Any, Dict

class ReceiptExtractionLLM(CustomLLMWrapper):    
    def __init__(self):
        super().__init__()
        self.max_tokens = 2048
        self.temperature = 0.1
        self.system_message = """You are a receipt data extraction expert. 
        Extract information accurately and return structured JSON only."""

    def _base_payload(self, prompt: str) -> Dict[str, Any]:
        payload = super()._base_payload(prompt)
        payload['messages'] = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": prompt}
        ]
        payload['deep_thinking'] = False
        return payload
