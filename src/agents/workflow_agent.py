from src.core.json_extraction import extract_json
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
            system_prompt=self.system_prompt, user_content=process_description, temperature=0.2
        )
        # Extraction lives in one place now. All three agents carried a copy
        # with the same defects: a greedy brace regex that swallowed trailing
        # prose, fenced-block fallbacks that raised out of the error handler,
        # and an IndexError on an unmatched fence. See core/json_extraction.
        return extract_json(response_text)
