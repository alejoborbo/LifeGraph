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
