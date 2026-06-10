"""
app.py — Footland Organic Social Analytics Dashboard
Entry point. Organic data only. No ad account data.
"""

import streamlit as st
from datetime import datetime, timezone
import threading

from config import LOG_FILE_PATH
from components.sidebar import render_sidebar
from views.facebook import render_facebook_dashboard
from views.instagram import render_instagram_dashboard
from views.boost import render_boost_tab, empty_boost_data
from views.analytics import render_analytics_tab
from views.login import render_login
from views.documentation import render_documentation
from components.skeleton import skeleton_boost_html
from components.chatbot import render_chatbot
import db


# ─── Background prefetch helpers ─────────────────────────────────────────────
def _prefetch_facebook(days, start, end):
    """Pre-populate Supabase cache for Facebook so tab switch is instant."""
    try:
        db.get_fb_audience(days, start, end)
        db.get_fb_engagement(days, start, end)
        db.get_fb_visibility(days, start, end)
        db.get_fb_posts(days, start, end)
        db.get_fb_post_totals(days, start, end)
        db.get_fb_conversations(days, start, end)
        db.get_fb_messaging_stats(days, start, end)
    except Exception as e:
        print(f"DEBUG prefetch facebook: {e}")


def _prefetch_instagram(days, start, end):
    """Pre-populate Supabase cache for Instagram so tab switch is instant."""
    try:
        db.get_ig_profile(days, start, end)
        db.get_ig_engagement(days, start, end)
        db.get_ig_posts(days, start, end)
        db.get_ig_post_totals(days, start, end)
    except Exception as e:
        print(f"DEBUG prefetch instagram: {e}")


def _prefetch_boost(days, start, end):
    """Pre-populate Supabase cache for Boost so tab switch is instant."""
    try:
        db.get_boost_insights(days, start, end)
        db.get_fb_demographics(days, start, end)
    except Exception as e:
        print(f"DEBUG prefetch boost: {e}")


def _start_prefetch(platform, days, start, end):
    """Start background threads to prefetch all OTHER platforms."""
    targets = []
    if platform != "Facebook":
        targets.append(_prefetch_facebook)
    if platform != "Instagram":
        targets.append(_prefetch_instagram)
    if platform != "Boost":
        targets.append(_prefetch_boost)
    for fn in targets:
        threading.Thread(target=fn, args=(days, start, end), daemon=True).start()

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Footland Analytics",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Auth guard ───────────────────────────────────────────────────────────────
if "user" not in st.session_state:
    render_login()
    st.stop()

# ─── Theme-aware CSS ─────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

_DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #0a0a0a !important; color: #ffffff !important; }

[data-testid="stSidebar"] { background: #111111 !important; border-right: 1px solid #222222 !important; }
[data-testid="stSidebar"] * { color: #eeeeee !important; }

[data-testid="stMainBlockContainer"] { background: transparent; }

[data-testid="metric-container"] {
    background: #161616; border: 1px solid #262626; border-radius: 16px;
    padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
[data-testid="metric-container"]:hover { transform: translateY(-2px); border-color: #E8420A; }
[data-testid="metric-container"] label,
[data-testid="metric-container"] [data-testid="stMetricLabel"] { color: #a1a1aa !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #ffffff !important; }

.stTabs [data-baseweb="tab-list"] { background: #161616; border-radius: 12px; padding: 4px; gap: 4px; width: 100%; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 20px; font-weight: 500; color: #a1a1aa !important; flex: 1; text-align: center; justify-content: center; }
.stTabs [aria-selected="true"] { background: #262626 !important; color: #E8420A !important; border: 1px solid #E8420A !important; }

.post-card { background: #161616; border: 1px solid #262626; border-radius: 16px; padding: 16px; margin-bottom: 12px; transition: border-color 0.2s, box-shadow 0.2s; }
.post-card:hover { border-color: #E8420A; box-shadow: 0 4px 20px rgba(232,66,10,0.15); }

.brand-header { font-size: 28px; font-weight: 700; background: linear-gradient(90deg, #E8420A, #FF6B35, #C1320A); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 4px; }
.brand-sub { font-size: 12px; color: #71717a; margin-bottom: 24px; }
.section-header { font-size: 18px; font-weight: 600; color: #ffffff; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(232,66,10,0.5); }

.stButton > button { background: linear-gradient(90deg, #E8420A, #C1320A) !important; color: white !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important; }
.stButton > button:hover { background: linear-gradient(90deg, #FF6B35, #E8420A) !important; box-shadow: 0 0 15px rgba(232,66,10,0.4); }

hr { border-color: #333333 !important; }
[data-testid="stRadio"] label[data-checked="true"] { color: #E8420A !important; }
[data-testid="stExpander"] { background: #111111; border: 1px solid #262626 !important; border-radius: 12px !important; }
[data-testid="stDataFrame"] { background: #111111; border-radius: 12px; }
p, span, li, label, h1, h2, h3 { color: #ffffff !important; }
small { color: #71717a !important; }

@media (max-width: 768px) {
  /* Reduce main padding on mobile */
  [data-testid="stMainBlockContainer"] { padding: 0.5rem 0.6rem !important; }
  /* KPI grid cards: 2 per row */
  div[style*="grid-template-columns:repeat(4"],
  div[style*="grid-template-columns:repeat(5"] { grid-template-columns: repeat(2, 1fr) !important; }
  /* Section headers smaller */
  div[style*="font-size:1.35rem"] { font-size: 1rem !important; }
  /* Summary bar wraps nicely */
  div[style*="display:flex;gap:2rem"] { gap: 0.8rem !important; flex-wrap: wrap !important; }
  /* Tabs scroll horizontally */
  .stTabs [data-baseweb="tab-list"] { width: 100% !important; overflow-x: auto !important; }
  /* Expander labels don't overflow */
  [data-testid="stExpander"] summary { font-size: 0.78rem !important; white-space: normal !important; }
}
</style>
"""

_LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] { background: #f5f7fa !important; color: #111827 !important; }

[data-testid="stSidebar"] { background: #ffffff !important; border-right: 1px solid #e5e7eb !important; }
[data-testid="stSidebar"] * { color: #111827 !important; }

[data-testid="stMainBlockContainer"] { background: transparent; }

[data-testid="metric-container"] {
    background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px;
    padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
[data-testid="metric-container"]:hover { transform: translateY(-2px); border-color: #E8420A; }
[data-testid="metric-container"] label,
[data-testid="metric-container"] [data-testid="stMetricLabel"] { color: #6b7280 !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #111827 !important; }

.stTabs [data-baseweb="tab-list"] { background: #e5e7eb; border-radius: 12px; padding: 4px; gap: 4px; width: 100%; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 20px; font-weight: 500; color: #6b7280 !important; flex: 1; text-align: center; justify-content: center; }
.stTabs [aria-selected="true"] { background: #ffffff !important; color: #E8420A !important; border: 1px solid #E8420A !important; }

.post-card { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 16px; margin-bottom: 12px; }
.post-card:hover { border-color: #E8420A; box-shadow: 0 4px 20px rgba(232,66,10,0.1); }

.brand-header { font-size: 28px; font-weight: 700; background: linear-gradient(90deg, #E8420A, #FF6B35, #C1320A); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 4px; }
.brand-sub { font-size: 12px; color: #6b7280; margin-bottom: 24px; }
.section-header { font-size: 18px; font-weight: 600; color: #111827; margin: 16px 0 12px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(232,66,10,0.5); }

.stButton > button { background: linear-gradient(90deg, #E8420A, #C1320A) !important; color: white !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important; }
.stButton > button:hover { background: linear-gradient(90deg, #FF6B35, #E8420A) !important; box-shadow: 0 0 15px rgba(232,66,10,0.3); }

hr { border-color: #e5e7eb !important; }
[data-testid="stRadio"] label[data-checked="true"] { color: #E8420A !important; }
[data-testid="stExpander"] { background: #ffffff; border: 1px solid #e5e7eb !important; border-radius: 12px !important; }
[data-testid="stDataFrame"] { background: #ffffff; border-radius: 12px; }
p, span, li, label, h1, h2, h3 { color: #111827 !important; }
small { color: #6b7280 !important; }

@media (max-width: 768px) {
  [data-testid="stMainBlockContainer"] { padding: 0.5rem 0.6rem !important; }
  div[style*="grid-template-columns:repeat(4"],
  div[style*="grid-template-columns:repeat(5"] { grid-template-columns: repeat(2, 1fr) !important; }
  div[style*="font-size:1.35rem"] { font-size: 1rem !important; }
  div[style*="display:flex;gap:2rem"] { gap: 0.8rem !important; flex-wrap: wrap !important; }
  .stTabs [data-baseweb="tab-list"] { width: 100% !important; overflow-x: auto !important; }
  [data-testid="stExpander"] summary { font-size: 0.78rem !important; white-space: normal !important; }
}

/* ── Override hardcoded dark inline styles in custom HTML cards ── */
/* Card backgrounds */
[style*="background:rgba(255,255,255,0.05)"] { background: #ffffff !important; box-shadow: 0 1px 4px rgba(0,0,0,0.08) !important; }
[style*="background:rgba(255,255,255,0.04)"] { background: #f9fafb !important; }
[style*="background:rgba(255,255,255,0.03)"] { background: #f3f4f6 !important; }

/* White/transparent text → dark text */
[style*="color:rgba(255,255,255,0.45)"] { color: #6b7280 !important; }
[style*="color:rgba(255,255,255,0.35)"] { color: #9ca3af !important; }
[style*="color:rgba(255,255,255,0.3)"]  { color: #9ca3af !important; }
[style*="color:rgba(255,255,255,0.4)"]  { color: #9ca3af !important; }
[style*="color:rgba(255,255,255,0.5)"]  { color: #6b7280 !important; }
[style*="color:rgba(255,255,255,0.6)"]  { color: #4b5563 !important; }
[style*="color:rgba(255,255,255,0.7)"]  { color: #374151 !important; }
[style*="color:rgba(255,255,255,0.75)"] { color: #374151 !important; }
[style*="color:rgba(255,255,255,0.8)"]  { color: #1f2937 !important; }
[style*="color:rgba(255,255,255,0.85)"] { color: #111827 !important; }
[style*="color:#ffffff"]                { color: #111827 !important; }
[style*="color:#fff;"]                  { color: #111827 !important; }
[style*="color:#eeeeee"]                { color: #374151 !important; }

/* Borders */
[style*="border-bottom:1px solid rgba(255,255,255,0.08)"] { border-bottom-color: #e5e7eb !important; }
[style*="border:1px solid rgba(255,255,255,0.08)"]        { border-color: #e5e7eb !important; }
[style*="border:1px solid rgba(255,255,255,0.1)"]         { border-color: #e5e7eb !important; }
[style*="border:1px solid rgba(255,255,255,0.12)"]        { border-color: #d1d5db !important; }
[style*="border-top:1px solid rgba(255,255,255,0.08)"]    { border-top-color: #e5e7eb !important; }

/* Backgrounds not covered by the 0.03/0.04/0.05 rules */
[style*="background:rgba(255,255,255,0.08)"] { background: #f1f5f9 !important; }

/* Specific dark section blocks */
[style*="background:rgba(232,66,10,0.08)"] { background: rgba(232,66,10,0.06) !important; }
[style*="background:rgba(232,66,10,0.15)"] { background: rgba(232,66,10,0.08) !important; }

/* Warning/info banners */
[style*="background:rgba(255,165,0,0.08)"]  { background: rgba(255,165,0,0.1) !important; }
[style*="background:rgba(255,165,0,0.12)"]  { background: rgba(255,165,0,0.1) !important; }
</style>
"""

st.markdown(_DARK_CSS if st.session_state.theme == "dark" else _LIGHT_CSS, unsafe_allow_html=True)

# ─── Mobile viewport fix ──────────────────────────────────────────────────────
st.markdown("""
<script>
(function() {
    var meta = document.querySelector('meta[name="viewport"]');
    if (!meta) {
        meta = document.createElement('meta');
        meta.name = 'viewport';
        document.head.appendChild(meta);
    }
    meta.content = 'width=device-width, initial-scale=1, maximum-scale=1';
})();
</script>
""", unsafe_allow_html=True)


# ─── Logging Helper ───────────────────────────────────────────────────────────
LOG_MAX_ENTRIES = 200  # keep the log bounded so it doesn't grow forever


def _trim_log(content: str, max_entries: int = LOG_MAX_ENTRIES) -> str:
    """Keep only the most recent `max_entries` records, preserving the header."""
    import re
    header, sep, rest = content.partition("## Session Log")
    if not sep:
        return content
    entries = re.split(r"(?=\n### \[)", rest)
    preamble, records = entries[0], entries[1:]
    if len(records) <= max_entries:
        return content
    return header + sep + preamble + "".join(records[-max_entries:])


def log_refresh(platform: str, period: str, status: str, notes: str = ""):
    """Appends a refresh entry to AI_CONTEXT_LOG.md, trimming old entries to keep it bounded."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n### [{timestamp} UTC] — Data Refresh\n"
        f"- **Platform:** {platform}\n"
        f"- **Period:** {period}\n"
        f"- **Status:** {status}\n"
    )
    if notes:
        entry += f"- **Notes:** {notes}\n"
    entry += "---\n"
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        trimmed = _trim_log(content)
        if trimmed != content:
            with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(trimmed)
    except Exception:
        pass


# ─── Sidebar ─────────────────────────────────────────────────────────────────
platform, period_label, days, start_date, end_date = render_sidebar(log_refresh)

# ─── Page Title ───────────────────────────────────────────────────────────────
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    _icon = {"Facebook": "🔵 Facebook", "Instagram": "📸 Instagram", "Boost": "🚀 Boost", "Google Analytics": "📊 Google Analytics", "Documentation": "📖 Documentation"}[platform]
    st.markdown(f"## {_icon} — {period_label}")
with col_t2:
    st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")

# ─── Dashboard routing ────────────────────────────────────────────────────────
if platform == "Documentation":
    render_documentation()
elif platform == "Facebook":
    render_facebook_dashboard(period_label, days, start_date, end_date, log_refresh)
    _start_prefetch("Facebook", days, start_date, end_date)
elif platform == "Instagram":
    render_instagram_dashboard(period_label, days, start_date, end_date, log_refresh)
    _start_prefetch("Instagram", days, start_date, end_date)
elif platform == "Google Analytics":
    # ── Google Analytics 4 ───────────────────────────────────────────────────
    from datetime import datetime as _gdt, timezone as _gtz, timedelta as _gtd
    if start_date and end_date:
        _ga4_start, _ga4_end = str(start_date), str(end_date)
    else:
        _ga4_today = _gdt.now(_gtz.utc).date()
        _ga4_end   = str(_ga4_today)
        _ga4_start = str(_ga4_today - _gtd(days=days - 1))
    try:
        from api.ga4 import fetch_all_ga4_data
        ga4_data = fetch_all_ga4_data(_ga4_start, _ga4_end)
    except Exception as _ga4_err:
        st.warning(f"⚠️ GA4: {_ga4_err}")
        ga4_data = {}
    render_analytics_tab(ga4_data, since=str(start_date) if start_date else "",
                         until=str(end_date) if end_date else "")
else:
    # ── Boost (paid campaigns) ────────────────────────────────────────────────
    from datetime import datetime as _bdt, timedelta as _btd, timezone as _btz

    # Compute previous equivalent period
    if start_date and end_date:
        _bs = _bdt.strptime(start_date, "%Y-%m-%d").date()
        _be = _bdt.strptime(end_date,   "%Y-%m-%d").date()
        _bspan = (_be - _bs).days + 1
        _prev_be = _bs - _btd(days=1)
        _prev_bs = _prev_be - _btd(days=_bspan - 1)
    else:
        _prev_be = _bdt.now(_btz.utc).date() - _btd(days=days)
        _prev_bs = _prev_be - _btd(days=days - 1)
    _b_prev_start, _b_prev_end = str(_prev_bs), str(_prev_be)

    @st.cache_data(ttl=None, show_spinner=False)
    def _cached_boost(days, start, end):
        try:
            return db.get_boost_insights(days, start, end)
        except Exception as e:
            print(f"DEBUG boost: fetch failed: {e}")
            return empty_boost_data()

    @st.cache_data(ttl=None, show_spinner=False)
    def _cached_boost_demo(days, start, end):
        try:
            return db.get_fb_demographics(days, start, end)
        except Exception as e:
            print(f"DEBUG boost demographics: fetch failed: {e}")
            return {}

    @st.cache_data(ttl=None, show_spinner=False)
    def _cached_adset_ad(days, start, end):
        try:
            return db.get_adset_ad_insights(days, start, end)
        except Exception as e:
            print(f"DEBUG adset/ad fetch failed: {e}")
            return {"adsets": [], "ads": []}

    # ── Skeleton placeholder — shown while data loads ─────────────────────────
    _skel_b = st.empty()
    _skel_b.markdown(skeleton_boost_html(), unsafe_allow_html=True)

    boost_data      = _cached_boost(days, start_date, end_date)
    prev_boost_data = _cached_boost(days, _b_prev_start, _b_prev_end)
    demo_data       = _cached_boost_demo(days, start_date, end_date)
    adset_ad_data   = _cached_adset_ad(days, start_date, end_date)

    # Data loaded — overwrite skeleton (more reliable than .empty() on Streamlit Cloud)
    _skel_b.markdown('<div style="display:none"></div>', unsafe_allow_html=True)

    render_boost_tab(boost_data, demo_data, prev_boost_data,
                     since=str(start_date) if start_date else "",
                     until=str(end_date)   if end_date   else "",
                     adset_ad_data=adset_ad_data)
    _start_prefetch("Boost", days, start_date, end_date)

# ─── AI Chatbot Assistant ─────────────────────────────────────────────────────
if st.session_state.get("chat_open"):
    render_chatbot()
