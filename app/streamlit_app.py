"""Investor-demo quality Streamlit dashboard for NEWSJACK AI."""

from __future__ import annotations

import sys
import os
from html import escape
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import plotly.express as px
import streamlit as st

from app.logging_config import configure_logging
from app.services.analytics_service import build_analytics
from app.services.brand_profile_service import delete_brand_profile, list_brand_profiles, save_brand_profile
from app.services.competitor_monitor_service import monitor_competitors
from app.services.linkedin_scheduler_service import (
    GAMEPULSE_PROFILE,
    approve_post,
    export_calendar_to_csv,
    generate_linkedin_calendar,
    load_calendar_from_notion,
    mark_post_as_failed,
    mark_post_as_posted,
    mark_post_as_scheduled,
    push_calendar_to_notion,
)
from app.services.linkedin_post_service import publish_due_posts
from app.services.mongodb_service import ping_mongodb
from app.services.notion_service import get_or_create_linkedin_calendar_database
from app.services.pipeline_service import add_campaign_assets, discover_and_rank
from app.services.env_service import env_presence_report

configure_logging()

st.set_page_config(page_title="NEWSJACK AI", page_icon="⚡", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1400px;}
      [data-testid="stMetric"] {background: rgba(120,120,120,.08); border: 1px solid rgba(130,130,130,.18);
        padding: 16px; border-radius: 16px;}
      .nj-card {padding: 18px; border: 1px solid rgba(130,130,130,.22); border-radius: 18px;
        background: linear-gradient(145deg, rgba(110,86,207,.10), rgba(0,180,180,.04)); margin-bottom: 12px;}
      .brand-card {padding: 16px; border: 1px solid rgba(130,130,130,.22); border-radius: 16px;
        background: rgba(120,120,120,.07); margin-bottom: 10px;}
      .active-brand {border-color: #ff4b4b; background: rgba(255,75,75,.08);}
      .nj-kicker {letter-spacing: .12em; text-transform: uppercase; color: #8c83ff; font-size: .78rem; font-weight: 700;}
      .nj-score {font-size: 2rem; font-weight: 800; color: #7f75ff;}
      .stButton > button {border-radius: 12px; font-weight: 650;}
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULT_BRAND = {
    "brand_name": "ProteinX",
    "industry": "Fitness & Nutrition",
    "target_audience": "Gym enthusiasts and health-conscious young professionals",
    "tone": "Motivational, credible, energetic",
    "goals": "Increase awareness and build category authority",
    "keywords": ["fitness", "protein", "recovery", "workout", "nutrition"],
    "competitors": ["MuscleBlaze", "Optimum Nutrition", "MyProtein"],
    "products": ["Protein Powder", "Pre Workout"],
    "brand_summary": "A performance nutrition brand helping active people train and recover better.",
}

if "profiles" not in st.session_state:
    st.session_state.profiles = list_brand_profiles()
if "brand" not in st.session_state:
    saved = st.session_state.profiles
    st.session_state.brand = saved[0].model_dump(mode="json") if saved else DEFAULT_BRAND.copy()
if "opportunities" not in st.session_state:
    st.session_state.opportunities = []
if "selected_topic" not in st.session_state:
    st.session_state.selected_topic = None
if "linkedin_generated_calendar" not in st.session_state:
    st.session_state.linkedin_generated_calendar = []
if "linkedin_notion_posts" not in st.session_state:
    st.session_state.linkedin_notion_posts = []


def headline(title: str, subtitle: str) -> None:
    st.markdown('<div class="nj-kicker">Mindshare Intelligence Engine</div>', unsafe_allow_html=True)
    st.title(title)
    st.caption(subtitle)


def run_discovery(generate_assets: bool = False) -> None:
    with st.spinner("Scanning live signals and ranking brand opportunities…"):
        st.session_state.opportunities = discover_and_rank(
            st.session_state.brand, limit=10, generate_assets=generate_assets
        )
    if st.session_state.opportunities:
        st.session_state.selected_topic = st.session_state.opportunities[0]["topic"]
    st.toast("Opportunity scan complete", icon="⚡")


def selected_opportunity() -> dict | None:
    for item in st.session_state.opportunities:
        if item["topic"] == st.session_state.selected_topic:
            return item
    return st.session_state.opportunities[0] if st.session_state.opportunities else None


def score_color(score: int) -> str:
    return "🟢" if score >= 75 else "🟡" if score >= 55 else "🔵"


def refresh_profiles() -> None:
    st.session_state.profiles = list_brand_profiles()


def activate_profile(profile) -> None:
    st.session_state.brand = profile.model_dump(mode="json")
    st.session_state.opportunities = []
    st.session_state.selected_topic = None


def database_badge() -> str:
    status = ping_mongodb()
    if status.get("connected"):
        return "🟢 MongoDB connected"
    if status.get("enabled"):
        return "🟡 MongoDB fallback"
    return "🔵 Local JSON storage"


with st.sidebar:
    st.markdown("## ⚡ NEWSJACK AI")
    st.caption("Discover trends. Find opportunities. Generate campaigns.")
    page = st.radio(
        "Workspace",
        [
            "Overview",
            "Opportunity Explorer",
            "Campaign Studio",
            "LinkedIn Scheduler",
            "Brand Profile",
            "Competitor Monitor",
            "Analytics",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Database")
    st.write(database_badge())
    st.divider()
    st.caption("Brand Library")
    profiles = st.session_state.get("profiles", [])
    if profiles:
        st.caption(f"{len(profiles)} saved profile{'s' if len(profiles) != 1 else ''}")
        profile_labels = [f"{profile.brand_name} · {profile.industry}" for profile in profiles]
        current_id = st.session_state.brand.get("id")
        current_index = next((i for i, profile in enumerate(profiles) if profile.id == current_id), 0)
        selected_label = st.selectbox("Switch active brand", profile_labels, index=current_index)
        selected_profile = profiles[profile_labels.index(selected_label)]
        if selected_profile.id != current_id:
            activate_profile(selected_profile)
            st.rerun()
        for profile in profiles[:5]:
            is_active = profile.id == st.session_state.brand.get("id")
            label = f"{'✓ ' if is_active else ''}{profile.brand_name}"
            if st.button(label, key=f"quick-brand-{profile.id}", use_container_width=True, disabled=is_active):
                activate_profile(profile)
                st.rerun()
    else:
        st.info("No saved profiles yet. Save one from Brand Profile.")
    if st.button("Refresh brand library", use_container_width=True):
        refresh_profiles()
        st.rerun()
    st.divider()
    st.caption("Active brand")
    st.write(f"**{st.session_state.brand['brand_name']}**")
    st.caption(st.session_state.brand.get("industry", ""))
    if st.button("Run intelligence scan", type="primary", use_container_width=True):
        run_discovery()


if page == "Overview":
    headline("Your next campaign is already in the news.", "See the strongest moments for your brand before attention moves on.")
    if not st.session_state.opportunities:
        st.info("Run an intelligence scan to load live opportunities. Provider-free fallback data keeps the demo fully usable.")
        if st.button("Discover opportunities", type="primary"):
            run_discovery()
            st.rerun()
    items = st.session_state.opportunities
    if items:
        analytics = build_analytics(items)
        cols = st.columns(4)
        cols[0].metric("Opportunities", len(items))
        cols[1].metric("Average score", analytics["average_score"])
        cols[2].metric("High priority", sum(item["final_score"] >= 75 for item in items))
        cols[3].metric("News sources", sum(item["source_diversity"] for item in items))

        st.subheader("Top opportunities")
        for item in items[:10]:
            safe_category = escape(str(item["category"]))
            safe_source = escape(str(item["source"]))
            safe_topic = escape(str(item["topic"]))
            safe_summary = escape(str(item["summary"] or item["reason"]))
            st.markdown(
                f"""<div class="nj-card"><div class="nj-kicker">{safe_category} · {safe_source}</div>
                <h3>{score_color(item['final_score'])} {safe_topic}</h3>
                <p>{safe_summary}</p>
                <span class="nj-score">{item['final_score']}</span> / 100
                &nbsp; · Relevance {item.get('relevance_score', item.get('brand_relevance', 0))}
                &nbsp; · Trend {item.get('trend_score', item.get('trend_strength', 0))}</div>""",
                unsafe_allow_html=True,
            )

        tab_news, tab_trends, tab_competitors, tab_ai = st.tabs(
            ["Latest relevant news", "Trending topics", "Competitor activity", "AI recommendations"]
        )
        with tab_news:
            shown = 0
            for item in items:
                for article in item.get("articles", []):
                    if article.get("relevance_score", 0) < 60:
                        continue
                    title = article.get("headline") or article.get("title")
                    st.markdown(f"**{title}**")
                    st.caption(f"{article.get('source', 'Unknown')} · relevance {article.get('relevance_score', 0)}/100")
                    if article.get("description"):
                        st.write(article["description"])
                    if article.get("url"):
                        st.link_button("Read source", article["url"])
                    shown += 1
                    if shown >= 8:
                        break
                if shown >= 8:
                    break
            if not shown:
                st.info("No article crossed the 60 relevance threshold yet. Try refining the brand profile or adding provider keys.")
        with tab_trends:
            left, right = st.columns([1.4, 1])
            with left:
                for item in items:
                    st.markdown(
                        f"- **{item['topic']}** — trend {item.get('trend_score', item.get('trend_strength', 0))}/100, "
                        f"brand relevance {item.get('brand_relevance', 0)}/100"
                    )
            with right:
                frame = pd.DataFrame(analytics["top_categories"])
                if not frame.empty:
                    st.plotly_chart(
                        px.pie(frame, names="category", values="count", hole=.58, title="Relevant topic mix"),
                        use_container_width=True,
                    )
        with tab_competitors:
            competitor_rows = []
            for item in items:
                competitor_rows.extend(item.get("competitor_signals", []))
            if competitor_rows:
                for mention in competitor_rows[:8]:
                    st.markdown(f"**{mention.get('competitor', 'Competitor')}** — {mention.get('headline', '')}")
                    st.caption(
                        f"{mention.get('announcement_type', 'Signal')} · impact {mention.get('impact_score', 0)}/100 · "
                        f"{mention.get('date', '')}"
                    )
                    if mention.get("url"):
                        st.link_button("Open mention", mention["url"])
            else:
                st.info("No competitor activity loaded yet. Add competitors and GNews/NewsAPI keys for live monitoring.")
        with tab_ai:
            for item in items[:3]:
                campaign = item.get("campaign") or {}
                safe_category = escape(str(item["category"]))
                safe_topic = escape(str(item["topic"]))
                st.markdown(f"#### {safe_topic}")
                st.caption(safe_category)
                st.write(f"**Recommended Campaign:** {campaign.get('campaign_angle', item.get('recommended_angle', 'Timely point of view'))}")
                st.write(f"**Recommended Content Piece:** {', '.join(campaign.get('suggested_content', ['Rapid-response LinkedIn post'])[:2])}")
                content = item.get("content") or {}
                st.write(f"**Recommended Social Post:** {content.get('twitter_post') or content.get('linkedin_post', '')[:220]}")
                st.write(f"**Why Now:** {campaign.get('why_it_matters', item.get('reason', 'The signal is timely and brand-relevant.'))}")

elif page == "Opportunity Explorer":
    headline("Opportunity Explorer", "Search, filter, and inspect the evidence behind every score.")
    items = st.session_state.opportunities
    if not items:
        st.warning("Run an intelligence scan from the sidebar first.")
    else:
        query = st.text_input("Search opportunities", placeholder="AI, sports, sustainability…")
        categories = sorted({item["category"] for item in items})
        selected_categories = st.multiselect("Categories", categories, default=categories)
        minimum = st.slider("Minimum score", 0, 100, 40)
        filtered = [
            item for item in items
            if query.lower() in item["topic"].lower()
            and item["category"] in selected_categories
            and item["final_score"] >= minimum
        ]
        for item in filtered:
            with st.expander(f"{score_color(item['final_score'])} {item['topic']} — {item['final_score']}/100"):
                a, b, c, d = st.columns(4)
                a.metric("Trend strength", item["trend_strength"])
                b.metric("Brand relevance", item["brand_relevance"])
                c.metric("Audience overlap", item["audience_overlap"])
                d.metric("Newsjack potential", item["newsjack_potential"])
                st.write(item["reason"])
                st.progress(item["final_score"] / 100)
                articles = item.get("articles", [])
                if articles:
                    st.markdown("#### Supporting news")
                    for article in articles[:5]:
                        label = f"{article['headline']} · {article['source']}"
                        if article.get("url"):
                            st.markdown(f"- [{label}]({article['url']})")
                        else:
                            st.markdown(f"- {label}")
                if st.button("Open in Campaign Studio", key=f"studio-{item['topic']}"):
                    st.session_state.selected_topic = item["topic"]
                    st.toast("Opportunity selected. Open Campaign Studio from the sidebar.")

elif page == "Campaign Studio":
    headline("Campaign Studio", "Turn a strong signal into a channel-ready campaign.")
    items = st.session_state.opportunities
    if not items:
        st.warning("Run an intelligence scan before generating a campaign.")
    else:
        topics = [item["topic"] for item in items]
        current = st.session_state.selected_topic if st.session_state.selected_topic in topics else topics[0]
        st.session_state.selected_topic = st.selectbox("Opportunity", topics, index=topics.index(current))
        item = selected_opportunity()
        if item:
            top = st.columns([3, 1])
            top[0].subheader(item["topic"])
            top[0].write(item["reason"])
            top[1].metric("Opportunity score", item["final_score"])
            if st.button("Generate / regenerate campaign", type="primary"):
                with st.spinner("Building the campaign and channel copy…"):
                    generated = add_campaign_assets(st.session_state.brand, item)
                    for index, candidate in enumerate(st.session_state.opportunities):
                        if candidate["topic"] == generated["topic"]:
                            st.session_state.opportunities[index] = generated
                    item = generated
            if item.get("campaign"):
                campaign = item["campaign"]
                st.success(campaign["campaign_angle"])
                c1, c2 = st.columns(2)
                c1.write("**Why it matters**")
                c1.write(campaign["why_it_matters"])
                c2.write("**Recommended channels**")
                c2.write(" · ".join(campaign["recommended_channels"]))
                content = item.get("content", {})
                tabs = st.tabs(["LinkedIn", "X / Twitter", "Instagram", "Blog", "Ads & Email", "Hook & CTA"])
                tabs[0].text_area("LinkedIn post", content.get("linkedin_post", ""), height=240)
                tabs[1].text_area("X post", content.get("twitter_post", ""), height=180)
                tabs[2].text_area("Instagram caption", content.get("instagram_caption", ""), height=240)
                tabs[3].text_area("Blog outline", content.get("blog_outline", ""), height=260)
                with tabs[4]:
                    st.text_area("Ad copy", content.get("ad_copy", ""), height=140)
                    st.text_area("Email campaign", content.get("email_campaign", ""), height=220)
                    st.text_area("Landing page headline", content.get("landing_page_headline", ""), height=100)
                with tabs[5]:
                    st.text_area("Marketing hook", content.get("marketing_hook", ""))
                    st.text_area("CTA", content.get("cta", ""))
                    st.write(" ".join(content.get("hashtags", [])))
            else:
                st.info("Generate the campaign to create angles, channel recommendations, and social copy.")

elif page == "LinkedIn Scheduler":
    headline("GamePulse AI LinkedIn Scheduler", "Generate, approve, and manage 30 days of LinkedIn content in Notion.")

    def load_notion_posts_into_state(success_message: str | None = None) -> bool:
        result = load_calendar_from_notion()
        if result.get("ok"):
            st.session_state.linkedin_notion_posts = result.get("posts", [])
            if success_message:
                st.success(success_message.format(count=len(st.session_state.linkedin_notion_posts)))
            return True
        st.error(result.get("message", "Could not load posts from Notion."))
        return False

    def apply_notion_action(page_id: str, action) -> None:
        result = action(page_id)
        if result.get("ok"):
            st.toast(result.get("message", "Notion updated."), icon="✅")
            load_notion_posts_into_state()
            st.rerun()
        else:
            st.error(result.get("message", "Could not update Notion."))

    notion_env = env_presence_report(["NOTION_API_KEY", "NOTION_PARENT_PAGE_ID", "NOTION_LINKEDIN_DATABASE_ID"])
    notion_ready = bool(notion_env["NOTION_API_KEY"] and (notion_env["NOTION_PARENT_PAGE_ID"] or notion_env["NOTION_LINKEDIN_DATABASE_ID"]))
    linkedin_env = env_presence_report(["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_URN"])
    if not notion_ready:
        st.warning("Notion is not configured yet.")
        st.markdown(
            """
            **Setup instructions**

            1. Create a Notion integration at https://www.notion.so/my-integrations.
            2. Copy the integration secret into `.env` as `NOTION_API_KEY`.
            3. Create or choose a parent Notion page for the scheduler database.
            4. Share that parent page with your Notion integration.
            5. Copy the parent page ID into `.env` as `NOTION_PARENT_PAGE_ID`.
            6. Optionally add `NOTION_LINKEDIN_DATABASE_ID` if you already have a database.
            7. Restart Streamlit after changing `.env`.
            """
        )
    if not all(linkedin_env.values()):
        st.info("LinkedIn publishing not configured yet. Notion generation, approval, scheduling, and CSV export are still available.")

    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("Connect Notion", use_container_width=True):
        with st.spinner("Connecting to Notion..."):
            result = get_or_create_linkedin_calendar_database()
        if result.get("ok"):
            st.success(f"{result['message']} Database ID: {result.get('database_id', '')}")
            load_notion_posts_into_state()
        else:
            st.error(result.get("message", "Could not connect to Notion."))

    if c2.button("Generate 30-Day Calendar", type="primary", use_container_width=True):
        with st.spinner("Generating GamePulse AI LinkedIn calendar..."):
            st.session_state.linkedin_generated_calendar = generate_linkedin_calendar(GAMEPULSE_PROFILE, days=30)
        st.success("Generated 30 draft posts. Use Push to Notion to save them.")

    if c3.button("Push to Notion", use_container_width=True):
        if not st.session_state.linkedin_generated_calendar:
            st.error("Generate a calendar before pushing to Notion.")
        else:
            with st.spinner("Pushing posts to Notion..."):
                result = push_calendar_to_notion(st.session_state.linkedin_generated_calendar)
            if result.get("ok"):
                st.success(result["message"])
                st.session_state.linkedin_generated_calendar = []
                load_notion_posts_into_state()
            else:
                st.error(result.get("message", "Could not push calendar to Notion."))

    if c4.button("Load from Notion", use_container_width=True):
        with st.spinner("Loading calendar from Notion..."):
            load_notion_posts_into_state("Loaded {count} posts from Notion.")

    if c5.button("Publish Due Posts", use_container_width=True):
        with st.spinner("Publishing due approved posts through LinkedIn API..."):
            result = publish_due_posts()
        if result.get("ok"):
            st.success(result.get("message", "Publish complete."))
        else:
            st.warning(
                f"Published {result.get('published', 0)} post(s); "
                f"{result.get('failed', 0)} failed."
            )
        load_notion_posts_into_state()

    pending_count = len(st.session_state.linkedin_generated_calendar)
    if pending_count:
        st.info(f"{pending_count} generated drafts are waiting to be pushed to Notion. The list below only shows Notion posts.")

    notion_posts = st.session_state.linkedin_notion_posts
    csv_data = export_calendar_to_csv(notion_posts) if notion_posts else ""
    st.download_button(
        "Export Notion Posts CSV",
        data=csv_data,
        file_name="gamepulse_ai_linkedin_calendar.csv",
        mime="text/csv",
        disabled=not bool(csv_data),
    )

    if notion_posts:
        table = pd.DataFrame(
            [
                {
                    "Date": post.get("date", ""),
                    "Time": post.get("time", ""),
                    "Title": post.get("post_title", ""),
                    "Status": post.get("status", ""),
                    "Approval": "Approved" if post.get("approval") else "Pending",
                    "LinkedIn URL": post.get("linkedin_url", ""),
                    "LinkedIn Post": post.get("linkedin_post", ""),
                }
                for post in notion_posts
            ]
        )
        st.dataframe(table, use_container_width=True, hide_index=True)
        for index, post in enumerate(notion_posts):
            title = post.get("post_title") or f"LinkedIn post {index + 1}"
            with st.expander(f"{post.get('date', '')} · {title}"):
                meta = st.columns(5)
                meta[0].write(f"**Date:** {post.get('date', '')}")
                meta[1].write(f"**Time:** {post.get('time', '')}")
                meta[2].write(f"**Title:** {title}")
                meta[3].write(f"**Status:** {post.get('status', '')}")
                meta[4].write(f"**Approval:** {'Approved' if post.get('approval') else 'Pending'}")
                st.text_area(
                    "Full LinkedIn post",
                    post.get("linkedin_post", ""),
                    height=220,
                    key=f"linkedin-post-{post.get('page_id', index)}",
                    disabled=True,
                )
                if post.get("campaign_angle"):
                    st.write(f"**Campaign angle:** {post.get('campaign_angle', '')}")
                if post.get("hashtags"):
                    st.write(f"**Hashtags:** {' '.join('#' + tag.lstrip('#') for tag in post.get('hashtags', []))}")
                if post.get("linkedin_url"):
                    st.link_button("Open LinkedIn post", post["linkedin_url"])
                actions = st.columns(4)
                page_id = post.get("page_id", "")
                if actions[0].button("Approve", key=f"approve-{index}", disabled=not bool(page_id)):
                    apply_notion_action(page_id, approve_post)
                if actions[1].button("Mark Scheduled", key=f"scheduled-{index}", disabled=not bool(page_id)):
                    apply_notion_action(page_id, mark_post_as_scheduled)
                if actions[2].button("Mark Posted", key=f"posted-{index}", disabled=not bool(page_id)):
                    apply_notion_action(page_id, mark_post_as_posted)
                if actions[3].button("Mark Failed", key=f"failed-{index}", disabled=not bool(page_id)):
                    apply_notion_action(page_id, mark_post_as_failed)
                if not page_id:
                    st.caption("Load this post from Notion to enable approval and status updates.")
    else:
        st.info("Load posts from Notion, or generate a 30-day calendar and push it to Notion.")

elif page == "Brand Profile":
    headline("Brand Profile", "Teach the engine what your brand stands for and who it needs to reach.")
    refresh_profiles()
    st.subheader("Saved Brand Library")
    profiles = st.session_state.get("profiles", [])
    if profiles:
        search = st.text_input("Find saved brands", placeholder="Search by brand or industry…")
        visible_profiles = [
            profile for profile in profiles
            if search.lower() in f"{profile.brand_name} {profile.industry} {' '.join(profile.keywords)}".lower()
        ]
        for profile in visible_profiles:
            active = profile.id == st.session_state.brand.get("id")
            card_class = "brand-card active-brand" if active else "brand-card"
            st.markdown(
                f"""<div class="{card_class}">
                <div class="nj-kicker">{escape(profile.industry)}</div>
                <h4>{'✓ ' if active else ''}{escape(profile.brand_name)}</h4>
                <p>{escape(profile.brand_summary or profile.target_audience or 'No summary yet.')}</p>
                </div>""",
                unsafe_allow_html=True,
            )
            c1, c2, c3 = st.columns([1, 1, 4])
            if c1.button("Use", key=f"use-profile-{profile.id}", disabled=active):
                activate_profile(profile)
                st.rerun()
            if c2.button("Delete", key=f"delete-profile-{profile.id}", disabled=active):
                delete_brand_profile(profile.id)
                refresh_profiles()
                st.success(f"Deleted {profile.brand_name}")
                st.rerun()
        if not visible_profiles:
            st.info("No saved brand matched that search.")
    else:
        st.info("No saved brands yet. Fill the form below and save your first profile.")
    st.divider()
    st.subheader("Create or edit active brand")
    brand = st.session_state.brand
    with st.form("brand-profile"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Brand name", brand.get("brand_name", ""))
        industry = c2.text_input("Industry", brand.get("industry", ""))
        audience = st.text_area("Target audience", brand.get("target_audience", ""))
        tone = c1.text_input("Tone", brand.get("tone", ""))
        goals = c2.text_input("Goals", brand.get("goals", ""))
        keywords = st.text_input("Keywords (comma separated)", ", ".join(brand.get("keywords", [])))
        products = st.text_input("Products (comma separated)", ", ".join(brand.get("products", [])))
        competitors = st.text_input("Competitors (comma separated)", ", ".join(brand.get("competitors", [])))
        summary = st.text_area("Brand summary", brand.get("brand_summary", ""))
        save_as_new = st.checkbox("Save as a new brand profile", value=not bool(brand.get("id")))
        submitted = st.form_submit_button("Save brand profile", type="primary")
    if submitted:
        try:
            profile_id = None if save_as_new else brand.get("id")
            saved = save_brand_profile(
                {
                    **brand,
                    "id": profile_id,
                    "brand_name": name,
                    "industry": industry,
                    "target_audience": audience,
                    "tone": tone,
                    "goals": goals,
                    "keywords": keywords,
                    "products": products,
                    "competitors": competitors,
                    "brand_summary": summary,
                }
            )
            st.session_state.brand = saved.model_dump(mode="json")
            refresh_profiles()
            st.success(f"Brand profile saved: {saved.brand_name}")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not save brand profile: {exc.__class__.__name__}")

elif page == "Competitor Monitor":
    headline("Competitor Monitor", "Track announcements and earned-media signals around your competitive set.")
    competitors = st.session_state.brand.get("competitors", [])
    edited = st.text_input("Competitors", ", ".join(competitors))
    if st.button("Refresh competitor intelligence", type="primary"):
        with st.spinner("Checking recent coverage…"):
            st.session_state.competitor_mentions = monitor_competitors(
                [item.strip() for item in edited.split(",") if item.strip()]
            )
    mentions = st.session_state.get("competitor_mentions", [])
    if not mentions:
        st.info("No mentions loaded yet. NewsAPI credentials enable live monitoring.")
    for mention in mentions:
        with st.expander(f"{mention['competitor']} · {mention['headline']}"):
            st.write(mention.get("description", ""))
            st.caption(
                f"{mention.get('source', 'Unknown')} · {mention.get('announcement_type', 'Signal')} · "
                f"impact {mention.get('impact_score', 0)}/100 · {mention.get('date', '')}"
            )
            if mention.get("url"):
                st.link_button("Read source", mention["url"])

elif page == "Analytics":
    headline("Analytics", "Understand where opportunity is clustering and how strongly it fits your brand.")
    items = st.session_state.opportunities
    if not items:
        st.warning("Run an intelligence scan to populate analytics.")
    else:
        analytics = build_analytics(items)
        a, b = st.columns(2)
        score_df = pd.DataFrame(analytics["score_breakdown"])
        category_df = pd.DataFrame(analytics["top_categories"])
        a.plotly_chart(
            px.bar(score_df, x="topic", y=["final_score", "brand_relevance", "newsjack_potential"],
                   barmode="group", title="Opportunity score composition"),
            use_container_width=True,
        )
        b.plotly_chart(
            px.bar(category_df, x="category", y="count", color="category", title="Category volume"),
            use_container_width=True,
        )
        distribution = pd.DataFrame(analytics["opportunity_distribution"])
        st.plotly_chart(
            px.area(distribution, x="band", y="count", markers=True, title="Score distribution"),
            use_container_width=True,
        )
