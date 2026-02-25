
import json
from src.core.llm_client import LLMClient
from src.core.prompts import WORKFLOW_AGENT_PROMPT

class WorkflowAgent:
    def __init__(self, client: LLMClient):
        self.client = client
        self.system_prompt = WORKFLOW_AGENT_PROMPT

    def analyze(self, process_description: str):
        """
        Analyzes a process description (or transcript describing a process) using the Workflow Automation Agent prompt.
        """
        response_text = self.client.generate(
            system_prompt=self.system_prompt,
            user_content=process_description,
            temperature=0.2
        )
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
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
