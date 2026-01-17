
import os
import shutil
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIMES = ["application/pdf", "image/png", "image/jpeg", "text/plain"]
UPLOAD_DIR = "uploads"

async def validate_file(file: UploadFile) -> str:
    """
    Validates file size and type.
    Returns the detected file type if valid, raises HTTPException otherwise.
    """
    # 1. Validate File Size
    # We need to read the file to check size properly if content-length is forged,
    # but for typical fast checks, we can try to rely on stream or read chunks.
    # However, to be safe and simple given the constraints, we read it.
    # CAUTION: This consumes memory. For very large files, stream processing is better.
    # Given MAX_FILE_SIZE is 10MB, reading into memory is acceptable.
    
    # Check size by seeking (blocking but fast for SpooledTempFile) or reading
    file.file.seek(0, 2)
    file_size = file.file.tell()
    await file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 10MB)")

    # 2. Validate File Type (Magic Numbers)
    try:
        # Check first 2048 bytes
        header = await file.read(2048)
        await file.seek(0)
        
        try:
            import magic
            # magic.from_buffer returns string like "PDF document, version 1.4"
            # magic.Magic(mime=True) returns "application/pdf"
            mime_type = magic.from_buffer(header, mime=True)
        except ImportError:
            # magic not installed or DLL missing
            mime_type = file.content_type or "application/octet-stream"
            
    except Exception as e:
        print(f"Magic validation warning: {e}")
        # Fallback to content-type header
        mime_type = file.content_type or "application/octet-stream"

    if mime_type not in ALLOWED_MIMES:
        # Fallback check: sometimes magic is too strict or fails
        filename = file.filename or ""
        ext = os.path.splitext(filename)[1].lower()
        allowed_exts = [".pdf", ".txt", ".png", ".jpg", ".jpeg"]
        
        # If magic failed to identify allowed mime, but extension looks okay,
        # we might want to be lenient OR strict. Security best practice: Strict.
        # But per existing code logic, we want to allow if extension matches known types 
        # as a fallback if magic was inconclusive (e.g. text files).
        
        is_valid_ext = ext in allowed_exts
        if not is_valid_ext:
             raise HTTPException(status_code=400, detail=f"Unsupported file type: {mime_type}")

    return mime_type

async def save_upload_file(file: UploadFile, directory: str = UPLOAD_DIR) -> str:
    """
    Saves an uploaded file to the specified directory with a unique name.
    Async version to prevent blocking code in route handlers.
    """
    os.makedirs(directory, exist_ok=True)
    
    filename = file.filename or "unknown"
    file_extension = os.path.splitext(filename)[1]
    if not file_extension:
        file_extension = ".bin" # Fallback
        
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(directory, unique_filename)
    
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await buffer.write(content)
        # Reset cursor for potential future reads (e.g. valid chains, though usually not needed after save)
        await file.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")
        
    return file_path

def resolve_file_path(file_path: str) -> str:
    """
    Resolves a file path to an absolute path and verifies it exists.
    Handles relative paths within UPLOAD_DIR.
    """
    if not file_path:
        raise FileNotFoundError("Empty file path")
        
    if os.path.isabs(file_path):
        abs_path = file_path
    else:
        # Assume relative to UPLOAD_DIR or root?
        # Existing code had confusion. Let's try UPLOAD_DIR first, then CWD.
        # But `file_path` in DB usually stores "uploads/filename" or just "uploads\filename"
        # if it was joined with os.path.join.
        abs_path = os.path.abspath(file_path)
    
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")
        
    return abs_path
