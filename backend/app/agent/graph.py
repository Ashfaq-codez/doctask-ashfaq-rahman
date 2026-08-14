import os
from typing import TypedDict, List, cast
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pypdf import PdfReader # type: ignore
from docx import Document as DocxDocument # type: ignore

# 1. State definition
class AgentState(TypedDict):
    run_id: str
    document_id: str
    file_path: str
    document_text: str
    existing_facts: str  
    extracted_facts: List[dict]
    conflicts: List[dict] 
    current_stage: str

# 2. Extraction & Conflict Schemas
class AtomicFact(BaseModel):
    fact_value: str = Field(description="The extracted atomic fact.")
    exact_quote: str = Field(description="The EXACT, VERBATIM quote from the source text that proves this fact.")
    page_number: int = Field(description="The page number where this fact is found (use 1 if unknown).", default=1)

class FactExtraction(BaseModel):
    facts: List[AtomicFact] = Field(description="A list of distinct, atomic facts extracted from the document.")

class DocumentAnomaly(BaseModel):
    topic: str = Field(description="Topic of the anomaly (e.g., Missing Signature)")
    reasoning: str = Field(description="Why this is an anomaly within the document")

class CrossDocumentContradiction(BaseModel):
    topic: str = Field(description="The topic of disagreement")
    existing_fact_id: str = Field(description="The EXACT ID of the existing fact that is contradicted")
    new_fact_text: str = Field(description="The EXACT text of the newly extracted fact that causes the contradiction")
    reasoning: str = Field(description="Why these two facts contradict each other logically")

class ConflictExtraction(BaseModel):
    anomalies: List[DocumentAnomaly] = Field(default_factory=list)
    contradictions: List[CrossDocumentContradiction] = Field(default_factory=list)

# 3. Robust Multi-Format Document Loader
def extract_text_from_file(file_path: str) -> str:
    if not os.path.exists(file_path):
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        reader = PdfReader(file_path)
        pages_text = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append(f"--- Page {idx+1} ---\n{text}")
        return "\n".join(pages_text)
        
    elif ext in [".docx", ".doc"]:
        doc = DocxDocument(file_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text])
        
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

# 4. Nodes
def load_document_node(state: AgentState):
    print(f"📖 [AGENT] Loading document from: {state['file_path']}")
    text = extract_text_from_file(state["file_path"])
    return {"document_text": text, "current_stage": "document_loaded"}

def extract_facts_node(state: AgentState):
    print(f"🧠 [AGENT] Extracting verifiable facts...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(FactExtraction)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert contract analyst. Extract key atomic facts. For every fact, you MUST extract the exact, verbatim substring from the document that proves it. Do not alter the quote."),
        ("human", "{document_text}")
    ])
    
    chain = prompt | structured_llm
    result = cast(FactExtraction, chain.invoke({"document_text": state["document_text"]}))
    
    rich_facts = [{"fact_value": f.fact_value, "exact_quote": f.exact_quote, "page_number": f.page_number} for f in result.facts]
    return {"extracted_facts": rich_facts, "current_stage": "facts_extracted"}

def detect_conflicts_node(state: AgentState):
    print(f"🕵️ [AGENT] Auditing facts against memory...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    structured_llm = llm.with_structured_output(ConflictExtraction)
    
    formatted_new_facts = "\n".join([f["fact_value"] for f in state["extracted_facts"]])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert compliance auditor. Review the newly extracted facts against existing memory.
        --- EXISTING VERIFIED FACTS (Format -> ID: Text) ---
        {existing_facts}
        """),
        ("human", f"--- NEW EXTRACTED FACTS ---\n{formatted_new_facts}")
    ])
    
    chain = prompt | structured_llm
    result = cast(ConflictExtraction, chain.invoke({
        "existing_facts": state.get("existing_facts", "No historic facts available.")
    }))
    
    unified_conflicts = []
    for anomaly in result.anomalies:
        unified_conflicts.append({"type": "anomaly", "topic": anomaly.topic, "reasoning": anomaly.reasoning})
    for contradiction in result.contradictions:
        unified_conflicts.append({
            "type": "contradiction", 
            "topic": contradiction.topic, 
            "existing_fact_id": contradiction.existing_fact_id, 
            "new_fact_text": contradiction.new_fact_text, 
            "reasoning": contradiction.reasoning
        })
        
    return {"conflicts": unified_conflicts, "current_stage": "conflicts_detected"}

# 5. Build Graph
builder = StateGraph(AgentState)
builder.add_node("load_document", load_document_node)
builder.add_node("extract_facts", extract_facts_node)
builder.add_node("detect_conflicts", detect_conflicts_node)

builder.set_entry_point("load_document")
builder.add_edge("load_document", "extract_facts")
builder.add_edge("extract_facts", "detect_conflicts")
builder.add_edge("detect_conflicts", END)

agent_executor = builder.compile()
agent_executor.builder = builder