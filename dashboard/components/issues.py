"""
Issues & Support: issue metrics, close rates, and trends.

Uses streamlit_echarts for dual line and line charts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars import DataFrame
from streamlit_echarts import st_echarts

from dashboard.components._palette import CLOSED, INFO, WARNING


def render_issues_opened_vs_closed(issue_metrics: DataFrame) -> None:
    """Dual line chart: issues opened vs closed per day."""
    if issue_metrics.is_empty():
        st.info(body="No issue data for the current selection.")
        return

    days: list[Any] = issue_metrics["day"].dt.strftime(format="%Y-%m-%d").to_list()
    opened: list[Any] = issue_metrics["issues_opened"].to_list()
    closed: list[Any] = issue_metrics["issues_closed"].to_list()

    options = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Opened", "Closed"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {"type": "value", "minInterval": 1},
        "series": [
            {
                "name": "Opened",
                "type": "line",
                "data": opened,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": WARNING},
            },
            {
                "name": "Closed",
                "type": "line",
                "data": closed,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": CLOSED},
            },
        ],
    }
    st_echarts(options, height="360px")


def render_issue_close_rate(issue_metrics: DataFrame, overall_mean: float | None = None) -> None:
    """Line chart: issue close rate over time with period-average markLine."""
    if issue_metrics.is_empty():
        st.info(body="No issue data for the current selection.")
        return

    days: list[Any] = issue_metrics["day"].dt.strftime(format="%Y-%m-%d").to_list()
    rates_pct = [
        round(number=r * 100, ndigits=1) if r is not None else None
        for r in issue_metrics["avg_close_rate"].to_list()
    ]

    legend: list[str] = ["Close rate"]
    series = [
        {
            "name": "Close rate",
            "type": "line",
            "data": rates_pct,
            "smooth": True,
            "lineStyle": {"width": 2},
            "itemStyle": {"color": INFO},
            "areaStyle": {"opacity": 0.15},
        },
    ]

    if overall_mean is not None:
        mean_pct: int | float = round(number=overall_mean * 100, ndigits=1)
        legend.append("Period avg")
        series.append(
            {
                "name": "Period avg",
                "type": "line",
                "data": [],
                "lineStyle": {"width": 0},
                "symbol": "none",
                "markLine": {
                    "silent": True,
                    "data": [
                        {
                            "yAxis": mean_pct,
                        }
                    ],
                    "symbol": "none",
                },
            }
        )

    options = {
        "tooltip": {"trigger": "axis", "formatter": "{b}<br/>Close rate: {c}%"},
        "legend": {"data": legend, "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
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
            "axisLabel": {"formatter": "{value}%"},
        },
        "series": series,
    }
    st_echarts(options, height="360px")
