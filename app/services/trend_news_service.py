from serpapi import GoogleSearch
from dotenv import load_dotenv
import os

load_dotenv()


def get_trend_news():

    params = {
        "engine": "google_trends_trending_now",
        "geo": "IN",
        "api_key": os.getenv("SERPAPI_KEY")
    }

    search = GoogleSearch(params)

    results = search.get_dict()

    opportunities = []

    trends = results.get("trending_searches", [])

    for trend in trends[:5]:

        topic = trend.get("query")

        page_token = trend.get("news_page_token")

        if not page_token:
            continue

        news_results = get_news_for_trend(page_token)

        articles = news_results.get("news_results", [])

        for article in articles[:3]:

            opportunities.append({
                "topic": topic,
                "headline": article.get("title"),
                "source": article.get("source"),
                "url": article.get("link"),
                "category": "trend_news"
            })

    return opportunities

from serpapi import GoogleSearch


def get_news_for_trend(page_token):

    params = {
        "engine": "google_trends_news",
        "page_token": page_token,
        "api_key": os.getenv("SERPAPI_KEY")
    }

    search = GoogleSearch(params)

    results = search.get_dict()
    print("\nDEBUG RESPONSE:\n")
    print(results)

    return results