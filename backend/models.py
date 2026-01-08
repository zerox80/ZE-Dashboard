from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime

# Join table for Contracts and Tags
class ContractTagLink(SQLModel, table=True):
    contract_id: Optional[int] = Field(default=None, foreign_key="contract.id", primary_key=True)
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.id", primary_key=True)

class Tag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    color: str = "#3b82f6" # Hex color
    
    contracts: List["Contract"] = Relationship(back_populates="tags", link_model=ContractTagLink)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="user") # 'admin' or 'user'
    totp_secret: Optional[str] = None # For 2FA
    
class Contract(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    file_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Financials
    value: float = Field(default=0.0)
    
    # Versioning
    version: int = Field(default=1)
    parent_id: Optional[int] = Field(default=None, foreign_key="contract.id")
    
    # Relationships
    tags: List[Tag] = Relationship(back_populates="contracts", link_model=ContractTagLink)
    
    # We could adding a children relationship for version history if needed
    # children: List["Contract"] = Relationship(sa_relationship_kwargs={"remote_side": "Contract.parent_id"})

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    action: str
    details: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
