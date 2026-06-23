from app.services.trend_opportunity_service import get_live_trends
from app.services.news_opportunity_service import get_news_opportunities
from app.services.trend_news_service import get_trend_news
import json


def load_json(path):

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def get_opportunity_pool():

    opportunities = []

    opportunities.extend(
        load_json(
            "app/data/opportunities/events.json"
        )
    )

    opportunities.extend(
        load_json(
            "app/data/opportunities/sports.json"
        )
    )

    opportunities.extend(
        load_json(
            "app/data/opportunities/technology.json"
        )
    )

    opportunities.extend(
        load_json(
            "app/data/opportunities/seasonal.json"
        )
    )

    live_trends = get_live_trends()
    news = get_news_opportunities()

    opportunities.extend(
        live_trends
    )

    opportunities.extend(
        get_trend_news()
    )

    opportunities.extend(
        news
    )

    return opportunities