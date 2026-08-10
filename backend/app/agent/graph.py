from typing import TypedDict, List, cast
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# 1. Update State to include conflicts
class AgentState(TypedDict):
    run_id: str
    document_id: str
    file_path: str
    document_text: str
    extracted_facts: List[str]
    conflicts: List[str]  # <-- NEW: Memory for the auditor
    current_stage: str

# 2. Schemas
class FactExtraction(BaseModel):
    facts: List[str] = Field(description="A list of distinct, atomic facts extracted from the provided document.")

class ConflictExtraction(BaseModel):
    conflicts: List[str] = Field(description="List of detected anomalies, contradictions, or missing standard clauses. Empty list if none.")

# 3. Nodes
def load_document_node(state: AgentState):
    print(f"📖 [AGENT] Loading document from: {state['file_path']}")
    with open(state["file_path"], "r", encoding="utf-8") as f:
        text = f.read()
    return {"document_text": text, "current_stage": "document_loaded"}

def extract_facts_node(state: AgentState):
    print(f"🧠 [AGENT] Analyzing text using OpenAI...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(FactExtraction)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert contract analyst. Extract the key atomic facts from the following document. Keep them concise and factual."),
        ("human", "{document_text}")
    ])
    
    chain = prompt | structured_llm
    result = cast(FactExtraction, chain.invoke({"document_text": state["document_text"]}))
    
    return {"extracted_facts": result.facts, "current_stage": "facts_extracted"}

def detect_conflicts_node(state: AgentState):
    """New Node: Audits the extracted facts for issues."""
    print(f"🕵️ [AGENT] Auditing facts for conflicts and anomalies...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(ConflictExtraction)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert compliance auditor. Review the following extracted facts. Identify any logical contradictions, unusual anomalies, or critical missing clauses (e.g., missing dates, missing signatures, missing payment terms). If everything looks perfectly standard and nothing is missing, return an empty list."),
        ("human", "Facts to review: {facts}")
    ])
    
    chain = prompt | structured_llm
    # We pass the output of the previous node into this one
    result = cast(ConflictExtraction, chain.invoke({"facts": state["extracted_facts"]}))
    
    return {"conflicts": result.conflicts, "current_stage": "conflicts_detected"}

# 4. Build the Graph
builder = StateGraph(AgentState)

builder.add_node("load_document", load_document_node)
builder.add_node("extract_facts", extract_facts_node)
builder.add_node("detect_conflicts", detect_conflicts_node)

builder.set_entry_point("load_document")
builder.add_edge("load_document", "extract_facts")
# Route facts to the auditor before ending
builder.add_edge("extract_facts", "detect_conflicts")
builder.add_edge("detect_conflicts", END)

agent_executor = builder.compile()