import io
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter
from sqlmodel import Session
from models import AuditLog

def log_audit(session: Session, user_id: int, action: str, details: str, ip_address: str | None = None, user_agent: str | None = None):
    log = AuditLog(
        user_id=user_id, 
        action=action, 
        details=details, 
        timestamp=datetime.utcnow(),
        ip_address=ip_address,
        user_agent=user_agent
    )
    session.add(log)
    session.commit()

def add_watermark(input_pdf_path: str, username: str) -> io.BytesIO:
    # Create the watermark
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("Helvetica", 10)
    can.setFillColorRGB(0.5, 0.5, 0.5, 0.5) # Grey, semi-transparent
    
    # Draw diagonally
    text = f"Downloaded by {username} on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Simple watermark at bottom
    can.drawString(50, 50, text)
    # can.rotate(45) # Rotation is complex with simple setup, keep simple for now
    
    can.save()

    # Move to the beginning of the StringIO buffer
    packet.seek(0)
    new_pdf = PdfReader(packet)
    
    # Read existing PDF
    existing_pdf = PdfReader(open(input_pdf_path, "rb"))
    output = PdfWriter()

    # Add the "watermark" (which is the new pdf) on the existing page
    for page in existing_pdf.pages:
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
    
    output_stream = io.BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    return output_stream
