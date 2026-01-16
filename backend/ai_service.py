"""
Mistral AI Service for Contract Analysis and Chat

Uses Mistral Large 3 for:
- PDF contract data extraction (auto-fill)
- Contract chatbot (Q&A)
"""

from mistralai import Mistral
import base64
import json
import os
import re

# Initialize client (lazy - only when API key is available)
_client = None

MODEL = "mistral-large-latest"  # Mistral Large 3


def get_client() -> Mistral:
    """Get or create Mistral client."""
    global _client
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set")
    if _client is None:
        _client = Mistral(api_key=api_key)
    return _client


async def analyze_contract_pdf(pdf_bytes: bytes) -> dict:
    """
    Analyze a PDF contract and extract structured data.
    Converts PDF to images first since Mistral requires image input.
    
    Returns:
        dict with keys: title, description, value, start_date, end_date, notice_period, tags
    """
    import fitz  # PyMuPDF
    
    client = get_client()

    
    # Convert PDF to images (first 3 pages max for cost efficiency)
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_base64 = []
    
    for page_num in range(min(3, len(pdf_doc))):
        page = pdf_doc[page_num]
        # Render at 150 DPI for good quality but not too large
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()
        images_base64.append(f"data:image/png;base64,{img_base64}")
    
    pdf_doc.close()
    
    # Build content with all page images
    content = []
    for img_b64 in images_base64:
        content.append({"type": "image_url", "image_url": img_b64})
    
    content.append({
        "type": "text",
        "text": """Analysiere diesen Vertrag sorgfältig und extrahiere die folgenden Informationen.
Antworte NUR mit einem validen JSON-Objekt, ohne zusätzlichen Text oder Erklärungen.

{
    "title": "Kurzer, prägnanter Vertragstitel",
    "description": "Kurze Zusammenfassung des Vertrags (max 200 Zeichen)",
    "value": 0.0,
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "notice_period": 30,
    "tags": ["Kategorie1", "Kategorie2"]
}

Regeln:
- value: Gesamtwert des Vertrags in Euro (als Zahl, nicht als String)
- start_date/end_date: Vertragslaufzeit im ISO-Format
- notice_period: Kündigungsfrist in Tagen (Standard: 30)
- tags: 1-3 passende Kategorien (z.B. "Software", "Lizenz", "Miete", "Service")
- Falls ein Wert nicht ermittelbar ist, verwende null"""
    })
    
    response = await client.chat.complete_async(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": content
            }
        ],
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    
    # Parse JSON response
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from response if wrapped in markdown
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {}
    
    # Ensure all expected keys exist
    defaults = {
        "title": None,
        "description": None,
        "value": None,
        "start_date": None,
        "end_date": None,
        "notice_period": 30,
        "tags": []
    }
    
    for key, default in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default
            
    return result


async def chat_about_contract(pdf_bytes: bytes, question: str) -> str:
    """
    Chat with AI about a specific contract.
    Converts PDF to images first since Mistral requires image input.
    
    Args:
        pdf_bytes: The PDF file content
        question: User's question about the contract
        
    Returns:
        AI-generated answer
    """
    import fitz  # PyMuPDF
    
    client = get_client()
    
    # Convert PDF to images (first 5 pages for chat to get more context)
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images_base64 = []
    
    for page_num in range(min(5, len(pdf_doc))):
        page = pdf_doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
        img_bytes = pix.tobytes("png")
        img_base64 = base64.b64encode(img_bytes).decode()
        images_base64.append(f"data:image/png;base64,{img_base64}")
    
    pdf_doc.close()
    
    # Build content with all page images + question
    content = []
    for img_b64 in images_base64:
        content.append({"type": "image_url", "image_url": img_b64})
    
    content.append({
        "type": "text",
        "text": f"Frage zum Vertrag: {question}"
    })
    
    response = await client.chat.complete_async(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """Du bist ein hilfreicher Vertragsassistent. 
Beantworte Fragen basierend auf dem bereitgestellten Vertragsdokument.
Sei präzise und verweise auf spezifische Abschnitte wenn möglich.
Wenn du etwas nicht im Dokument findest, sage das ehrlich."""
            },
            {
                "role": "user",
                "content": content
            }
        ]
    )
    
    return response.choices[0].message.content

