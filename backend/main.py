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
from models import User, Contract, Tag, ContractTagLink, AuditLog, ContractPermission
from schemas import ContractRead, Token, UserCreate, ContractCreate, ContractUpdate, AuditLogRead, OTPVerify, TagRead, UserRead, UserUpdate, PermissionCreate, PermissionRead
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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Create initial admin user if not exists
    with next(get_session()) as session:
        user = session.exec(select(User).where(User.username == "admin")).first()
        admin_pw = os.getenv("ADMIN_PASSWORD")
        if not admin_pw:
            # Only generate random if not set AND user doesn't exist
            if not user:
                admin_pw = secrets.token_urlsafe(16)
                print(f"\n[SECURITY ALERT] ADMIN_PASSWORD not set. Generated temporary password: {admin_pw}\n")
        
        if admin_pw:
            hashed_pw = get_password_hash(admin_pw)
            if not user:
                # Create new
                admin_user = User(username="admin", hashed_password=hashed_pw, role="admin")
                session.add(admin_user)
                session.commit()
            else:
                # Update existing (Self-Healing)
                user.hashed_password = hashed_pw
                session.add(user)
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
        secure=False, # Force False for localhost
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    log_audit(session, user.id, "LOGIN", "User logged in", request.client.host, request.headers.get("user-agent"))
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/logout")
def logout(response: Response):
    """Clear the access_token cookie to log out"""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out"}


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
    # By default, ALL users see ALL contracts
    # Permissions are OPTIONAL restrictions, not required grants
    contracts = session.exec(select(Contract)).all()
    return contracts

@app.post("/contracts", response_model=ContractRead)
async def create_contract(
    request: Request,
    title: Annotated[str, Form()],
    start_date: Annotated[datetime, Form()],
    end_date: Annotated[datetime, Form()],
    value: Annotated[float, Form()] = 0.0,
    notice_period: Annotated[int, Form()] = 30,
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
        value=value,
        notice_period=notice_period
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
    
    log_audit(session, current_user.id, "UPLOAD", f"[CID:{contract.id}] Uploaded contract {contract.title}", request.client.host, request.headers.get("user-agent"))
    return contract

from fastapi.responses import StreamingResponse
@app.get("/contracts/{contract_id}/download")
def download_contract(contract_id: int, request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check permission
    if not check_contract_permission(current_user, contract_id, "read", session):
        raise HTTPException(status_code=403, detail="You don't have permission to access this contract")
        
    if not os.path.exists(contract.file_path):
        print(f"[ERROR] File not found on disk: {contract.file_path}")
        raise HTTPException(status_code=404, detail="File not found on server")

    # Standard download
    log_audit(session, current_user.id, "DOWNLOAD", f"[CID:{contract.id}] Downloaded {contract.title}", request.client.host, request.headers.get("user-agent"))
    
    # Determine basic mime types to avoid browser confusion
    # Determine basic mime types to avoid browser confusion
    import mimetypes
    media_type, _ = mimetypes.guess_type(contract.file_path)
    
    # Check explicitly for pdf to be sure
    _, ext = os.path.splitext(contract.file_path)
    if ext.lower() == ".pdf":
        media_type = "application/pdf"
        
    if not media_type:
        media_type = "application/octet-stream"
        
    # Ensure extension is in filename
    filename = f"{contract.title}{ext}"
    
    from fastapi.responses import FileResponse
    return FileResponse(contract.file_path, media_type=media_type, filename=filename)

@app.put("/contracts/{contract_id}", response_model=ContractRead)
async def update_contract(
    contract_id: int, 
    request: Request,
    title: Annotated[Optional[str], Form()] = None,
    description: Annotated[Optional[str], Form()] = None,
    start_date: Annotated[Optional[datetime], Form()] = None,
    end_date: Annotated[Optional[datetime], Form()] = None,
    value: Annotated[Optional[float], Form()] = None,
    notice_period: Annotated[Optional[int], Form()] = None,
    tags: Annotated[Optional[str], Form()] = None,
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check permission (need at least "write" level)
    if not check_contract_permission(current_user, contract_id, "write", session):
        raise HTTPException(status_code=403, detail="You don't have permission to edit this contract")
        
    changes = []
    
    # helper to check and update
    def check_and_update(field_name, new_val):
        if new_val is not None:
            old_val = getattr(contract, field_name)
            
            # Normalize dates for comparison (ignore time/timezone)
            if field_name in ['start_date', 'end_date']:
                # Compare only YYYY-MM-DD
                v1 = old_val.date() if isinstance(old_val, datetime) else old_val
                v2 = new_val.date() if isinstance(new_val, datetime) else new_val
                if v1 != v2:
                    changes.append(f"{field_name}: '{v1}' -> '{v2}'")
                    setattr(contract, field_name, new_val)
                return

            if old_val != new_val:
                changes.append(f"{field_name}: '{old_val}' -> '{new_val}'")
                setattr(contract, field_name, new_val)
    
    check_and_update("title", title)
    check_and_update("description", description)
    check_and_update("start_date", start_date)
    check_and_update("end_date", end_date)
    check_and_update("value", value)
    check_and_update("notice_period", notice_period)

    # Handle File Update
    if file:
        # Validate File Size (Max 10MB)
        MAX_FILE_SIZE = 10 * 1024 * 1024
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
             raise HTTPException(status_code=413, detail="File too large (Max 10MB)")

        # Validate File Type (Magic Numbers)
        mime = magic.Magic(mime=True)
        header = file.file.read(2048)
        file.file.seek(0)
        file_type = mime.from_buffer(header)
        
        ALLOWED_MIMES = ["application/pdf", "image/png", "image/jpeg", "text/plain"]
        if file_type not in ALLOWED_MIMES:
             raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")

        # Save new file
        UPLOAD_DIR = "uploads"
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        new_file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(new_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Remove old file
        if contract.file_path and os.path.exists(contract.file_path):
            try:
                os.remove(contract.file_path)
            except Exception as e:
                print(f"Error removing old file: {e}")
                
        contract.file_path = new_file_path
        changes.append("file: updated")
    
    # Handle Tags Update if provided
    if tags is not None:
        # Simple Logic: Clear and Re-add. 
        old_tags = [t.name for t in contract.tags]
        new_tags = [t.strip() for t in tags.split(",") if t.strip()]
        
        if set(old_tags) != set(new_tags):
            changes.append(f"tags: {old_tags} -> {new_tags}")
            contract.tags = []
            for t_name in new_tags:
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
            f"[CID:{contract_id}] Updated Contract. Changes: {diff_summary}", 
            request.client.host, 
            request.headers.get("user-agent")
        )
    
    return contract

@app.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: int, 
    current_user: User = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    contract = session.get(Contract, contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check permission (need "full" level to delete)
    if not check_contract_permission(current_user, contract_id, "full", session):
        raise HTTPException(status_code=403, detail="You don't have permission to delete this contract")
    
    # Delete file if exists
    if contract.file_path and os.path.exists(contract.file_path):
        try:
            os.remove(contract.file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")

    session.delete(contract)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.get("/tags", response_model=List[TagRead])
def get_tags(session: Session = Depends(get_session)):
    return session.exec(select(Tag)).all()

@app.get("/audit-logs", response_model=List[AuditLogRead])
def get_audit_logs(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    results = session.exec(select(AuditLog, User).join(User, isouter=True).order_by(AuditLog.timestamp.desc()).limit(100)).all()
    logs = []
    for log, user in results:
        l_dict = log.model_dump()
        l_dict["username"] = user.username if user else "Unknown"
        logs.append(l_dict)
    return logs

@app.get("/contracts/{contract_id}/audit", response_model=List[AuditLogRead])
def get_contract_audit_logs(
    contract_id: int, 
    current_user: User = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    pattern = f"%[CID:{contract_id}]%"
    results = session.exec(select(AuditLog, User).join(User, isouter=True).where(AuditLog.details.like(pattern)).order_by(AuditLog.timestamp.desc())).all()
    
    logs = []
    for log, user in results:
        l_dict = log.model_dump()
        l_dict["username"] = user.username if user else "Unknown"
        logs.append(l_dict)
    return logs


# ========================================
#           ADMIN PANEL ENDPOINTS
# ========================================

# Helper dependency for admin-only endpoints
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# Helper to check contract permission
def check_contract_permission(user: User, contract_id: int, required_level: str, session: Session) -> bool:
    """Check if user has required permission level for a contract.
    Admin users always have full access.
    If NO permission entry exists for the user/contract, DEFAULT IS FULL ACCESS.
    Permissions are OPTIONAL RESTRICTIONS, not required grants.
    required_level: 'read', 'write', or 'full'
    """
    if user.role == "admin":
        return True
    
    permission = session.exec(
        select(ContractPermission)
        .where(ContractPermission.user_id == user.id)
        .where(ContractPermission.contract_id == contract_id)
    ).first()
    
    # NO permission entry = DEFAULT FULL ACCESS (permissions are restrictions)
    if not permission:
        return True
    
    level_hierarchy = {"read": 1, "write": 2, "full": 3}
    return level_hierarchy.get(permission.permission_level, 0) >= level_hierarchy.get(required_level, 0)


# --- Current User Info Endpoint ---
@app.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "has_2fa": bool(current_user.totp_secret)
    }


# --- User Management Endpoints ---
@app.get("/admin/users", response_model=List[UserRead])
def list_users(
    admin: User = Depends(require_admin), 
    session: Session = Depends(get_session)
):
    """List all users (Admin only)"""
    users = session.exec(select(User)).all()
    result = []
    for u in users:
        user_dict = {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active if hasattr(u, 'is_active') else True,
            "created_at": u.created_at if hasattr(u, 'created_at') else datetime.utcnow(),
            "has_2fa": bool(u.totp_secret)
        }
        result.append(user_dict)
    return result


@app.post("/admin/users", response_model=UserRead)
def create_user(
    request: Request,
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Create a new user (Admin only)"""
    # Check if username exists
    existing = session.exec(select(User).where(User.username == user_data.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    new_user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        role="user",
        is_active=True,
        created_at=datetime.utcnow()
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    
    log_audit(session, admin.id, "CREATE_USER", f"Created user '{new_user.username}'", request.client.host, request.headers.get("user-agent"))
    
    return {
        "id": new_user.id,
        "username": new_user.username,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "created_at": new_user.created_at,
        "has_2fa": False
    }


@app.put("/admin/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    request: Request,
    user_data: UserUpdate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Update a user (Admin only)"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    changes = []
    
    if user_data.username is not None and user_data.username != user.username:
        # Check if new username exists
        existing = session.exec(select(User).where(User.username == user_data.username)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already exists")
        changes.append(f"username: '{user.username}' -> '{user_data.username}'")
        user.username = user_data.username
    
    if user_data.password is not None:
        user.hashed_password = get_password_hash(user_data.password)
        changes.append("password: updated")
    
    if user_data.role is not None and user_data.role != user.role:
        if user_data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
        changes.append(f"role: '{user.role}' -> '{user_data.role}'")
        user.role = user_data.role
    
    if user_data.is_active is not None and hasattr(user, 'is_active'):
        if user_data.is_active != user.is_active:
            changes.append(f"is_active: {user.is_active} -> {user_data.is_active}")
            user.is_active = user_data.is_active
    
    if changes:
        session.add(user)
        session.commit()
        session.refresh(user)
        log_audit(session, admin.id, "UPDATE_USER", f"Updated user '{user.username}': {'; '.join(changes)}", request.client.host, request.headers.get("user-agent"))
    
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active if hasattr(user, 'is_active') else True,
        "created_at": user.created_at if hasattr(user, 'created_at') else datetime.utcnow(),
        "has_2fa": bool(user.totp_secret)
    }


@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Deactivate a user (Admin only) - We don't actually delete to preserve audit trail"""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    # Deactivate instead of delete
    if hasattr(user, 'is_active'):
        user.is_active = False
        session.add(user)
        session.commit()
    
    log_audit(session, admin.id, "DEACTIVATE_USER", f"Deactivated user '{user.username}'", request.client.host, request.headers.get("user-agent"))
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Permission Management Endpoints ---
@app.get("/admin/permissions", response_model=List[PermissionRead])
def list_permissions(
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """List all contract permissions (Admin only)"""
    perms = session.exec(select(ContractPermission)).all()
    result = []
    for p in perms:
        user = session.get(User, p.user_id)
        contract = session.get(Contract, p.contract_id)
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "contract_id": p.contract_id,
            "permission_level": p.permission_level,
            "username": user.username if user else None,
            "contract_title": contract.title if contract else None
        })
    return result


@app.get("/admin/users/{user_id}/permissions", response_model=List[PermissionRead])
def get_user_permissions(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Get all permissions for a specific user (Admin only)"""
    perms = session.exec(select(ContractPermission).where(ContractPermission.user_id == user_id)).all()
    result = []
    for p in perms:
        contract = session.get(Contract, p.contract_id)
        user = session.get(User, p.user_id)
        result.append({
            "id": p.id,
            "user_id": p.user_id,
            "contract_id": p.contract_id,
            "permission_level": p.permission_level,
            "username": user.username if user else None,
            "contract_title": contract.title if contract else None
        })
    return result


@app.post("/admin/permissions", response_model=PermissionRead)
def create_permission(
    request: Request,
    perm_data: PermissionCreate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Create a new contract permission (Admin only)"""
    # Validate user and contract exist
    user = session.get(User, perm_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    contract = session.get(Contract, perm_data.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Check if permission already exists
    existing = session.exec(
        select(ContractPermission)
        .where(ContractPermission.user_id == perm_data.user_id)
        .where(ContractPermission.contract_id == perm_data.contract_id)
    ).first()
    
    if existing:
        # Update existing permission
        existing.permission_level = perm_data.permission_level
        session.add(existing)
        session.commit()
        session.refresh(existing)
        
        log_audit(session, admin.id, "UPDATE_PERMISSION", 
                  f"Updated permission for '{user.username}' on contract '{contract.title}' to '{perm_data.permission_level}'",
                  request.client.host, request.headers.get("user-agent"))
        
        return {
            "id": existing.id,
            "user_id": existing.user_id,
            "contract_id": existing.contract_id,
            "permission_level": existing.permission_level,
            "username": user.username,
            "contract_title": contract.title
        }
    
    new_perm = ContractPermission(
        user_id=perm_data.user_id,
        contract_id=perm_data.contract_id,
        permission_level=perm_data.permission_level
    )
    session.add(new_perm)
    session.commit()
    session.refresh(new_perm)
    
    log_audit(session, admin.id, "CREATE_PERMISSION", 
              f"Granted '{perm_data.permission_level}' permission to '{user.username}' for contract '{contract.title}'",
              request.client.host, request.headers.get("user-agent"))
    
    return {
        "id": new_perm.id,
        "user_id": new_perm.user_id,
        "contract_id": new_perm.contract_id,
        "permission_level": new_perm.permission_level,
        "username": user.username,
        "contract_title": contract.title
    }


@app.delete("/admin/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session)
):
    """Delete a contract permission (Admin only)"""
    perm = session.get(ContractPermission, permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    user = session.get(User, perm.user_id)
    contract = session.get(Contract, perm.contract_id)
    
    session.delete(perm)
    session.commit()
    
    log_audit(session, admin.id, "DELETE_PERMISSION", 
              f"Revoked permission from '{user.username if user else 'Unknown'}' for contract '{contract.title if contract else 'Unknown'}'",
              request.client.host, request.headers.get("user-agent"))
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

