"""Validated domain schemas shared by the API, services, and UI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class BrandProfile(DomainModel):
    id: str | None = None
    brand_name: str = Field(min_length=1, max_length=120)
    industry: str = Field(default="General", max_length=120)
    target_audience: str = Field(default="General consumers", max_length=500)
    tone: str = Field(default="Professional", max_length=100)
    goals: str = Field(default="Increase awareness", max_length=500)
    keywords: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    website: str | None = None
    brand_summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("keywords", "competitors", "products", mode="before")
    @classmethod
    def split_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(item).strip() for item in value if str(item).strip()]


class Trend(DomainModel):
    topic: str
    title: str | None = None
    category: str = "general"
    source: str = "fallback"
    search_volume: int = 0
    growth_rate: int = 0
    increase_percentage: int = 0
    trend_strength: int = Field(default=50, ge=0, le=100)
    trend_score: int = Field(default=50, ge=0, le=100)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Article(DomainModel):
    headline: str
    description: str = ""
    content: str = ""
    source: str = "Unknown"
    published_date: str | None = None
    image: str = ""
    url: str = ""
    relevance_score: int = Field(default=0, ge=0, le=100)
    importance_score: int = Field(default=0, ge=0, le=100)
    recency_score: int = Field(default=0, ge=0, le=100)
    credibility_score: int = Field(default=0, ge=0, le=100)


class Campaign(DomainModel):
    campaign_angle: str
    why_it_matters: str
    confidence: int = Field(ge=0, le=100)
    recommended_channels: list[str] = Field(default_factory=list)
    marketing_insight: str = ""
    suggested_content: list[str] = Field(default_factory=list)


class ContentPack(DomainModel):
    linkedin_post: str
    twitter_post: str
    instagram_caption: str
    blog_outline: str = ""
    ad_copy: str = ""
    email_campaign: str = ""
    landing_page_headline: str = ""
    marketing_hook: str
    cta: str
    hashtags: list[str] = Field(default_factory=list)


class Opportunity(DomainModel):
    topic: str
    category: str = "general"
    source: str = "unknown"
    summary: str = ""
    articles: list[Article] = Field(default_factory=list)
    trend_strength: int = Field(default=0, ge=0, le=100)
    news_volume: int = 0
    source_diversity: int = 0
    brand_relevance: int = Field(default=0, ge=0, le=100)
    audience_overlap: int = Field(default=0, ge=0, le=100)
    newsjack_potential: int = Field(default=0, ge=0, le=100)
    final_score: int = Field(default=0, ge=0, le=100)
    opportunity_score: int = Field(default=0, ge=0, le=100)
    trend_score: int = Field(default=0, ge=0, le=100)
    freshness_score: int = Field(default=0, ge=0, le=100)
    competitor_activity_score: int = Field(default=0, ge=0, le=100)
    youtube_buzz_score: int = Field(default=0, ge=0, le=100)
    content_volume_score: int = Field(default=0, ge=0, le=100)
    latest_news: list[Article] = Field(default_factory=list)
    youtube_signals: list[dict[str, Any]] = Field(default_factory=list)
    competitor_signals: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""
    recommended_angle: str = "informative"
    campaign: Campaign | None = None
    content: ContentPack | None = None
