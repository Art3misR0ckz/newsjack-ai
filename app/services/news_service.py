import os
import requests

from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def fetch_news(keywords):

    query = " OR ".join(keywords[:3])

    url = (
        "https://newsapi.org/v2/everything"
    )

    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }

    response = requests.get(
        url,
        params=params
    )

    data = response.json()

    articles = []

    for article in data.get(
        "articles",
        []
    ):

        articles.append(
            {
                "title":
                article["title"],

                "description":
                article["description"],

                "source":
                article["source"]["name"],

                "url":
                article["url"]
            }
        )

    return articles