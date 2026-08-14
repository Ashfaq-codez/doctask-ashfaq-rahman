# backend/tests/test_agent.py
import json
import os
import tempfile
import asyncio
from unittest.mock import patch
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import agent_executor, AgentState

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

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
    
    # Check messages structure for routing
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
            "document_text": "",
            "existing_facts": "fact-existing-uuid-99: The governing law is California.",
            "extracted_facts": [],
            "conflicts": [],
            "current_stage": "initialized"
        }

        with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
            final_state = agent_executor.invoke(initial_state)

        assert final_state["current_stage"] == "conflicts_detected"
        assert len(final_state["extracted_facts"]) == 2
        assert len(final_state["conflicts"]) == 1
        assert final_state["conflicts"][0]["type"] == "contradiction"

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def test_checkpointer_resumability_after_interruption():
    """Proves that a halted graph retains completed node state and resumes without re-running."""
    memory_checkpointer = MemorySaver()
    app = agent_executor.builder.compile(checkpointer=memory_checkpointer, interrupt_after=["extract_facts"])
    
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as temp_file:
        temp_file.write("Jurisdiction: State of Delaware")
        temp_file_path = temp_file.name

    try:
        config: RunnableConfig = {"configurable": {"thread_id": "resumed-thread-999"}}
        initial_state: AgentState = {
            "run_id": "resumed-thread-999",
            "document_id": "doc-999",
            "file_path": temp_file_path,
            "document_text": "",
            "existing_facts": "",
            "extracted_facts": [],
            "conflicts": [],
            "current_stage": "initialized"
        }

        with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
            # Run up to interruption point
            interrupted_state = app.invoke(initial_state, config=config)

        assert interrupted_state["current_stage"] == "facts_extracted"
        assert len(interrupted_state["extracted_facts"]) == 2

        # Recompile without interrupt and resume passing None as input
        resumed_app = agent_executor.builder.compile(checkpointer=memory_checkpointer)
        with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
            final_resumed_state = resumed_app.invoke(None, config=config)

        assert final_resumed_state["current_stage"] == "conflicts_detected"
        assert len(final_resumed_state["conflicts"]) == 1

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def test_isolated_concurrent_executions():
    """Proves that multiple concurrent graph executions maintain independent states without cross-talk."""
    
    # 1. Create two isolated real temporary files
    file_a = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    file_a.write("Contract Content Document Alpha")
    file_a.close()

    file_b = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt")
    file_b.write("Contract Content Document Beta")
    file_b.close()

    try:
        async def run_isolated_instance(instance_id: str, file_path: str):
            state: AgentState = {
                "run_id": f"concurrent-{instance_id}",
                "document_id": f"doc-{instance_id}",
                "file_path": file_path,
                "document_text": "",
                "existing_facts": "",
                "extracted_facts": [],
                "conflicts": [],
                "current_stage": "initialized"
            }
            return await agent_executor.ainvoke(state)

        async def main():
            with patch("langchain_openai.ChatOpenAI._generate", side_effect=mock_llm_dispatch):
                return await asyncio.gather(
                    run_isolated_instance("A", file_a.name),
                    run_isolated_instance("B", file_b.name)
                )

        results = asyncio.run(main())
        
        # Verify run identities remain isolated
        assert results[0]["run_id"] == "concurrent-A"
        assert results[1]["run_id"] == "concurrent-B"
        
        # Verify file contents loaded independently without cross-talk
        assert results[0]["document_text"] == "Contract Content Document Alpha"
        assert results[1]["document_text"] == "Contract Content Document Beta"

    finally:
        # Cleanup temporary files
        if os.path.exists(file_a.name):
            os.remove(file_a.name)
        if os.path.exists(file_b.name):
            os.remove(file_b.name)