"""
Color palette for GitPulse Analytics charts.

Centralises all ECharts colours so the dashboard keeps a consistent, modern, and professional look.
"""

# Tailwind-inspired palette: clean, modern, professional
EVENT_COLORS: dict[str, str] = {
    "Push": "#3B82F6",
    "Pull Request": "#10B981",
    "Issue": "#F59E0B",
    "Watch/Star": "#EF4444",
    "Fork": "#06B6D4",
    "Release": "#8B5CF6",
    "Comment": "#F97316",
    "Review": "#EC4899",
}

# Semantic aliases: readable intent over raw hex
PRIMARY = "#3B82F6"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
INFO = "#06B6D4"
VIOLET = "#8B5CF6"
ORANGE = "#F97316"
PINK = "#EC4899"

# Paired chart colours
HUMAN = "#3B82F6"
BOT = "#F97316"
OPENED = "#3B82F6"
MERGED = "#10B981"
CLOSED = "#10B981"

# Health scorecard
HEALTH_GOOD = "#10B981"
HEALTH_MEDIUM = "#F59E0B"
HEALTH_LOW = "#EF4444"
