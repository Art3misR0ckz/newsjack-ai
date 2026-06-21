from services.brand_audit_service import scrape_brand_website
from services.brand_profile_service import generate_brand_profile
from services.news_service import fetch_news
from services.mindshare_service import score_articles
from services.relevance_service import select_best_news
from services.content_generation_service import generate_content


# =====================================
# STAGE 1 - BRAND AUDIT
# =====================================

data = scrape_brand_website(
    "https://www.thewholetruthfoods.com"
)

print("\n" + "=" * 60)
print("BRAND AUDIT")
print("=" * 60)

print(data)


# =====================================
# STAGE 2 - BRAND PROFILE
# =====================================

profile = generate_brand_profile(
    data
)

print("\n" + "=" * 60)
print("BRAND PROFILE")
print("=" * 60)

print(profile)


# =====================================
# STAGE 3 - NEWS FETCHING
# =====================================

articles = fetch_news(
    profile["keywords"]
)

print("\n" + "=" * 60)
print("NEWS ARTICLES")
print("=" * 60)

for article in articles:

    print("\n" + "-" * 50)

    print(
        article["title"]
    )

    print(
        article["description"]
    )


# =====================================
# STAGE 4 - MINDSHARE
# =====================================

articles = score_articles(
    articles
)

print("\n" + "=" * 60)
print("MINDSHARE SCORES")
print("=" * 60)

for article in articles:

    print("\n")
    print(
        "Keyword:",
        article["trend_keyword"]
    )

    print(
        "Score:",
        article["mindshare_score"]
    )

    print(
        "Trend:",
        article["trend"]
    )

print(
    article["title"]
)


# Only keep top 2

top_articles = articles[:2]


# =====================================
# STAGE 5 - RELEVANCE MATCHING
# =====================================

result = select_best_news(
    profile,
    top_articles
)

print("\n" + "=" * 60)
print("BEST NEWS MATCH")
print("=" * 60)

print(result)


# =====================================
# STAGE 6 - CONTENT GENERATION
# =====================================

content = generate_content(
    profile,
    result
)

print("\n" + "=" * 60)
print("GENERATED CONTENT")
print("=" * 60)

print(content)