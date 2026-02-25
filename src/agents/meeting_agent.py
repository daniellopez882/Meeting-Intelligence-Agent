
import json
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
            temperature=0.2 # Structured output
        )
        
        # Attempt to parse JSON. 
        # In a real app, might want to use a retry mechanism if JSON is invalid.
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find a JSON block in the response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass

            if "```json" in response_text:
                cleaned = response_text.split("```json")[1].split("```")[0].strip()
                return json.loads(cleaned)
            elif "```" in response_text:
                cleaned = response_text.split("```")[1].split("```")[0].strip()
                return json.loads(cleaned)
            return {"error": "Failed to parse JSON", "raw_response": response_text}
