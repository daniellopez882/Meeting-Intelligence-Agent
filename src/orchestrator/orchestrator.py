
import json
from src.core.llm_client import LLMClient
from src.core.prompts import ORCHESTRATOR_PROMPT
from src.agents.meeting_agent import MeetingAgent
from src.agents.sales_agent import SalesAgent
from src.agents.workflow_agent import WorkflowAgent

class Orchestrator:
    def __init__(self, client: LLMClient):
        self.client = client
        self.system_prompt = ORCHESTRATOR_PROMPT
        self.meeting_agent = MeetingAgent(client)
        self.sales_agent = SalesAgent(client)
        self.workflow_agent = WorkflowAgent(client)

    def process_request(self, user_request: str, content_context: str = ""):
        """
        Orchestrates the processing of a user request.
        
        Args:
            user_request: The specific instruction from the user (e.g., "Analyze this sales call...")
            content_context: The content to process (e.g., the transcript text).
        """
        
        # Step 1: Planning
        # We ask the Orchestrator to decide which agents to use.
        # We wrap the user request to specifically ask for a plan.
        planning_instruction = (
            f"USER REQUEST: {user_request}\n\n"
            f"CONTENT CONTEXT (Preview): {content_context[:500]}...\n\n"
            "Based on the above, please output ONLY the 'orchestration_plan' JSON object indicating which agents are required and the execution pattern."
        )
        
        plan_response = self.client.generate(
            system_prompt=self.system_prompt,
            user_content=planning_instruction,
            temperature=0.2
        )
        
        try:
            plan_data = self._parse_json(plan_response)
            orchestration_plan = plan_data.get("orchestration_plan", plan_data)
        except Exception as e:
            print(f"Error parsing orchestration plan: {e}")
            # Fallback: Assume Meeting Agent if failed
            orchestration_plan = {"agents_required": ["Meeting Intelligence Agent"], "execution_pattern": "sequential"}

        agents_required = orchestration_plan.get("agents_required", [])
        print(f"Orchestration Plan: Agents required: {agents_required}")

        agent_outputs = {}

        # Step 2: Execution
        # This is a simplified execution model (sequential/parallel handled simply here)
        if "Meeting Intelligence Agent" in agents_required or "Meeting Agent" in str(agents_required):
            print("Running Meeting Agent...")
            agent_outputs["meeting_agent"] = self.meeting_agent.analyze(content_context)
            
        if "Sales Intelligence Agent" in agents_required or "Sales Agent" in str(agents_required):
            print("Running Sales Agent...")
            agent_outputs["sales_agent"] = self.sales_agent.analyze(content_context)
            
        if "Workflow Automation Agent" in agents_required or "Workflow Agent" in str(agents_required):
            print("Running Workflow Agent...")
            agent_outputs["workflow_agent"] = self.workflow_agent.analyze(content_context)


        # Step 3: Synthesis
        # Now we provide the agent outputs back to the Orchestrator for the final JSON.
        synthesis_instruction = (
            f"USER REQUEST: {user_request}\n\n"
            f"ORCHESTRATION PLAN EXECUTED: {json.dumps(orchestration_plan)}\n\n"
            f"AGENT OUTPUTS: {json.dumps(agent_outputs)}\n\n"
            "Please generate the final response JSON. CRITICAL: Ensure the JSON includes:\n"
            "1. 'unified_response' with 'executive_summary', 'decisions' (list), 'action_items' (list of objects with 'task' and 'owner'), and 'next_steps' (list).\n"
            "2. 'metadata' with 'confidence_score' (0.0 to 1.0) and 'agents_utilized'.\n"
            "Include as much detail as possible from the agent outputs."
        )

        final_response = self.client.generate(
            system_prompt=self.system_prompt,
            user_content=synthesis_instruction,
            temperature=0.2
        )
        
        return self._parse_json(final_response)

    def _parse_json(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if "```json" in text:
                cleaned = text.split("```json")[1].split("```")[0]
                return json.loads(cleaned)
            elif "```" in text:
                 cleaned = text.split("```")[1].split("```")[0]
                 return json.loads(cleaned)
            return {"error": "Failed to parse JSON", "raw": text}
