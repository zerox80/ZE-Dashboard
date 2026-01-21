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
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Initialize client (lazy - only when API key is available)
_client = None

MODEL = "mistral-large-latest"  # Mistral Large 3

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Executor for CPU-bound tasks
_executor = ThreadPoolExecutor(max_workers=3)


def get_client() -> Mistral:
    """Get or create Mistral client."""
    global _client
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable not set")
    if _client is None:
        _client = Mistral(api_key=api_key)
    return _client


def _process_pdf_to_images(pdf_bytes: bytes, max_pages: int = 3) -> list[str]:
    """
    Blocking function to convert PDF bytes to base64 images.
    To be run in a thread pool.
    """
    import fitz  # PyMuPDF
    
    images_base64 = []
    
    # helper to safely close doc
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_doc:
            for page_num in range(min(max_pages, len(pdf_doc))):
                page = pdf_doc[page_num]
                # Render at 100 DPI (sufficient for OCR, saves tokens)
                pix = page.get_pixmap(matrix=fitz.Matrix(100/72, 100/72))
                # Use JPEG to greatly reduce data size
                img_bytes = pix.tobytes("jpeg")
                img_base64 = base64.b64encode(img_bytes).decode()
                images_base64.append(f"data:image/jpeg;base64,{img_base64}")
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        raise
        
    return images_base64


async def analyze_contract_pdf(pdf_bytes: bytes) -> dict:
    """
    Analyze a PDF contract and extract structured data.
    Converts PDF to images first since Mistral requires image input.
    
    Returns:
        dict with keys: title, description, value, start_date, end_date, notice_period, tags
    """
    client = get_client()

    # Offload blocking PDF processing to thread pool
    loop = asyncio.get_running_loop()
    images_base64 = await loop.run_in_executor(
        _executor, 
        _process_pdf_to_images, 
        pdf_bytes, 
        3  # max pages
    )
    
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
    
    response_content = response.choices[0].message.content
    
    # helper for mypy/safety
    if not isinstance(response_content, str):
        response_content = "" if response_content is None else str(response_content)
    
    # Parse JSON response
    try:
        result = json.loads(response_content)
    except json.JSONDecodeError:
        # Try to extract JSON from response if wrapped in markdown
        json_match = re.search(r'\{[\s\S]*\}', response_content)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                result = {}
        else:
            result = {}
    
    # Ensure all expected keys exist
    defaults: dict = {
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
    client = get_client()
    
    # Offload blocking PDF processing to thread pool (use 5 pages for chat)
    loop = asyncio.get_running_loop()
    images_base64 = await loop.run_in_executor(
        _executor, 
        _process_pdf_to_images, 
        pdf_bytes, 
        15  # max pages
    )
    
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
    
    response_content = response.choices[0].message.content
    # Safety check for mypy - content can be str | None | list
    if not isinstance(response_content, str):
        response_content = "" if response_content is None else str(response_content)
    return response_content

