import streamlit as st
import sys
import os
import json
import re

sys.path.append(
    os.path.abspath(
        os.path.dirname(__file__)
    )
)

from services.brand_audit_service import scrape_brand_website
from services.brand_profile_service import generate_brand_profile
from services.news_service import fetch_news
from services.mindshare_service import score_articles
from services.relevance_service import select_best_news
from services.content_generation_service import generate_content


# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="NewsJack AI",
    page_icon="📰",
    layout="wide"
)

st.title("📰 NewsJack AI")
st.caption("Mindshare-Driven Newsjacking Engine")

st.divider()

brand_url = st.text_input(
    "Enter Brand Website URL",
    placeholder="https://www.thewholetruthfoods.com"
)

# =====================================================
# PIPELINE
# =====================================================

if st.button("Analyze Brand"):

    if not brand_url:
        st.error("Please enter a valid URL.")
        st.stop()

    try:

        with st.spinner("Running NewsJack Pipeline..."):

            # =================================
            # STAGE 1
            # =================================

            audit_data = scrape_brand_website(
                brand_url
            )

            if not audit_data:
                st.error(
                    "Could not scrape website."
                )
                st.stop()

            # =================================
            # STAGE 2
            # =================================

            profile = generate_brand_profile(
                audit_data
            )

            if isinstance(profile, str):

                try:
                    profile = re.sub(
                        r"```json|```",
                        "",
                        profile
                    ).strip()

                    profile = json.loads(
                        profile
                    )

                except Exception:
                    st.error(
                        "Brand profile JSON parsing failed."
                    )
                    st.write(profile)
                    st.stop()

            # =================================
            # STAGE 3
            # =================================

            articles = fetch_news(
                profile.get(
                    "keywords",
                    []
                )
            )

            if not articles:
                st.error(
                    "No news articles found."
                )
                st.stop()

            # =================================
            # STAGE 4
            # =================================

            articles = score_articles(
                articles
            )

            top_articles = articles[:2]

            # =================================
            # STAGE 5
            # =================================

            result = select_best_news(
                profile,
                top_articles
            )

            if isinstance(result, str):

                try:
                    result = re.sub(
                        r"```json|```",
                        "",
                        result
                    ).strip()

                    result = json.loads(
                        result
                    )

                except Exception:
                    st.error(
                        "Opportunity JSON parsing failed."
                    )
                    st.write(result)
                    st.stop()

            # =================================
            # STAGE 6
            # =================================

            content = generate_content(
                profile,
                result
            )

            if isinstance(content, str):

                try:
                    content = re.sub(
                        r"```json|```",
                        "",
                        content
                    ).strip()

                    content = json.loads(
                        content
                    )

                except Exception:
                    st.error(
                        "Content JSON parsing failed."
                    )
                    st.write(content)
                    st.stop()

    except Exception as e:

        st.error(
            f"Pipeline Error: {e}"
        )

        st.stop()

    # =====================================================
    # OUTPUT
    # =====================================================

    st.success(
        "Analysis Complete"
    )

    st.divider()

    # =====================================================
    # BRAND PROFILE
    # =====================================================

    st.header(
        "🏢 Brand Profile"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            "**Brand Name**"
        )

        st.write(
            profile.get(
                "brand_name",
                "N/A"
            )
        )

        st.write(
            "**Category**"
        )

        st.write(
            profile.get(
                "category",
                "N/A"
            )
        )

        st.write(
            "**Tone**"
        )

        st.write(
            profile.get(
                "tone",
                "N/A"
            )
        )

    with col2:

        st.write(
            "**Target Audience**"
        )

        st.write(
            profile.get(
                "target_audience",
                []
            )
        )

        st.write(
            "**Keywords**"
        )

        st.write(
            profile.get(
                "keywords",
                []
            )
        )

    st.write(
        "**Brand Summary**"
    )

    st.info(
        profile.get(
            "brand_summary",
            ""
        )
    )

    st.divider()

    # =====================================================
    # NEWS ARTICLES
    # =====================================================

    st.header(
        "📰 News Articles"
    )

    for article in articles:

        with st.expander(
            article.get(
                "title",
                "Untitled"
            )
        ):

            st.write(
                article.get(
                    "description",
                    ""
                )
            )

            st.write(
                f"Mindshare Score: {article.get('mindshare_score',0)}"
            )

            st.write(
                f"Trend: {article.get('trend','unknown')}"
            )

    st.divider()

    # =====================================================
    # BEST OPPORTUNITY
    # =====================================================

    st.header(
        "🎯 Selected Opportunity"
    )

    st.success(
        result.get(
            "selected_title",
            ""
        )
    )

    st.metric(
        "Relevance Score",
        result.get(
            "relevance_score",
            0
        )
    )

    st.write(
        "**Recommended Angle**"
    )

    st.write(
        result.get(
            "angle",
            ""
        )
    )

    st.write(
        "**Reason**"
    )

    st.info(
        result.get(
            "reason",
            ""
        )
    )

    st.divider()

    # =====================================================
    # GENERATED CONTENT
    # =====================================================

    st.header(
        "✨ Generated Content"
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "Instagram",
            "LinkedIn",
            "Twitter/X"
        ]
    )

    with tab1:

        st.text_area(
            "Instagram Caption",
            value=content.get(
                "instagram_caption",
                ""
            ),
            height=250
        )

    with tab2:

        st.text_area(
            "LinkedIn Post",
            value=content.get(
                "linkedin_post",
                ""
            ),
            height=250
        )

    with tab3:

        st.text_area(
            "Tweet / X Post",
            value=content.get(
                "tweet_x",
                ""
            ),
            height=250
        )

    st.divider()

    # =====================================================
    # MINDSHARE RANKING
    # =====================================================

    st.header(
        "📊 Mindshare Ranking"
    )

    for idx, article in enumerate(
        articles,
        start=1
    ):

        st.write(
            f"{idx}. {article.get('title','')}"
        )

        st.write(
            f"Score: {article.get('mindshare_score',0)}"
        )

        st.write(
            f"Trend: {article.get('trend','unknown')}"
        )

        st.write("---")

