
import pytest
from unittest.mock import MagicMock
from src.core.llm_client import LLMClient
from src.agents.meeting_agent import MeetingAgent
from src.orchestrator.orchestrator import Orchestrator

def test_meeting_agent():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.generate.return_value = '{"meeting_type": "status_update", "output": "test"}'
    
    agent = MeetingAgent(mock_client)
    result = agent.analyze("transcript content")
    
    assert result["meeting_type"] == "status_update"
    mock_client.generate.assert_called_once()

def test_orchestrator_flow():
    mock_client = MagicMock(spec=LLMClient)
    
    # First call is Planning, Second is Synthesis (assuming execution happens)
    # Be careful with the Orchestrator logic calling agents which ALSO call client.generate
    
    # We need to setup the side_effect for multiple calls.
    # 1. Orchestrator Plan Request
    # 2. Meeting Agent Analysis Request
    # 3. Orchestrator Synthesis Request
    
    plan_json = '{"orchestration_plan": {"agents_required": ["Meeting Intelligence Agent"]}}'
    meeting_json = '{"actions": []}'
    synthesis_json = '{"unified_response": "done"}'
    
    mock_client.generate.side_effect = [plan_json, meeting_json, synthesis_json]
    
    orchestrator = Orchestrator(mock_client)
    result = orchestrator.process_request("Analyze this", "content")
    
    assert result["unified_response"] == "done"
    assert mock_client.generate.call_count == 3
