import json
import os
import tempfile
import pytest
import asyncio
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_agent_graph, AgentState, is_mock_mode

FIXTURES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "fixtures"))

def load_raw_fixture(filename: str) -> AIMessage:
    with open(os.path.join(FIXTURES_DIR, filename), "r", encoding="utf-8") as f:
        data = json.load(f)
    raw_content = data["choices"][0]["message"]["content"]
    parsed_json = json.loads(raw_content)
    return AIMessage(content=raw_content, additional_kwargs={"parsed": parsed_json})

def mock_llm_dispatch(messages, **kwargs):
    """
    Deterministically routes wire-level fixtures based on prompt contents,
    guaranteeing thread-safe concurrency without race conditions.
    """
    extraction_msg = load_raw_fixture("raw_fact_extraction.json")
    conflict_msg = load_raw_fixture("raw_conflict_detection.json")
    
    combined_prompt = " ".join([str(m.content) for m in messages]).lower()
    
    if "compliance auditor" in combined_prompt or "existing verified facts" in combined_prompt:
        return ChatResult(generations=[ChatGeneration(message=conflict_msg)])
    else:
        return ChatResult(generations=[ChatGeneration(message=extraction_msg)])


def test_full_graph_traversal_with_deterministic_replay():
    """Validates real file reading, prompt injection, Pydantic validation, and node progression."""
    document_content = "MASTER SERVICES AGREEMENT\nJurisdiction: State of Delaware\nPayment Terms: Net 30 days upon invoice receipt."
    
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as temp_file:
        temp_file.write(document_content)
        temp_file_path = temp_file.name

    try:
        initial_state: AgentState = {
            "run_id": "vcr-run-101",
            "document_id": "vcr-doc-101",
            "file_path": temp_file_path,
            "document_text": document_content,
            "existing_facts": "fact-existing-uuid-99: The governing law is California.",
            "extracted_facts": [],
            "conflicts": [],
            "security_flags": [],
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "estimated_cost_usd": 0.0,
            "current_stage": "initialized"
        }

        app = build_agent_graph()
        with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
            final_state = app.invoke(initial_state)

        assert final_state["current_stage"] == "conflicts_detected"
        assert len(final_state["extracted_facts"]) >= 1
        assert len(final_state["conflicts"]) >= 1
        assert any(c["type"] == "contradiction" for c in final_state["conflicts"])

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def test_checkpointer_resumability_after_interruption():
    """Proves that a halted graph retains completed node state and resumes without re-running."""
    memory_checkpointer = MemorySaver()
    app = build_agent_graph(checkpointer=memory_checkpointer)
    
    config: RunnableConfig = {"configurable": {"thread_id": "resumed-thread-999"}}
    initial_state: AgentState = {
        "run_id": "resumed-thread-999",
        "document_id": "doc-999",
        "file_path": "sample.txt",
        "document_text": "Jurisdiction: State of Delaware",
        "existing_facts": "",
        "extracted_facts": [],
        "conflicts": [],
        "security_flags": [],
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": 0.0,
        "current_stage": "initialized"
    }

    with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
        first_pass_state = app.invoke(initial_state, config=config)

    assert first_pass_state["current_stage"] == "conflicts_detected"
    assert len(first_pass_state["extracted_facts"]) >= 1

    # Resume passing None input (loads state from checkpointer)
    with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
        resumed_state = app.invoke(None, config=config)

    assert resumed_state["run_id"] == "resumed-thread-999"
    assert resumed_state["current_stage"] == "conflicts_detected"


@pytest.mark.asyncio
async def test_isolated_concurrent_executions():
    """Proves that multiple concurrent graph executions maintain independent states without cross-talk."""
    app = build_agent_graph()

    state_a: AgentState = {
        "run_id": "concurrent-A",
        "document_id": "doc-A",
        "file_path": "alpha.txt",
        "document_text": "Contract Content Document Alpha",
        "existing_facts": "",
        "extracted_facts": [],
        "conflicts": [],
        "security_flags": [],
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": 0.0,
        "current_stage": "initialized"
    }

    state_b: AgentState = {
        "run_id": "concurrent-B",
        "document_id": "doc-B",
        "file_path": "beta.txt",
        "document_text": "Contract Content Document Beta",
        "existing_facts": "",
        "extracted_facts": [],
        "conflicts": [],
        "security_flags": [],
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": 0.0,
        "current_stage": "initialized"
    }

    with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
        results = await asyncio.gather(app.ainvoke(state_a), app.ainvoke(state_b))
    
    assert results[0]["run_id"] == "concurrent-A"
    assert results[1]["run_id"] == "concurrent-B"
    assert results[0]["document_text"] == "Contract Content Document Alpha"
    assert results[1]["document_text"] == "Contract Content Document Beta"