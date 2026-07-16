"""
Entrypoint with global sidebar filters and page navigation.

Pages are loaded on demand, only the active page fetches its data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from streamlit.navigation.page import StreamlitPage

# ensure the project root is importable from Streamlit execution
_project_root = Path(__file__).resolve().parent.parent
if str(object=_project_root) not in sys.path:
    sys.path.insert(0, str(object=_project_root))

from dashboard.components.sidebar import render as render_sidebar  # noqa: E402

st.set_page_config(page_title="GitPulse Analytics", layout="wide")

# render global sidebar filters (widgets persist across pages)
render_sidebar()

# define pages
overview: StreamlitPage = st.Page(
    page="pages/overview.py",
    title="Overview",
    icon=":material/home:",
    default=True,
)
community: StreamlitPage = st.Page(
    page="pages/community.py",
    title="Community & Activity",
    icon=":material/group:",
)
development: StreamlitPage = st.Page(
    page="pages/development.py",
    title="Code Quality",
    icon=":material/code:",
)
ecosystem: StreamlitPage = st.Page(
    page="pages/ecosystem.py",
    title="Ecosystem & Growth",
    icon=":material/trending_up:",
)
about: StreamlitPage = st.Page(
    page="pages/about.py",
    title="About",
    icon=":material/info:",
)

pg: StreamlitPage = st.navigation(
    pages=[
        overview,
        community,
        development,
        ecosystem,
        about,
    ]
)
pg.run()
