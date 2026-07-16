"""
Overview Charts: daily event timeline, event type distribution, and top repos bar chart.

Uses streamlit_echarts for line, pie, and bar charts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars import DataFrame
from streamlit_echarts import st_echarts

from dashboard.components._palette import EVENT_COLORS, PRIMARY


def render_events_timeline(timeline: DataFrame) -> None:
    """Line chart: events per day over the selected period."""
    if timeline.is_empty():
        st.info(body="No activity data for the current selection.")
        return

    days: list[Any] = timeline["day"].dt.strftime(format="%Y-%m-%d").to_list()
    values: list[Any] = timeline["total_events"].to_list()

    options = {
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {"type": "value", "minInterval": 1},
        "series": [
            {
                "name": "Events",
                "type": "line",
                "data": values,
                "smooth": True,
                "lineStyle": {"width": 2},
                "areaStyle": {"opacity": 0.15},
                "itemStyle": {"color": PRIMARY},
            }
        ],
    }
    st_echarts(options, height="360px")


def render_event_type_distribution(distribution: dict[str, int]) -> None:
    """Half doughnut chart: breakdown of event types."""
    if not distribution or all(v == 0 for v in distribution.values()):
        st.info(body="No event distribution available for the current selection.")
        return

    data = [
        {"value": count, "name": etype, "itemStyle": {"color": EVENT_COLORS.get(etype, "#999")}}
        for etype, count in distribution.items()
        if count > 0
    ]

    options = {
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"bottom": "-5%", "left": "center"},
        "series": [
            {
                "name": "Event type",
                "type": "pie",
                "radius": ["40%", "70%"],
                "center": ["50%", "70%"],
                "startAngle": 180,
                "endAngle": 360,
                "itemStyle": {"borderRadius": 4},
                "label": {"fontSize": 11},
                "data": data,
            }
        ],
    }
    st_echarts(options, height="400px")


def render_top_repos(top_repos: DataFrame) -> None:
    """Horizontal bar chart: top N repos by total events."""
    if top_repos.is_empty():
        st.info(body="No repository data for the current selection.")
        return

    names: list[Any] = top_repos["repo_name"].to_list()[::-1]
    values: list[Any] = top_repos["total_events"].to_list()[::-1]

    options = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "8%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value", "minInterval": 1},
        "yAxis": {
            "type": "category",
            "data": names,
            "axisLabel": {"fontSize": 11},
        },
        "series": [
            {
                "name": "Total events",
                "type": "bar",
                "data": values,
                "itemStyle": {"color": PRIMARY, "borderRadius": [0, 4, 4, 0]},
            }
        ],
    }
    st_echarts(options, height="320px")
