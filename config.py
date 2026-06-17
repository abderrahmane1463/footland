"""
config.py — Footland Dashboard Configuration & Constants
Strict Constraint: No ad account or paid benchmark data is ever used.
"""

import os

# ─── Meta Graph API ───────────────────────────────────────────────────────────
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Page Access Token — organic data (FB posts, insights, IG)
# Can be overridden via environment variable FOOTLAND_TOKEN
ACCESS_TOKEN = os.environ.get(
    "FOOTLAND_TOKEN",
    "EAAXdQDmFoT8BRYOvKeaEYk9az3iqKbDnlHks3hT5WZBKmMT8cXjO7D03YX3QOelqZCxHOjKmCbZBLx6rMi7vOrcRLMbYofDwfBbPd7TNOlE2ZCbnWPkEOQ9QZAIbzpNuqpFRP9OvX3LuZC4M1lZAuDszoCxwRkGfKmZBvdeZBr1fZCx41Tv9t7AZAsXhutOo7pQfPzrPSwUpZCy11mn70VINXyXwOvIZD"
)

# User Access Token — Marketing API only (Boost tab)
# Can be overridden via environment variable FOOTLAND_ADS_TOKEN
ADS_ACCESS_TOKEN = os.environ.get(
    "FOOTLAND_ADS_TOKEN",
    "EAAXdQDmFoT8BRVJ0R2CRwHDsjLiOKZA6B1OLQv2Wmzg0n0TGaZBShCnOJwrxsPZC9OFD7KZCZCrzEPCn2mabS4Xtt6M6nAcYZAPIMwG39ZBy5n6Dq1axERYaSgDg4yEB5ATZCCLxAcZBrmykPacCD2tmbThqUhsn55CZCxMn6c7StzYTMCiiIGuKkAa0XZBOiGZB1ulQ866PiY9T3KOlKgni"
)

# ─── Asset IDs ─────────────────────────────────────────────────────────────────
FACEBOOK_PAGE_ID = "144124252311741"
INSTAGRAM_USER_ID = "17841403000855491"

# ─── Boost — Footland campaign identification keywords ────────────────────────
# The ad account (act_765947885726761) manages multiple clients.
# A campaign is considered Footland if its name contains ANY of these strings.
# Update this list when the agency changes their naming convention.
FOOTLAND_CAMPAIGN_KEYWORDS = [
    "144124252311741",  # page ID  — post-boost campaigns
    "- FL -",           # agency code — brand/weekly campaigns
    "ON- FL",           # agency code variant
    "-FL-",             # agency code without spaces
    " FL -",            # agency code with leading space
    "Footland",         # explicit brand name
]

# ─── Blocklisted (Paid) Assets — NEVER query these ────────────────────────────
BLOCKED_AD_ACCOUNTS = ["act_765947885726761"]

# ─── Date Period Mapping ───────────────────────────────────────────────────────
# Simple rolling windows (days back from today). Calendar-based periods
# (Today, Yesterday, This Week, etc.) are computed dynamically in sidebar.py.
PERIOD_DAYS = {
    "Last 7 Days":  7,
    "Last 14 Days": 14,
    "Last 30 Days": 30,
    "Last 60 Days": 60,
    "Last 90 Days": 90,
}

# Calendar-based presets resolved to (start, end) in sidebar.py
CALENDAR_PERIODS = [
    "Today",
    "Yesterday",
    "This Week",
    "Last Week",
    "This Month",
    "Last Month",
    "This Quarter",
    "Last Quarter",
]

# ─── API Settings ──────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30        # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0         # exponential backoff multiplier
CACHE_TTL_SECONDS = 900     # 15 minutes

# ─── Facebook Insight Metrics ──────────────────────────────────────────────────
FB_AUDIENCE_METRICS = [
    "page_fans",
    "page_fan_adds",
    "page_fan_removes",
]

FB_ENGAGEMENT_METRICS = [
    "page_post_engagements",
    "page_actions_post_reactions_total",
]

# NOTE (2026-06-15): Meta deprecated page_impressions / page_impressions_unique /
# page_posts_impressions. Replacements: page_total_media_view_unique (unique reach,
# paid+organic) and page_media_view (total media views). page_views_total still valid.
FB_VISIBILITY_METRICS = [
    "page_total_media_view_unique",
    "page_media_view",
    "page_views_total",
]

# Fields to request for Facebook posts
FB_POST_FIELDS = "id,message,story,created_time,full_picture,shares,comments.summary(true).filter(stream),reactions.summary(true),attachments{type,media_type}"

# ─── Instagram Insight Metrics ─────────────────────────────────────────────────
IG_PROFILE_METRICS = [
    "impressions",
    "reach",
    "profile_views",
    "follower_count",
]

IG_ENGAGEMENT_METRICS = [
    "likes",
    "comments",
    "shares",
    "saves",
]

# Fields for Instagram media
IG_MEDIA_FIELDS = (
    "id,caption,media_type,thumbnail_url,media_url,permalink,"
    "timestamp,like_count,comments_count"
)

# ─── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "AI_CONTEXT_LOG.md")
