from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Response, Request, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from typing import List, Annotated, Optional
import shutil
import os
import uuid
import pyotp
import qrcode
import io
from datetime import datetime, timedelta

import secrets
import magic

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import create_db_and_tables, get_session
from models import User, Contract, Tag, ContractTagLink, AuditLog
from schemas import ContractRead, Token, UserCreate, ContractCreate, ContractUpdate, AuditLogRead, OTPVerify, TagRead
from auth import verify_password, create_access_token, get_password_hash, ACCESS_TOKEN_EXPIRE_MINUTES
from security_utils import log_audit, add_watermark

# Configuration
PRODUCTION_MODE = os.getenv("PRODUCTION", "false").lower() == "true"
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80", "http://127.0.0.1", "http://127.0.0.1:80"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Create initial admin user if not exists
    with next(get_session()) as session:
        user = session.exec(select(User).where(User.username == "admin")).first()
        if not user:
            admin_pw = os.getenv("ADMIN_PASSWORD")
            if not admin_pw:
                admin_pw = secrets.token_urlsafe(16)
                print(f"\n[SECURITY ALERT] ADMIN_PASSWORD not set. Generated temporary password: {admin_pw}\n")
            
            hashed_pw = get_password_hash(admin_pw)
            admin_user = User(username="admin", hashed_password=hashed_pw, role="admin")
            session.add(admin_user)
            session.commit()
            
        # Create some default tags
        if not session.exec(select(Tag)).first():
            tags = [
                Tag(name="Software", color="#3b82f6"),
                Tag(name="Hardware", color="#ef4444"),
                Tag(name="Legal", color="#10b981"),
                Tag(name="HR", color="#f59e0b")
            ]
            for t in tags: session.add(t)
            session.commit()

async def get_current_user(
    token: Annotated[Optional[str], Depends(oauth2_scheme)] = None, 
    access_token: Annotated[Optional[str], Cookie()] = None,
    session: Session = Depends(get_session)
):
    # Prioritize Cookie, fall back to Header (for API testing tools if needed, but we can enforce Cookie)
    final_token = access_token if access_token else token
    
    if not final_token:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    from jose import JWTError, jwt
    from auth import SECRET_KEY, ALGORITHM
    from schemas import TokenData
    
    try:
        payload = jwt.decode(final_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        token_data = TokenData(username=username)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        
    user = session.exec(select(User).where(User.username == token_data.username)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

@app.post("/token")
@limiter.limit(RATE_LIMIT_LOGIN)
async def login_for_access_token(
    response: Response,
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    session: Session = Depends(get_session)
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Check 2FA if enabled
    if user.totp_secret:
        # Require OTP
        otp_code = form_data.client_secret # We can reuse client_secret field or expect a custom header/field
        # NOTE: OAuth2PasswordRequestForm has client_secret but it is optional.
        # Alternatively, we can parse it from body if we extend the form or use a separate param.
        # For strict compliance, let's assume the frontend sends it or we fail.
        
        # Checking if 'otp' is passed in the request body (FastAPI form parsing workaround)
        # Since OAuth2PasswordRequestForm is strict, we might need a custom dependency or use client_uuid/secret.
        # Let's check if the user provided the OTP in the 'client_secret' field for now, 
        # OR require a separate 2FA verify step (2-step login).
        
        # STRATEGY: 2-Step Login is safer but complex to refactor frontend entirely.
        # Approach: User validation passed. If 2FA enabled, return a temporary "PRE-AUTH" token or 403 with "2FA Required".
        # SIMPLIFIED SECURE APPROACH: Use 'client_secret' field of the form for OTP code.
        
        otp = form_data.client_secret
        if not otp:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="2FA Required",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(otp, valid_window=1):
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA Code",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # Add role to token claims
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    
    # Set HttpOnly Cookie (secure=True when PRODUCTION=true)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=PRODUCTION_MODE,
        samesite="lax" if not PRODUCTION_MODE else "strict",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    log_audit(session, user.id, "LOGIN", "User logged in", request.client.host, request.headers.get("user-agent"))
    return {"access_token": access_token, "token_type": "bearer"}

# --- 2FA Endpoints ---
@app.post("/2fa/setup")
def setup_2fa(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    secret = pyotp.random_base32()
    current_user.totp_secret = secret
    session.add(current_user)
    session.commit()
    
    # Generate QR Code
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.username, issuer_name="ZE-Dashboard")
    
    # Create QR image
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    
    return Response(content=buf.getvalue(), media_type="image/png")

@app.post("/2fa/verify")
def verify_2fa(otp_data: OTPVerify, current_user: User = Depends(get_current_user)):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not setup")
        
    totp = pyotp.TOTP(current_user.totp_secret)
    if not totp.verify(otp_data.otp):
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    return {"message": "Verified"}

# --- Contract Endpoints ---

@app.get("/contracts", response_model=List[ContractRead])
def read_contracts(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    contracts = session.exec(select(Contract)).all()
    # Manual populate tags if needed or rely on SQLModel relationship
    return contracts

@app.post("/contracts", response_model=ContractRead)
async def create_contract(
    request: Request,
    title: Annotated[str, Form()],
    start_date: Annotated[datetime, Form()],
    end_date: Annotated[datetime, Form()],
    value: Annotated[float, Form()] = 0.0,
    file: UploadFile = File(...),
    description: Annotated[str, Form()] = None,
    tags: Annotated[str, Form()] = "",
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # 1. Validate File Size (Max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (Max 10MB)")

    # 2. Validate File Type (Magic Numbers)
    mime = magic.Magic(mime=True)
    header = file.file.read(2048)
    file.file.seek(0)
    file_type = mime.from_buffer(header)
    
    ALLOWED_MIMES = ["application/pdf", "image/png", "image/jpeg", "text/plain"]
    if file_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")

    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # 3. Secure Filename (Discard user filename)
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension.lower() not in [".pdf", ".png", ".jpg", ".jpeg", ".txt"]:
         # Double check extension matches mime type roughly
         raise HTTPException(status_code=400, detail="Invalid file extension")

    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    contract = Contract(
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
        file_path=file_path,
        value=value
    )
    
    # Handle Tags
    if tags:
        tag_list = tags.split(",")
        for t_name in tag_list:
            t_name = t_name.strip()
            if not t_name: continue
            # Find or create tag
            tag = session.exec(select(Tag).where(Tag.name == t_name)).first()
            if not tag:
                # Assign random color or loop
                tag = Tag(name=t_name)
                session.add(tag)
                session.commit()
                session.refresh(tag)
            contract.tags.append(tag)
            
    session.add(contract)
    session.commit()
    session.refresh(contract)
    
    log_audit(session, current_user.id, "UPLOAD", f"Uploaded contract {contract.title} ({contract.id})", request.client.host, request.headers.get("user-agent"))
    return contract

from fastapi.responses import StreamingResponse
@app.get("/contracts/{contract_id}/download")
def download_contract(contract_id: int, request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
        
    # Check mime type (simple check via ext)
    if contract.file_path.lower().endswith(".pdf"):
        try:
            watermarked_pdf = add_watermark(contract.file_path, current_user.username)
            log_audit(session, current_user.id, "DOWNLOAD", f"Downloaded (Watermarked) {contract.title}", request.client.host, request.headers.get("user-agent"))
            return StreamingResponse(
                watermarked_pdf, 
                media_type="application/pdf", 
                headers={"Content-Disposition": f"attachment; filename={contract.title}.pdf"}
            )
        except Exception:
            # Fallback if PDF processing fails
             pass

    # Standard download
    log_audit(session, current_user.id, "DOWNLOAD", f"Downloaded {contract.title}", request.client.host, request.headers.get("user-agent"))
    from fastapi.responses import FileResponse
    return FileResponse(contract.file_path, filename=os.path.basename(contract.file_path))

@app.put("/contracts/{contract_id}", response_model=ContractRead)
async def update_contract(
    contract_id: int, 
    update_data: ContractUpdate, 
    request: Request,
    current_user: User = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
        
    changes = []
    
    # helper to check and update
    def check_and_update(field_name, new_val):
        if new_val is not None:
            old_val = getattr(contract, field_name)
            if old_val != new_val:
                changes.append(f"{field_name}: '{old_val}' -> '{new_val}'")
                setattr(contract, field_name, new_val)
    
    check_and_update("title", update_data.title)
    check_and_update("description", update_data.description)
    check_and_update("start_date", update_data.start_date)
    check_and_update("end_date", update_data.end_date)
    check_and_update("value", update_data.value)
    
    # Handle Tags Update if provided
    if update_data.tags is not None:
        # Simple Logic: Clear and Re-add. 
        # For audit, we could list added/removed, but "Tags updated" is often enough.
        old_tags = [t.name for t in contract.tags]
        new_tags = update_data.tags
        
        if set(old_tags) != set(new_tags):
            changes.append(f"tags: {old_tags} -> {new_tags}")
            contract.tags = []
            for t_name in new_tags:
                t_name = t_name.strip()
                if not t_name: continue
                tag = session.exec(select(Tag).where(Tag.name == t_name)).first()
                if not tag:
                    tag = Tag(name=t_name)
                    session.add(tag)
                    session.commit()
                    session.refresh(tag)
                contract.tags.append(tag)
    
    if changes:
        session.add(contract)
        session.commit()
        session.refresh(contract)
        
        diff_summary = "; ".join(changes)
        log_audit(
            session, 
            current_user.id, 
            "UPDATE_CONTRACT", 
            f"Updated Contract {contract_id}. Changes: {diff_summary}", 
            request.client.host, 
            request.headers.get("user-agent")
        )
    
    return contract

@app.get("/tags", response_model=List[TagRead])
def get_tags(session: Session = Depends(get_session)):
    return session.exec(select(Tag)).all()

@app.get("/audit-logs", response_model=List[AuditLogRead])
def get_audit_logs(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return session.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100)).all()
