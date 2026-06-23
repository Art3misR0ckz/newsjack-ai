from serpapi import GoogleSearch
from dotenv import load_dotenv
from app.services.opportunity_discovery_service import discover_opportunities
import os

load_dotenv()


def get_google_trends():

    params = {
        "engine": "google_trends_trending_now",
        "geo": "IN",
        "api_key": os.getenv("SERPAPI_KEY")
    }

    search = GoogleSearch(params)

    results = search.get_dict()

    trends = []

    for item in results.get("trending_searches", []):

        trends.append({
            "topic": item.get("query"),
            "search_volume": item.get("search_volume", 0),
            "increase_percentage": item.get("increase_percentage", 0),
            "category": item.get("categories", [{}])[0].get("name", "Unknown")
        })

    return trends

def filter_trends(trends):

    allowed_categories = [
        #"Sports",
        "Technology",
        "Entertainment",
        "Climate"
    ]

    filtered = []

    for trend in trends:

        topic = trend["topic"]

        if trend["category"] not in allowed_categories:
            continue

        if len(topic) < 4:
            continue

        if topic.lower() in ["www", "play", "we"]:
            continue

        filtered.append(trend)

    return filtered

import requests

def get_news_headlines():

    api_key = os.getenv("NEWS_API_KEY")

    categories = [
        "technology",
        "business",
        "entertainment",
        "health"
    ]

    topics = []

    for category in categories:

        url = (
            "https://newsapi.org/v2/top-headlines?"
            f"country=us&category={category}"
            f"&apiKey={api_key}"
        )

        response = requests.get(url)

        data = response.json()

        for article in data.get("articles", []):

            topics.append({
                "topic": article["title"],
                "source": "news",
                "category": category
            })

    return topics

def get_raw_topics():

    trends = filter_trends(
        get_google_trends()
    )

    news = get_news_headlines()

    opportunities = []

    for trend in trends:

        opportunities.append({
            "topic": trend["topic"],
            "source": "google_trends",
            "score": trend["increase_percentage"]
        })

    for article in news:

        opportunities.append({
            "topic": article["topic"],
            "source": "news",
            "score": 50
        })

    return opportunities

def get_marketing_opportunities():

    raw_topics = get_raw_topics()

    simplified_topics = []

    for topic in raw_topics:

        simplified_topics.append(
            topic["topic"]
        )

    opportunities = discover_opportunities(
        simplified_topics[:50]
    )

    return opportunities