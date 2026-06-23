import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_news_opportunities():

    api_key = os.getenv("NEWS_API_KEY")

    print("\nNEWS API KEY:")
    print(api_key)

    url = (
        f"https://newsapi.org/v2/top-headlines?"
        f"country=in&"
        f"pageSize=5&"
        f"apiKey={api_key}"
    )

    response = requests.get(url)

    print("\nSTATUS:")
    print(response.status_code)

    data = response.json()

    print("\nRAW NEWS RESPONSE:")
    print(data)

    opportunities = []

    for article in data.get("articles", []):

        opportunities.append({
            "topic": article.get("title", ""),
            "category": "news",
            "source": "news"
        })

    print("\nNEWS OPPORTUNITIES:")
    print(len(opportunities))

    return opportunities