from app.services.trend_news_service import get_news_for_trend

topics = [
    "iphone 18",
    "virat kohli shoes",
    "india vs south africa",
    "OpenAI Product Launches",
]

for topic in topics:

    print("\n" + "="*100)
    print("TOPIC:", topic)

    result = get_news_for_trend(topic)

    print("NEWSJACK SCORE:", result["newsjack_score"])
    print("ARTICLE COUNT:", result["article_count"])
    print("AVG RELEVANCE:", result["avg_relevance"])
    print("AVG IMPORTANCE:", result["avg_importance"])

    print("\nTOP 3 ARTICLES")

    for article in result["top_articles"][:3]:
        print("-", article["title"])
        print("  Relevance:", article["relevance_score"])
        print("  Importance:", article["importance_score"])