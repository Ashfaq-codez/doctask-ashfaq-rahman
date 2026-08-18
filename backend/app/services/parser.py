import os
from typing import Optional

def extract_document_text(file_path: str) -> str:
    """
    Extracts text from PDF, DOCX, MD, and TXT files.
    Returns clean plain text with section breaks.
    """
    if not file_path or not os.path.exists(file_path):
        return "[Error: Document file not found on disk]"

    lower_path = file_path.lower()

    # 1. PDF Extraction
    if lower_path.endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"--- PAGE {i + 1} ---\n{text.strip()}")
            return "\n\n".join(pages) if pages else "[PDF contains scanned images with no extractable text layer]"
        except Exception as e:
            return f"[Error parsing PDF: {str(e)}]"

    # 2. DOCX Extraction
    elif lower_path.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            # Also extract text from tables inside the docx
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                    if row_text:
                        paragraphs.append(row_text)
                        
            return "\n\n".join(paragraphs) if paragraphs else "[Empty DOCX document]"
        except Exception as e:
            return f"[Error parsing DOCX: {str(e)}]"

    # 3. Plain Text & Markdown
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[Error reading file: {str(e)}]"