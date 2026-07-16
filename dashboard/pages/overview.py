"""Overview: KPIs, timeline, event distribution, and top repositories."""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars.dataframe.frame import DataFrame
from streamlit.delta_generator import DeltaGenerator

from dashboard.components.activity_trends import render_event_breakdown
from dashboard.components.kpi_cards import render as render_kpi_cards
from dashboard.components.overview_charts import (
    render_event_type_distribution,
    render_events_timeline,
    render_top_repos,
)
from dashboard.queries import (
    get_daily_event_breakdown,
    get_daily_timeline,
    get_event_type_distribution,
    get_overview_kpis,
    get_top_repos,
)

# Date validation
date_range: Any | None = st.session_state.get("filter_date_range")

if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:  # noqa: PLR2004
    st.info(body="Select a date range in the sidebar.", icon=":material/calendar_month:")
    st.stop()

start, end = date_range

if start > end:
    st.error(body="Start date must be on or before end date.")
    st.stop()

# Data loading
progress_holder: DeltaGenerator = st.empty()

try:
    with progress_holder.container():
        bar: DeltaGenerator = st.progress(value=0, text="Fetching KPIs…")
        kpis: dict[str, Any] = get_overview_kpis(start=start, end=end)

        bar.progress(value=15, text="Loading timeline…")
        timeline: DataFrame = get_daily_timeline(start=start, end=end)

        bar.progress(value=30, text="Loading event distribution…")
        distribution: dict[str, int] = get_event_type_distribution(start=start, end=end)

        bar.progress(value=45, text="Fetching top repos…")
        top_repos: DataFrame = get_top_repos(start=start, end=end)

        bar.progress(value=65, text="Building event breakdown…")
        breakdown: DataFrame = get_daily_event_breakdown(start=start, end=end)

        bar.progress(value=100, text=":material/check_circle: Ready!")
except Exception:
    progress_holder.empty()
    st.error(body="Failed to load overview data. Check that the data source is available.")
    st.stop()

progress_holder.empty()

# Render sections
st.subheader(body=":material/home: At a glance")
render_kpi_cards(kpis)
st.divider()

st.subheader(body=":material/trending_up: Activity timeline")
st.markdown(body="Daily event volume across all repositories.")
render_events_timeline(timeline)
st.divider()

col1, col2 = st.columns(spec=2)
with col1:
    st.subheader(body=":material/track_changes: Event type distribution")
    st.markdown(body="Proportion of each event type in the period.")
    render_event_type_distribution(distribution)
with col2:
    st.subheader(body=":material/bar_chart: Event type breakdown")
    st.markdown(body="Daily volume per event type as a stacked area.")
    render_event_breakdown(breakdown)
st.divider()

st.subheader(body=":material/emoji_events: Top repositories")
st.markdown(body="Repositories with the highest event count.")
render_top_repos(top_repos)
st.caption(
    body="**Note**: Based on total events in the selected period, not necessarily the most active repos overall."
)
