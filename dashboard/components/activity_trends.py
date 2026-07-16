"""
Activity Trends: event breakdown and GitPulse score over time.

Uses streamlit_echarts for stacked area and line charts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars import DataFrame
from streamlit_echarts import st_echarts

from dashboard.components._palette import DANGER, EVENT_COLORS, SUCCESS, WARNING

EVENT_COLUMNS: list[tuple[str, str]] = [
    ("push_events", "Push"),
    ("pr_events", "Pull Request"),
    ("issue_events", "Issue"),
    ("watch_events", "Watch/Star"),
    ("fork_events", "Fork"),
]


def render_event_breakdown(breakdown: DataFrame) -> None:
    """Stacked area chart: daily event type breakdown."""
    if breakdown.is_empty():
        st.info(body="No event breakdown data for the current selection.")
        return

    days: list[Any] = breakdown["day"].dt.strftime(format="%Y-%m-%d").to_list()

    series = []
    for col, name in EVENT_COLUMNS:
        series.append(
            {
                "name": name,
                "type": "line",
                "stack": "events",
                "areaStyle": {"opacity": 0.6},
                "emphasis": {"focus": "series"},
                "data": breakdown[col].to_list(),
                "itemStyle": {"color": EVENT_COLORS[name]},
            }
        )

    options = {
        "tooltip": {
            "trigger": "axis",
            "formatter": (
                "{b}<br/>"
                + "<br/>".join(
                    f"{name}: {{c{i}}}" for i, (_, name) in enumerate(iterable=EVENT_COLUMNS)
                )
            ),
        },
        "legend": {
            "data": [name for _, name in EVENT_COLUMNS],
            "bottom": 0,
            "type": "scroll",
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "15%",
            "containLabel": True,
        },
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {"type": "value", "minInterval": 1},
        "series": series,
    }
    st_echarts(options, height="400px")


def render_score_timeline(breakdown: DataFrame) -> None:
    """Line chart: average GitPulse score per day."""
    if breakdown.is_empty():
        st.info(body="No score data for the current selection.")
        return

    days: list[Any] = breakdown["day"].dt.strftime(format="%Y-%m-%d").to_list()
    scores = [round(number=score, ndigits=2) for score in breakdown["avg_gitpulse_score"].to_list()]

    options = {
        "tooltip": {"trigger": "axis", "formatter": "{b}<br/>Score: {c}"},
        "legend": {"data": ["GitPulse score"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {
            "type": "value",
            "min": 0,
            "max": 100,
        },
        "visualMap": {
            "show": True,
            "type": "piecewise",
            "bottom": -10,
            "left": "center",
            "orient": "horizontal",
            "inverse": False,
            "pieces": [
                {"lte": 30, "color": DANGER, "label": "Low (≤30)"},
                {"gt": 30, "lte": 60, "color": WARNING, "label": "Average (31‑60)"},
                {"gt": 60, "color": SUCCESS, "label": "Good (>60)"},
            ],
        },
        "series": [
            {
                "name": "GitPulse Score",
                "type": "line",
                "data": scores,
                "smooth": True,
                "lineStyle": {"width": 2},
                "areaStyle": {"opacity": 0.15},
                "markLine": {
                    "silent": True,
                    "data": [
                        {
                            "yAxis": 60,
                            # "label": {"formatter": "Good {c}"},
                            "lineStyle": {"color": SUCCESS},
                        },
                        {
                            "yAxis": 30,
                            # "label": {"formatter": "Low {c}"},
                            "lineStyle": {"color": DANGER},
                        },
                    ],
                    "lineStyle": {"type": "dashed", "opacity": 0.5},
                },
            }
        ],
    }
    st_echarts(options, height="360px")
