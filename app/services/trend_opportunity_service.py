from serpapi import GoogleSearch
from dotenv import load_dotenv
import os

load_dotenv()


def get_live_trends():

    params = {
        "engine": "google_trends_trending_now",
        "geo": "IN",
        "api_key": os.getenv("SERPAPI_KEY")
    }

    search = GoogleSearch(params)

    results = search.get_dict()

    opportunities = []

    allowed_categories = [
        "Sports",
        "Technology",
        "Entertainment",
        "Climate"
    ]

    for item in results.get("trending_searches", []):

        topic = item.get("query", "")

        categories = item.get("categories", [])

        if not categories:
            continue

        category = categories[0].get("name", "")

        if category not in allowed_categories:
            continue

        if len(topic) < 4:
            continue

        if topic.lower() in [
            "www",
            "play",
            "we"
        ]:
            continue

        opportunities.append({
            "topic": topic,
            "category": category,
            "source": "google_trends"
        })

    return opportunities