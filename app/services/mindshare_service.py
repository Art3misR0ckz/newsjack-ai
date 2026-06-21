from pytrends.request import TrendReq
import re

pytrends = TrendReq()


def extract_keyword(title):

    title = title.lower()

    stopwords = {
        "this", "that", "with", "from", "into",
        "over", "under", "like", "will", "have",
        "has", "been", "their", "they", "about",
        "excellent", "start", "finish", "the",
        "and", "for", "are", "its", "than"
    }

    words = re.findall(
        r"[a-zA-Z]+",
        title
    )

    words = [
        word
        for word in words
        if word not in stopwords
        and len(word) > 3
    ]

    return " ".join(
        words[:3]
    )


def get_trend_score(keyword):

    try:

        pytrends.build_payload(
            [keyword],
            timeframe="today 3-m"
        )

        df = pytrends.interest_over_time()

        if df.empty:

            return {
                "keyword": keyword,
                "score": 0,
                "trend": "unknown"
            }

        avg_score = round(
            df[keyword].mean(),
            2
        )

        recent = (
            df[keyword]
            .tail(7)
            .mean()
        )

        older = (
            df[keyword]
            .head(7)
            .mean()
        )

        trend = (
            "rising"
            if recent > older
            else "falling"
        )

        return {
            "keyword": keyword,
            "score": avg_score,
            "trend": trend
        }

    except Exception as e:

        print(
            f"Mindshare Error ({keyword}):",
            e
        )

        return {
            "keyword": keyword,
            "score": 0,
            "trend": "unknown"
        }


def score_articles(articles):

    scored_articles = []

    for article in articles:

        title = article.get(
            "title",
            ""
        )

        keyword = extract_keyword(
            title
        )

        trend_data = get_trend_score(
            keyword
        )

        article[
            "trend_keyword"
        ] = keyword

        article[
            "mindshare_score"
        ] = trend_data[
            "score"
        ]

        article[
            "trend"
        ] = trend_data[
            "trend"
        ]

        scored_articles.append(
            article
        )

    scored_articles.sort(
        key=lambda x:
        x["mindshare_score"],
        reverse=True
    )

    return scored_articles