from app.services.opportunity_pool_service import get_opportunity_pool
from app.services.opportunity_scoring_service import rank_opportunities
from app.services.trend_news_service import get_news_for_trend


def print_divider(title=""):
    print("\n" + "=" * 100)

    if title:
        print(title)

    print("=" * 100)


def main():

    print_divider("NEWSJACK AI - OPPORTUNITY DISCOVERY ENGINE")

    # STEP 1
    print("\n[STEP 1] Discovering Opportunities...")

    opportunities = get_opportunity_pool()

    print(f"\nTotal Opportunities Found: {len(opportunities)}")

    # STEP 2
    print_divider("TOP OPPORTUNITIES")

    ranked = rank_opportunities(opportunities)

    for i, op in enumerate(ranked[:20], start=1):

        print(
            f"{i:02d}. "
            f"{op.get('topic', 'N/A')}\n"
            f"     Category : {op.get('category', 'N/A')}\n"
            f"     Source   : {op.get('source', 'N/A')}\n"
            f"     Score    : {op.get('score', 0)}\n"
        )

    # STEP 3
    top_topic = ranked[0]["topic"]

    print_divider("NEWS ENRICHMENT")

    print(f"\nFetching news for top trend:\n")
    print(top_topic)

    try:

        news_articles = get_news_for_trend(top_topic)

        print(f"\nArticles Retrieved: {len(news_articles)}")

        if news_articles:

            print_divider("TOP NEWS ARTICLES")

            for i, article in enumerate(news_articles[:5], start=1):

                print(f"\n[{i}] {article.get('title', 'No Title')}")

                print(
                    f"Source : {article.get('source', 'Unknown')}"
                )

                print(
                    f"Date   : {article.get('date', 'Unknown')}"
                )

                print(
                    f"Link   : {article.get('link', 'N/A')}"
                )

        else:
            print("\nNo articles found.")

    except Exception as e:

        print("\nNews Retrieval Failed")
        print(e)

    # STEP 4
    print_divider("NEWSJACKING INSIGHT")

    if ranked:

        trend = ranked[0]

        print(
            f"""
TREND:
{trend['topic']}

CATEGORY:
{trend['category']}

WHY IT MATTERS:
This topic is currently receiving significant public attention and
has potential for real-time marketing campaigns.

POSSIBLE BRAND ACTION:
Create timely content, social media posts, ads, memes,
or campaign messaging aligned with this trend.

NEWSJACK AI VALUE:
Automatically discovers emerging trends,
collects related news,
and helps marketers identify campaign opportunities.
"""
        )

    print_divider("PIPELINE COMPLETE")


if __name__ == "__main__":
    main()