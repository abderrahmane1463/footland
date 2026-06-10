import base64
import pathlib
import streamlit as st
from datetime import datetime, timezone, timedelta

from config import PERIOD_DAYS, CALENDAR_PERIODS
import db


@st.cache_data(ttl=None, show_spinner=False)
def _get_health():
    try:
        result = db.load_fetched_at("ig_profile", "2026-01-01", "2026-12-31")
        # Just check if Supabase responds — any response means connection is OK
        import requests, os
        from dotenv import load_dotenv
        load_dotenv()
        resp = requests.get(
            f"{os.environ['SUPABASE_URL']}/rest/v1/metric_cache",
            headers={"apikey": os.environ["SUPABASE_KEY"], "Authorization": f"Bearer {os.environ['SUPABASE_KEY']}"},
            params={"limit": "1", "select": "id"},
            timeout=5,
        )
        if resp.status_code == 200:
            return {"status": "ok", "name": "Supabase connecte"}
        return {"status": "error", "message": f"Supabase HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def render_sidebar(log_refresh_fn):
    """
    Renders the sidebar and returns (platform, days, start_date, end_date).
    log_refresh_fn is called when the user clicks Refresh.
    """
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    with st.sidebar:
        _logo_path = pathlib.Path("assets/footland_logo.png")
        if _logo_path.exists():
            _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
            st.markdown(
                f'<div style="background:#fff;border-radius:12px;padding:12px 16px;'
                f'margin-bottom:8px;text-align:center;">'
                f'<img src="data:image/png;base64,{_logo_b64}" style="max-width:160px;width:100%;"/>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown('<div class="brand-header">⚽ Footland</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">Analytics Dashboard</div>', unsafe_allow_html=True)

        platform = st.radio("Platform", ["🔵 Facebook", "📸 Instagram", "🚀 Boost", "📊 Google Analytics", "📖 Documentation"], label_visibility="collapsed")
        if "Facebook" in platform:
            platform = "Facebook"
        elif "Instagram" in platform:
            platform = "Instagram"
        elif "Boost" in platform:
            platform = "Boost"
        elif "Google Analytics" in platform:
            platform = "Google Analytics"
        else:
            platform = "Documentation"

        period_options = (
            list(PERIOD_DAYS.keys())
            + ["─── Calendar ───"]
            + CALENDAR_PERIODS
            + ["─── Custom ───", "Custom Range"]
        )
        period_label = st.selectbox(
            "Date Range",
            period_options,
            index=2,  # default: Last 30 Days
            label_visibility="collapsed",
        )

        # Separators are non-selectable labels — skip back to default if chosen
        if period_label.startswith("───"):
            period_label = "Last 30 Days"

        today = datetime.now(timezone.utc).date()
        start_date, end_date = None, None

        if period_label == "Custom Range":
            c1, c2 = st.columns(2)
            start_val = c1.date_input("Start", today - timedelta(days=30))
            end_val = c2.date_input("End", today)
            start_date, end_date = str(start_val), str(end_val)
            days = (end_val - start_val).days

        elif period_label in PERIOD_DAYS:
            days = PERIOD_DAYS[period_label]

        else:
            # ── Calendar-based periods ────────────────────────────────────────
            import calendar as _cal

            def _quarter(d):
                return (d.month - 1) // 3 + 1

            if period_label == "Today":
                s, e = today, today
            elif period_label == "Yesterday":
                s = today - timedelta(days=1)
                e = s
            elif period_label == "This Week":
                s = today - timedelta(days=today.weekday())   # Monday
                e = today
            elif period_label == "Last Week":
                e = today - timedelta(days=today.weekday() + 1)  # last Sunday
                s = e - timedelta(days=6)                         # last Monday
            elif period_label == "This Month":
                s = today.replace(day=1)
                e = today
            elif period_label == "Last Month":
                e = today.replace(day=1) - timedelta(days=1)
                s = e.replace(day=1)
            elif period_label == "This Quarter":
                q = _quarter(today)
                s = today.replace(month=(q - 1) * 3 + 1, day=1)
                e = today
            elif period_label == "Last Quarter":
                q = _quarter(today)
                lq = q - 1 if q > 1 else 4
                lq_year = today.year if q > 1 else today.year - 1
                s = today.replace(year=lq_year, month=(lq - 1) * 3 + 1, day=1)
                last_month = (lq - 1) * 3 + 3
                _, last_day = _cal.monthrange(lq_year, last_month)
                e = today.replace(year=lq_year, month=last_month, day=last_day)
            else:
                s, e = today - timedelta(days=30), today

            start_date, end_date = str(s), str(e)
            days = (e - s).days or 1

        if st.button("🔄 Refresh Data", width="stretch"):
            from api.base import _cache_key_range as _ckr
            ck_start, ck_end = _ckr(days, start_date, end_date)
            db.invalidate(platform, ck_start, ck_end)
            st.cache_data.clear()
            log_refresh_fn(platform, period_label, "🔄 Manual Refresh Triggered")
            st.rerun()

        if "theme" not in st.session_state:
            st.session_state.theme = "dark"

        _is_admin = st.session_state.get("user", {}).get("role") == "admin"

        if _is_admin:
            st.divider()

            health = _get_health()
            if health.get("status") == "ok":
                st.success(f"✅ Base de donnees connectee")
            else:
                st.error(f"❌ Erreur\n\n{health.get('message', 'Unknown error')}")

            st.caption("Cache permanent • Supabase")

        st.divider()

        if st.button(
            "✕ Fermer l'assistant" if st.session_state.chat_open else "💬 Assistant IA",
            width="stretch",
        ):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()

        if st.session_state.chat_open and st.session_state.chat_history:
            if st.button("🗑️ Effacer la conversation", width="stretch"):
                st.session_state.chat_history = []
                st.rerun()

        st.divider()

        user = st.session_state.get("user", {})
        if _is_admin:
            st.caption(f"Connecté : {user.get('display_name') or user.get('email', '')}")
        if st.button("🚪 Se déconnecter", width="stretch"):
            del st.session_state["user"]
            st.rerun()

    return platform, period_label, days, start_date, end_date
