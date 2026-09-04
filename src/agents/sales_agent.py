from src.core.json_extraction import extract_json
from src.core.llm_client import LLMClient
from src.core.prompts import SALES_AGENT_PROMPT


class SalesAgent:
    def __init__(self, client: LLMClient):
        self.client = client
        self.system_prompt = SALES_AGENT_PROMPT

    def analyze(self, transcript: str):
        """
        Analyzes a sales call transcript using the Sales Intelligence Agent prompt.
        """
        response_text = self.client.generate(
            system_prompt=self.system_prompt, user_content=transcript, temperature=0.2
        )
        # Extraction lives in one place now. All three agents carried a copy
        # with the same defects: a greedy brace regex that swallowed trailing
        # prose, fenced-block fallbacks that raised out of the error handler,
        # and an IndexError on an unmatched fence. See core/json_extraction.
        return extract_json(response_text)
