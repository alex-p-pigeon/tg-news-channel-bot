# models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

class ArticleStatus(Enum):
    NEW = "new"
    PROCESSING = "processing"
    RATED = "rated"
    TRANSLATED = "translated"
    POSTED = "posted"
    FAILED = "failed"

@dataclass
class Article:
    id: str
    title: str
    type: Optional[str]
    link: str
    date: datetime
    tags: Optional[str]
    summary: str
    media_content: Optional[str]
    content: Optional[str] = None  # New field for full content
    rhymable: Optional[str] = None  # New field for rhymable score
    rating: int = 0
    lurkable: int = 0
    category: Optional[str] = None
    lurk_translation: Optional[str] = None
    used: bool = False
    status: ArticleStatus = ArticleStatus.NEW
    created_at: datetime = None
    updated_at: datetime = None
    processing_time: int = 0
    api_cost: float = 0.0


@dataclass
class RatingResult:
    interest_score: int
    lurkable_score: int
    reasoning: str
    category: str