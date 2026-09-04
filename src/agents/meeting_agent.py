from src.core.json_extraction import extract_json
from src.core.llm_client import LLMClient
from src.core.prompts import MEETING_AGENT_PROMPT


class MeetingAgent:
    def __init__(self, client: LLMClient):
        self.client = client
        self.system_prompt = MEETING_AGENT_PROMPT

    def analyze(self, transcript: str):
        """
        Analyzes a meeting transcript using the Meeting Intelligence Agent prompt.
        """
        response_text = self.client.generate(
            system_prompt=self.system_prompt,
            user_content=transcript,
            temperature=0.2,  # Structured output
        )

        # Attempt to parse JSON.
        # Extraction lives in one place now. All three agents carried a copy
        # with the same defects: a greedy brace regex that swallowed trailing
        # prose, fenced-block fallbacks that raised out of the error handler,
        # and an IndexError on an unmatched fence. See core/json_extraction.
        return extract_json(response_text)
