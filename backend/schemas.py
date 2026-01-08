from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
import re

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator('username')
    @classmethod
    def username_pattern(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only letters, numbers, underscores, and hyphens')
        return v

class TagRead(BaseModel):
    id: int
    name: str
    color: str

class ContractCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: datetime
    end_date: datetime
    value: float = Field(default=0.0, ge=0)
    tags: List[str] = []

class ContractUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    value: Optional[float] = Field(None, ge=0)
    tags: Optional[List[str]] = None

class ContractRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    # file_path removed - internal server path should not be exposed!
    uploaded_at: datetime
    value: float
    version: int
    tags: List[TagRead] = []

class AuditLogRead(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    details: str
    timestamp: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class OTPVerify(BaseModel):
    otp: str = Field(..., min_length=6, max_length=6)
