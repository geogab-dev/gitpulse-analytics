"""Ecosystem & Growth: organisations, trending repos, releases, and star growth."""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars.dataframe.frame import DataFrame
from streamlit.delta_generator import DeltaGenerator

from dashboard.components.ecosystem import (
    render_active_repos_over_time,
    render_ecosystem_kpis,
    render_star_engagement_conversion,
    render_star_growth,
    render_stars_vs_forks_scatter,
    render_top_open_repos,
    render_trending_repos,
)
from dashboard.components.organizations import render_org_summary
from dashboard.queries import (
    get_active_repos_over_time,
    get_ecosystem_health_kpis,
    get_fork_growth,
    get_org_summary,
    get_star_engagement_conversion,
    get_star_growth,
    get_stars_vs_forks,
    get_top_forked_repos,
    get_top_open_repos,
    get_trending_repos,
)

st.title(body=":material/trending_up: Ecosystem & Growth")
st.markdown(
    body="Organisational metrics, trending repositories, forks, stars, and community growth."
)

# Date validation
date_range: Any | None = st.session_state.get("filter_date_range")

if not date_range or not isinstance(date_range, (list, tuple)) or len(date_range) != 2:  # noqa: PLR2004
    st.info(
        body="Select a complete date range in the sidebar.",
        icon=":material/calendar_month:",
    )
    st.stop()

start, end = date_range

if start > end:
    st.error(body="Start date must be on or before end date.")
    st.stop()

# Data loading
progress_holder: DeltaGenerator = st.empty()

try:
    with progress_holder.container():
        bar: DeltaGenerator = st.progress(value=0, text="Fetching ecosystem health…")
        health_kpis: dict[str, int | float | None] = get_ecosystem_health_kpis(start=start, end=end)

        bar.progress(value=10, text="Fetching organisations…")
        org_summary: DataFrame = get_org_summary(start=start, end=end)

        bar.progress(value=20, text="Loading trending repos…")
        trending: DataFrame = get_trending_repos(start=start, end=end)

        bar.progress(value=30, text="Loading active repos…")
        active_repos: DataFrame = get_active_repos_over_time(start=start, end=end)

        bar.progress(value=40, text="Loading star vs fork data…")
        stars_vs_forks: DataFrame = get_stars_vs_forks(start=start, end=end, limit=60)

        bar.progress(value=55, text="Loading star growth…")
        stars: DataFrame = get_star_growth(start=start, end=end)
        forks_growth: DataFrame = get_fork_growth(start=start, end=end)

        bar.progress(value=70, text="Loading open issues & PRs…")
        top_issues: DataFrame = get_top_open_repos(start=start, end=end, sort_by="issues")
        top_prs: DataFrame = get_top_open_repos(start=start, end=end, sort_by="prs")

        bar.progress(value=80, text="Loading trending forks…")
        trending_forks: DataFrame = get_top_forked_repos(start=start, end=end)

        bar.progress(value=85, text="Loading star engagement…")
        engagement: DataFrame = get_star_engagement_conversion(start=start, end=end, limit=60)

        bar.progress(value=100, text=":material/check_circle: Ready!")
except Exception:
    progress_holder.empty()
    st.error(body="Failed to load ecosystem data. Check that the data source is available.")
    st.stop()

progress_holder.empty()

# Render sections
render_ecosystem_kpis(health_kpis)
st.divider()

st.subheader(body=":material/business: Organizations")
st.markdown(body="Aggregated activity and score per organization.")
render_org_summary(org_summary)
st.divider()

tab_stars, tab_forks = st.tabs(
    tabs=[
        ":material/star: Stars",
        ":material/call_split: Forks",
    ]
)
with tab_stars:
    col1, col2 = st.columns(spec=2)
    with col1:
        st.subheader(body=":material/star: Star growth")
        st.markdown(body="Daily and cumulative star (WatchEvent) activity.")
        render_star_growth(star_data=stars, mode="stars")
    with col2:
        st.subheader(body=":material/star: Trending repos (stars)")
        st.markdown(body="Repositories with the most new stars in the period.")
        render_trending_repos(trending, mode="stars")
with tab_forks:
    col1, col2 = st.columns(spec=2)
    with col1:
        st.subheader(body=":material/call_split: Fork growth")
        st.markdown(body="Daily and cumulative fork activity.")
        render_star_growth(star_data=forks_growth, mode="forks")
    with col2:
        st.subheader(body=":material/call_split: Trending repos (forks)")
        st.markdown(body="Repositories with the most fork events in the period.")
        render_trending_repos(trending_forks, mode="forks")

st.divider()

st.subheader(body=":material/scatter_plot: Repository scatter analysis")
st.markdown(body="Explore how repositories relate across dimensions.")

tab_fork, tab_engage = st.tabs(
    tabs=[
        ":material/call_split: Stars vs Forks",
        ":material/conversion_path: Stars vs Engagement",
    ]
)
with tab_fork:
    render_stars_vs_forks_scatter(data=stars_vs_forks)
with tab_engage:
    render_star_engagement_conversion(conversion_data=engagement)

st.divider()

col1, col2 = st.columns(spec=2)
with col1:
    st.subheader(body=":material/dynamic_feed: Active repos over time")
    st.markdown(body="Unique repositories with activity each day.")
    render_active_repos_over_time(repo_data=active_repos)
with col2:
    st.subheader(body=":material/track_changes: Top open repos")
    st.markdown(body="Repositories with the most opened issues and pull requests.")
    tab_issues, tab_prs = st.tabs(
        tabs=[
            ":material/bug_report: By issues",
            ":material/call_merge: By PRs",
        ]
    )
    with tab_issues:
        render_top_open_repos(open_data=top_issues, show="issues")
    with tab_prs:
        render_top_open_repos(open_data=top_prs, show="prs")
