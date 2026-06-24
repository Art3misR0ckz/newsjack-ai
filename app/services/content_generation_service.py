"""Generate channel-ready campaign content through OpenRouter or local fallback."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

from app.models import ContentPack
from app.services.llm_service import generate_json


def generate_content(
    brand_profile: Mapping[str, Any],
    news_match: Mapping[str, Any],
    campaign: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    brand = str(brand_profile.get("brand_name", "Our brand"))
    topic = str(news_match.get("topic") or news_match.get("selected_title") or "today's conversation")
    campaign_angle = str((campaign or {}).get("campaign_angle") or news_match.get("recommended_angle") or topic)
    hashtags = _hashtags(topic, brand_profile)
    fallback = {
        "linkedin_post": (
            f"{topic} is more than a headline—it is a useful signal for our industry.\n\n"
            f"At {brand}, our take is simple: {campaign_angle}. The strongest brands add value "
            "to the conversation before asking for attention.\n\nWhat are you seeing?"
        ),
        "twitter_post": f"{topic} is a signal, not just a headline. {campaign_angle}. What’s your take? {' '.join(hashtags[:2])}",
        "instagram_caption": (
            f"Trending now: {topic} ✨\n\n{campaign_angle}.\n\n"
            "We’re turning the conversation into something useful for our community."
        ),
        "blog_outline": (
            f"1. What happened around {topic}\n"
            f"2. Why it matters for {brand_profile.get('target_audience', 'the audience')}\n"
            f"3. {brand}'s practical point of view\n"
            "4. Three actions readers can take this week\n"
            "5. Soft CTA into the brand offer"
        ),
        "ad_copy": f"Headline: Turn {topic} into momentum.\nBody: {brand} helps you act on what matters now.",
        "email_campaign": (
            f"Subject: What {topic} means right now\n\n"
            f"Hi {{first_name}},\n\n{topic} is shaping the conversation. "
            f"Here is {brand}'s practical take: {campaign_angle}.\n\nCTA: {fallback_cta()}"
        ),
        "landing_page_headline": f"What {topic} means for {brand_profile.get('industry', 'your market')} — and what to do next",
        "marketing_hook": f"What {topic} means for people who care about {brand_profile.get('industry', 'this space')}.",
        "cta": "Join the conversation and share your perspective.",
        "hashtags": hashtags,
    }
    result = generate_json(
        system_prompt=(
            "You write timely, non-exploitative social content. Match the requested brand tone. "
            "Return strict JSON only. Keep twitter_post under 280 characters."
        ),
        user_prompt=(
            "Return keys linkedin_post, twitter_post, instagram_caption, blog_outline, ad_copy, "
            "email_campaign, landing_page_headline, marketing_hook, cta, hashtags.\n"
            f"Brand: {json.dumps(dict(brand_profile), default=str)}\n"
            f"Opportunity: {json.dumps(dict(news_match), default=str)}\n"
            f"Campaign: {json.dumps(dict(campaign or {}), default=str)}"
        ),
        fallback=fallback,
        cache_key=f"content:{brand}:{topic}:{campaign_angle}",
        temperature=0.5,
    )
    merged = {**fallback, **result}
    merged["twitter_post"] = str(merged["twitter_post"])[:280]
    pack = ContentPack.model_validate(merged).model_dump(mode="json")
    pack["tweet_x"] = pack["twitter_post"]
    return pack


def fallback_cta() -> str:
    return "Explore the full recommendation"


def _hashtags(topic: str, brand_profile: Mapping[str, Any]) -> list[str]:
    raw = [topic, str(brand_profile.get("industry", "")), str(brand_profile.get("brand_name", ""))]
    tags: list[str] = []
    for item in raw:
        tag = re.sub(r"[^A-Za-z0-9]", "", item.title())
        if tag and f"#{tag}" not in tags:
            tags.append(f"#{tag}")
    return tags[:5]
