def score_opportunity(opportunity):

    score = 0

    source = opportunity.get("source", "")
    category = opportunity.get("category", "")

    if source == "google_trends":
        score += 50

    elif source == "google_trends_news":
        score += 40

    elif source == "technology":
        score += 30

    elif source == "sports":
        score += 25

    elif source == "seasonal":
        score += 20

    elif source == "event":
        score += 20

    if category == "technology":
        score += 20

    elif category == "sports":
        score += 15

    elif category == "seasonal":
        score += 10

    elif category == "health":
        score += 10

    return score


def rank_opportunities(opportunities):

    ranked = []

    for opportunity in opportunities:

        opportunity["score"] = score_opportunity(
            opportunity
        )

        ranked.append(opportunity)

    ranked.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return ranked