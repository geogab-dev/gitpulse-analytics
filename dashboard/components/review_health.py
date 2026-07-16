"""
Code Review Engagement: review and comment activity relative to PRs.

Uses streamlit_echarts for dual line charts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from polars import DataFrame
from streamlit_echarts import st_echarts

from dashboard.components._palette import ORANGE, PINK


def render_reviews_comments_per_day(review_data: DataFrame) -> None:
    """Dual line chart: review events and comment events per day."""
    if review_data.is_empty():
        st.info(body="No review data for the current selection.")
        return

    days: list[Any] = review_data["day"].dt.strftime(format="%Y-%m-%d").to_list()
    reviews: list[Any] = review_data["review_events"].to_list()
    comments: list[Any] = review_data["comment_events"].to_list()

    options = {
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["Reviews", "Comments"], "bottom": 0},
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
                "name": "Reviews",
                "type": "line",
                "data": reviews,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": PINK},
            },
            {
                "name": "Comments",
                "type": "line",
                "data": comments,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": ORANGE},
            },
        ],
    }
    st_echarts(options, height="320px")


def render_reviews_per_pr(review_data: DataFrame) -> None:
    """Line chart: reviews per PR ratio with target markLine."""
    if review_data.is_empty():
        st.info(body="No review data for the current selection.")
        return

    days: list[Any] = review_data["day"].dt.strftime("%Y-%m-%d").to_list()
    reviews: list[Any] = review_data["review_events"].to_list()
    prs: list[Any] = review_data["pr_events"].to_list()
    review_per_pr = [
        round(number=r / p, ndigits=2) if p and p > 0 else None
        for r, p in zip(reviews, prs, strict=False)
    ]

    options = {
        "tooltip": {"trigger": "axis", "formatter": "{b}<br/>Reviews/PR: {c}x"},
        "legend": {"data": ["Reviews/PR"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {"type": "value", "min": 0, "axisLabel": {"formatter": "{value}x"}},
        "series": [
            {
                "name": "Reviews/PR",
                "type": "line",
                "data": review_per_pr,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": PINK},
                "areaStyle": {"opacity": 0.15},
                "markLine": {
                    "silent": True,
                    "data": [{"yAxis": 1, "label": {"formatter": "Target {c}"}}],
                    "lineStyle": {"type": "dashed", "opacity": 0.4},
                    "symbol": "none",
                },
            }
        ],
    }
    st_echarts(options, height="320px")


def render_comments_per_pr(review_data: DataFrame) -> None:
    """Line chart: comments per PR ratio."""
    if review_data.is_empty():
        st.info(body="No review data for the current selection.")
        return

    days: list[Any] = review_data["day"].dt.strftime(format="%Y-%m-%d").to_list()
    comments: list[Any] = review_data["comment_events"].to_list()
    prs: list[Any] = review_data["pr_events"].to_list()
    comment_per_pr = [
        round(number=c / p, ndigits=2) if p and p > 0 else None
        for c, p in zip(comments, prs, strict=False)
    ]

    options = {
        "tooltip": {"trigger": "axis", "formatter": "{b}<br/>Comments/PR: {c}x"},
        "legend": {"data": ["Comments/PR"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": days,
            "boundaryGap": False,
            "axisLabel": {"rotate": 45, "fontSize": 10},
        },
        "yAxis": {"type": "value", "min": 0, "axisLabel": {"formatter": "{value}x"}},
        "series": [
            {
                "name": "Comments/PR",
                "type": "line",
                "data": comment_per_pr,
                "smooth": True,
                "lineStyle": {"width": 2},
                "itemStyle": {"color": ORANGE},
                "areaStyle": {"opacity": 0.15},
            }
        ],
    }
    st_echarts(options, height="320px")
