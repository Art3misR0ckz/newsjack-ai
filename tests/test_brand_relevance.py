"""Sample runner for brand relevance scoring."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.opportunity_scoring_service import rank_opportunities

logging.basicConfig(level=logging.INFO)


def main() -> None:
    brand_profile: Dict[str, Any] = {
        "brand_name": "ProteinX",
        "industry": "Fitness",
        "target_audience": "Gym Enthusiasts",
        "tone": "Motivational",
        "goals": "Increase awareness and engagement",
    }

    opportunities: List[Dict[str, Any]] = [
        {
            "topic": "Virat Kohli Shoes",
            "summary": "Virat Kohli launches One8 sports footwear...",
            "newsjack_score": 78,
        },
        {
            "topic": "FIFA World Cup",
            "summary": "Global football tournament coverage...",
            "newsjack_score": 82,
        },
        {
            "topic": "iPhone 18",
            "summary": "Apple's next device rumors and launch chatter...",
            "newsjack_score": 65,
        },
        {
            "topic": "OpenAI Product Launches",
            "summary": "New AI product announcements and launch updates...",
            "newsjack_score": 88,
        },
    ]

    ranked = rank_opportunities(opportunities, brand_profile)

    for item in ranked:
        print("Topic:", item.get("topic", ""))
        print("Relevance Score:", item.get("relevance_score", 0))
        print("Newsjack Score:", item.get("newsjack_score", 0))
        print("Final Score:", item.get("final_score", 0))
        print("Recommended Angle:", item.get("recommended_angle", "informative"))
        print()


if __name__ == "__main__":
    main()