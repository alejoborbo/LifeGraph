from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Document:
    id: Optional[int]
    title: str
    source: str
    source_id: str
    source_url: str
    created_at: Optional[str]
    fetched_at: str
    raw_text: str


@dataclass
class Project:
    id: Optional[int]
    name: str
    status: str = "active"  # idea | active | blocked | shipped | abandoned
    category: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
