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
st.caption(
    "Mindshare-Driven Newsjacking Engine"
)

st.divider()

# =====================================================
# INPUT
# =====================================================

brand_url = st.text_input(
    "Enter Brand Website URL",
    placeholder="https://www.thewholetruthfoods.com"
)

# =====================================================
# PIPELINE
# =====================================================

if st.button("Analyze Brand"):

    if not brand_url:

        st.error(
            "Please enter a valid URL."
        )

    else:

        try:

            with st.spinner(
                "Running NewsJack Pipeline..."
            ):

                # =================================
                # STAGE 1
                # =================================

                audit_data = scrape_brand_website(
                    brand_url
                )

                # =================================
                # STAGE 2
                # =================================

                profile = generate_brand_profile(
                    audit_data
                )

                # =================================
                # STAGE 3
                # =================================

                articles = fetch_news(
                    profile["keywords"]
                )

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

                    result = re.sub(
                        r"```json|```",
                        "",
                        result
                    ).strip()

                    result = json.loads(
                        result
                    )

                # =================================
                # STAGE 6
                # =================================

                content = generate_content(
                    profile,
                    result
                )

                if isinstance(content, str):

                    content = re.sub(
                        r"```json|```",
                        "",
                        content
                    ).strip()

                    content = json.loads(
                        content
                    )

        except Exception as e:

            st.error(
                f"Pipeline Error: {e}"
            )

            st.stop()

        # =================================================
        # BRAND PROFILE
        # =================================================

        st.success(
            "Analysis Complete"
        )

        st.divider()

        st.header(
            "🏢 Brand Profile"
        )

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                "**Brand Name**"
            )
            st.write(
                profile["brand_name"]
            )

            st.write(
                "**Category**"
            )
            st.write(
                profile["category"]
            )

            st.write(
                "**Tone**"
            )
            st.write(
                profile["tone"]
            )

        with col2:

            st.write(
                "**Target Audience**"
            )

            st.write(
                profile["target_audience"]
            )

            st.write(
                "**Keywords**"
            )

            st.write(
                profile["keywords"]
            )

        st.write(
            "**Brand Summary**"
        )

        st.info(
            profile["brand_summary"]
        )

        st.divider()

        # =================================================
        # NEWS
        # =================================================

        st.header(
            "📰 News Articles"
        )

        for article in articles:

            with st.expander(
                article["title"]
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

        # =================================================
        # SELECTED OPPORTUNITY
        # =================================================

        st.header(
            "🎯 Selected Opportunity"
        )

        st.success(
            result["selected_title"]
        )

        st.metric(
            "Relevance Score",
            result["relevance_score"]
        )

        st.write(
            "**Recommended Angle**"
        )

        st.write(
            result["angle"]
        )

        st.write(
            "**Reason**"
        )

        st.info(
            result["reason"]
        )

        st.divider()

        # =================================================
        # GENERATED CONTENT
        # =================================================

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

        st.header(
            "📊 Mindshare Ranking"
        )

        for idx, article in enumerate(
            articles,
            start=1
        ):

            st.write(
                f"""
                {idx}. {article['title']}
                
                Score: {article.get('mindshare_score',0)}
                
                Trend: {article.get('trend','unknown')}
                """
            )