"""
views/boost.py — Boost (Ads Performance) dashboard tab.

Data contract
─────────────
All functions accept a `data` dict whose shape mirrors what the
Meta Marketing API (v19.0) would return.  Pass the placeholder
produced by `empty_boost_data()` until the real API integration
is wired up.

TODO: replace `empty_boost_data()` calls in views/facebook.py with
      a call to api/boost.py → fetch_boost_insights(ad_account_id, since, until)
      once the Marketing API access token is available.
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.charts import get_chart_layout
from api.boost import fetch_reach_for_ids


def _df_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "Campagnes") -> bytes:
    """Serialize a DataFrame to .xlsx bytes for st.download_button."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buffer.getvalue()


@st.cache_data(ttl=900, show_spinner=False)
def _cached_reach_for_ids(camp_ids: tuple, since: str, until: str) -> int:
    return fetch_reach_for_ids(camp_ids, since, until)


# ─── Placeholder data structure ───────────────────────────────────────────────
def empty_boost_data() -> dict:
    """
    Returns a zero-filled data structure that matches the shape expected by
    render_boost_tab().  Replace this with real Meta Marketing API data.

    Shape reference (Meta Marketing API fields):
      campaigns[*].insights → impressions, reach, clicks (link_clicks),
                               spend, cpc, ctr, frequency,
                               actions[action_type=purchase].value,
                               cost_per_action_type[action_type=purchase].value
    """
    return {
        # ── Totals across all active campaigns ──────────────────────────────
        # TODO: aggregate from ad_account/insights?fields=impressions,reach,
        #       clicks,spend,cpc,ctr,frequency&date_preset=...
        "totals": {
            "campaigns_count":  0,
            "link_clicks":      0,
            "reach":            0,
            "impressions":      0,
            "cpc":              0.0,   # €
            "ctr":              0.0,   # %
            "spend":            0.0,   # €
            "frequency":        0.0,
        },

        # ── Conversion-objective campaigns only ──────────────────────────────
        # TODO: filter by effective_status=ACTIVE & objective=CONVERSIONS
        "conversions": {
            "campaigns_count":       0,
            "link_clicks":           0,
            "reach":                 0,
            "impressions":           0,
            "cpc":                   0.0,
            "ctr":                   0.0,
            "spend":                 0.0,
            "frequency":             0.0,
            "cost_per_conversion":   0.0,  # cost_per_action_type[purchase]
            "total_conversions":     0,    # actions[purchase]
        },

        # ── Per-campaign detail (used for Top Campaigns chart) ───────────────
        # TODO: /act_{ad_account_id}/campaigns?fields=name,objective,
        #       insights{impressions,reach,clicks,spend,actions,cpc,ctr}
        "campaigns": [
            # {
            #     "name":        "Nom de la campagne",
            #     "objective":   "CONVERSIONS",
            #     "spend":       0.0,
            #     "conversions": 0,
            #     "cpa":         0.0,
            #     "clicks":      0,
            #     "reach":       0,
            # }
        ],
    }


# ─── Internal helpers ──────────────────────────────────────────────────────────
def _fmt_currency(value: float) -> str:
    return f"€{value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def _fmt_int(value: int) -> str:
    return f"{value:,}"


def _kpi_card(icon: str, label: str, value: str, color: str | None = None,
              delta: float | None = None, lower_is_better: bool = False) -> str:
    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg  = "rgba(255,255,255,0.05)" if _dark else "#ffffff"
    _brd = "none"                    if _dark else "1px solid #e5e7eb"
    _lc  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _vc  = color if color else ("#ffffff" if _dark else "#111827")
    if delta is not None:
        _good = (delta < 0) if lower_is_better else (delta > 0)
        _dc   = "#4ade80" if _good else "#f87171" if delta != 0 else "#a1a1aa"
        _arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
        _sign  = "+" if delta > 0 else ""
        _delta_html = (
            f'<div style="font-size:0.65rem;color:{_dc};margin-top:0.15rem;">'
            f'{_arrow} {_sign}{delta:.1f}%</div>'
        )
    else:
        _delta_html = ""
    return (
        f'<div style="background:{_bg};border:{_brd};border-radius:12px;'
        f'padding:0.9rem 1rem;text-align:center;">'
        f'<div style="font-size:0.72rem;color:{_lc};'
        f'margin-bottom:0.25rem;">{icon} {label}</div>'
        f'<div style="font-size:1.3rem;font-weight:800;color:{_vc};'
        f'white-space:nowrap;">{value}</div>'
        f'{_delta_html}'
        f'</div>'
    )


def _no_data_banner(msg: str = "Aucune donnée publicitaire disponible pour cette période."):
    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg  = "rgba(255,165,0,0.08)"  if _dark else "rgba(255,165,0,0.12)"
    _tc  = "rgba(255,165,0,0.9)"   if _dark else "#92400e"
    st.markdown(
        f'<div style="background:{_bg};border:1px solid rgba(255,165,0,0.3);'
        f'border-radius:10px;padding:1rem 1.2rem;color:{_tc};'
        f'font-size:0.85rem;margin:0.5rem 0 1rem;">'
        f'⚠️ {msg}</div>',
        unsafe_allow_html=True,
    )


def _section_header(title: str, big: bool = True):
    _brd = "rgba(255,255,255,0.15)"
    st.markdown(
        f'<div style="font-size:1.35rem;color:#ffffff;font-weight:700;'
        f'letter-spacing:0.05em;'
        f'margin:1.8rem 0 0.8rem;border-bottom:2px solid {_brd};'
        f'padding-bottom:0.5rem;">{title}</div>',
        unsafe_allow_html=True,
    )


# ─── Section renderers ─────────────────────────────────────────────────────────
def _render_global_kpis(totals: dict, prev_totals: dict | None = None):
    """Top-level ad account KPI row."""
    _section_header("📊 STATISTIQUES DU BOOST", big=True)

    no_data = totals.get("campaigns_count", 0) == 0
    pt = prev_totals or {}

    def _d(curr, prev):
        try:
            return round((curr - prev) / abs(prev) * 100, 1) if prev else None
        except Exception:
            return None

    row1 = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:0.5rem;">
  {_kpi_card("📁", "Total des campagnes", _fmt_int(totals.get("campaigns_count", 0)),
             delta=_d(totals.get("campaigns_count",0), pt.get("campaigns_count",0)))}
  {_kpi_card("🖱️", "Clics sur le lien",  _fmt_int(totals.get("link_clicks", 0)),
             delta=_d(totals.get("link_clicks",0), pt.get("link_clicks",0)))}
  {_kpi_card("👁️", "Comptes touchés",    _fmt_int(totals.get("reach", 0)),
             delta=_d(totals.get("reach",0), pt.get("reach",0)))}
  {_kpi_card("📢", "Impressions",         _fmt_int(totals.get("impressions", 0)),
             delta=_d(totals.get("impressions",0), pt.get("impressions",0)))}
</div>"""

    row2 = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("💸", "Coût par clic",   _fmt_currency(totals.get("cpc", 0.0)),   "#facc15",
             delta=_d(totals.get("cpc",0.0), pt.get("cpc",0.0)),   lower_is_better=True)}
  {_kpi_card("📈", "CTR",             _fmt_pct(totals.get("ctr", 0.0)),         "#4ade80",
             delta=_d(totals.get("ctr",0.0), pt.get("ctr",0.0)))}
  {_kpi_card("💰", "Montant dépensé", _fmt_currency(totals.get("spend", 0.0)), "#f97316",
             delta=_d(totals.get("spend",0.0), pt.get("spend",0.0)), lower_is_better=True)}
  {_kpi_card("🔁", "Répétition",      f"{totals.get('frequency', 0.0):.2f}x",
             delta=_d(totals.get("frequency",0.0), pt.get("frequency",0.0)), lower_is_better=True)}
</div>"""

    st.markdown(row1 + row2, unsafe_allow_html=True)

    if no_data:
        _no_data_banner(
            "Données Marketing API non connectées. "
            "Connectez votre compte publicitaire pour afficher vos KPIs."
        )


def _render_conversion_campaigns(conv: dict, prev_conv: dict | None = None):
    """Conversion-objective campaigns subsection."""
    _section_header("🎯 AVEC L'OBJECTIF CONVERSION", big=True)

    no_data = conv.get("campaigns_count", 0) == 0
    pc = prev_conv or {}

    def _d(curr, prev):
        try:
            return round((curr - prev) / abs(prev) * 100, 1) if prev else None
        except Exception:
            return None

    row1 = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:0.5rem;">
  {_kpi_card("📁", "Campagnes",         _fmt_int(conv.get("campaigns_count", 0)),
             delta=_d(conv.get("campaigns_count",0), pc.get("campaigns_count",0)))}
  {_kpi_card("🖱️", "Clics sur le lien", _fmt_int(conv.get("link_clicks", 0)),
             delta=_d(conv.get("link_clicks",0), pc.get("link_clicks",0)))}
  {_kpi_card("👁️", "Comptes touchés",   _fmt_int(conv.get("reach", 0)),
             delta=_d(conv.get("reach",0), pc.get("reach",0)))}
  {_kpi_card("📢", "Impressions",        _fmt_int(conv.get("impressions", 0)),
             delta=_d(conv.get("impressions",0), pc.get("impressions",0)))}
</div>"""

    row2 = f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.6rem;margin-bottom:0.5rem;">
  {_kpi_card("💸", "Coût par clic",    _fmt_currency(conv.get("cpc", 0.0)),                "#facc15",
             delta=_d(conv.get("cpc",0.0), pc.get("cpc",0.0)),                   lower_is_better=True)}
  {_kpi_card("📈", "CTR",              _fmt_pct(conv.get("ctr", 0.0)),                     "#4ade80",
             delta=_d(conv.get("ctr",0.0), pc.get("ctr",0.0)))}
  {_kpi_card("💰", "Montant dépensé",  _fmt_currency(conv.get("spend", 0.0)),              "#f97316",
             delta=_d(conv.get("spend",0.0), pc.get("spend",0.0)),               lower_is_better=True)}
  {_kpi_card("🎁", "Coût par vente",   _fmt_currency(conv.get("cost_per_conversion",0.0)),"#fb7185",
             delta=_d(conv.get("cost_per_conversion",0.0), pc.get("cost_per_conversion",0.0)), lower_is_better=True)}
  {_kpi_card("✅", "Commandes (conv.)", _fmt_int(conv.get("total_conversions", 0)),         "#a78bfa",
             delta=_d(conv.get("total_conversions",0), pc.get("total_conversions",0)))}
</div>"""

    st.markdown(row1 + row2, unsafe_allow_html=True)

    if no_data:
        _no_data_banner("Aucune campagne de conversion détectée pour la période sélectionnée.")


def _render_funnel(totals: dict, campaigns: list[dict]):
    """Conversion funnel: Impressions → Clicks → LP Views → Add to Cart → Checkout → Purchases."""
    _section_header("🔁 FUNNEL DE CONVERSION")

    imp    = totals.get("impressions", 0)
    clicks = totals.get("link_clicks", 0)
    lp     = totals.get("landing_page_views", 0) or sum(c.get("landing_page_views", 0) for c in campaigns)
    cart   = totals.get("adds_to_cart", 0)        or sum(c.get("adds_to_cart", 0)       for c in campaigns)
    chk    = totals.get("checkouts", 0)            or sum(c.get("checkouts", 0)           for c in campaigns)
    conv   = totals.get("purchases", 0)            or sum(c.get("conversions", 0)         for c in campaigns)

    stages = ["Impressions", "Clics", "Pages vues", "Ajouts panier", "Checkouts", "Achats"]
    values = [imp, clicks, lp, cart, chk, conv]

    # Drop trailing zero stages (e.g. if pixel not set up)
    last_nonzero = max((i for i, v in enumerate(values) if v > 0), default=1)
    stages = stages[:last_nonzero + 1]
    values = values[:last_nonzero + 1]

    if not any(v > 0 for v in values):
        _no_data_banner("Données funnel non disponibles pour cette période.")
        return

    _dark      = st.session_state.get("theme", "dark") == "dark"
    _bar_color = "#E8420A"
    _txt_color = "#ffffff" if _dark else "#111827"
    _sub_color = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _bg        = "rgba(255,255,255,0.03)" if _dark else "#f9fafb"
    _brd       = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"

    # Build HTML funnel bars
    max_val = max(values) or 1
    rows_html = ""
    for i, (stage, val) in enumerate(zip(stages, values)):
        bar_pct  = round(val / max_val * 100, 1)
        drop_pct = round((values[i - 1] - val) / values[i - 1] * 100, 1) if i > 0 and values[i - 1] > 0 else None
        drop_html = (
            f'<span style="font-size:0.65rem;color:#f87171;margin-left:0.5rem;">▼ -{drop_pct}%</span>'
            if drop_pct is not None else ""
        )
        rows_html += (
            f'<div style="margin-bottom:0.6rem;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">'
            f'<span style="font-size:0.78rem;color:{_txt_color};font-weight:600;">{stage}{drop_html}</span>'
            f'<span style="font-size:0.78rem;color:{_sub_color};">{val:,}</span>'
            f'</div>'
            f'<div style="background:{_brd};border-radius:6px;height:10px;">'
            f'<div style="background:{_bar_color};width:{bar_pct}%;height:10px;border-radius:6px;'
            f'transition:width 0.4s ease;"></div>'
            f'</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="background:{_bg};border:1px solid {_brd};border-radius:12px;padding:1.2rem 1.4rem;">'
        f'{rows_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_acquisition_kpis(totals: dict, campaigns: list[dict]):
    """ROAS + Landing Page CVR + Cart Abandonment + Purchase Rate."""
    _section_header("💡 KPIs D'ACQUISITION")

    clicks  = totals.get("link_clicks", 0)
    lp      = totals.get("landing_page_views", 0) or sum(c.get("landing_page_views", 0) for c in campaigns)
    cart    = totals.get("adds_to_cart", 0)        or sum(c.get("adds_to_cart", 0)       for c in campaigns)
    chk     = totals.get("checkouts", 0)            or sum(c.get("checkouts", 0)           for c in campaigns)
    conv    = totals.get("purchases", 0)            or sum(c.get("conversions", 0)         for c in campaigns)
    roas    = totals.get("roas", 0.0)

    lp_cvr        = round(lp  / clicks * 100, 2) if clicks else 0.0
    cart_abandon  = round((1 - chk / cart) * 100, 2) if cart else 0.0
    purchase_rate = round(conv / chk * 100, 2)        if chk  else 0.0

    row = f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("🛬", "LP Conversion", _fmt_pct(lp_cvr), "#7dd3fc")}
  {_kpi_card("🛒", "Abandon panier", _fmt_pct(cart_abandon), "#f87171", lower_is_better=True)}
  {_kpi_card("💳", "Taux d'achat", _fmt_pct(purchase_rate), "#a78bfa")}
</div>"""
    st.markdown(row, unsafe_allow_html=True)

    if lp_cvr == 0 and cart_abandon == 0 and purchase_rate == 0:
        _no_data_banner("KPIs d'acquisition non disponibles — vérifiez que le Meta Pixel est actif sur le site.")


def _render_by_objective(campaigns: list[dict], obj_reach: dict | None = None,
                         period: dict | None = None):
    """Single KPI block aggregated from selected objectives (multiselect filter).
    Reach is fetched dynamically with a single deduplicated API call for selected campaigns."""
    _section_header("🗂️ PAR OBJECTIF")
    obj_reach = obj_reach or {}
    since = (period or {}).get("since", "")
    until = (period or {}).get("until", "")

    # Keep only campaigns with activity
    active = [c for c in campaigns if c.get("spend", 0) > 0 or c.get("impressions", 0) > 0]
    if not active:
        _no_data_banner("Aucune campagne active pour afficher la répartition par objectif.")
        return

    # Friendly labels
    _OBJ_LABELS = {
        "OUTCOME_SALES":         "🛒 Ventes",
        "OUTCOME_TRAFFIC":       "🚦 Trafic",
        "OUTCOME_AWARENESS":     "📣 Notoriété",
        "OUTCOME_ENGAGEMENT":    "💬 Engagement",
        "OUTCOME_LEADS":         "🎯 Leads",
        "OUTCOME_APP_PROMOTION": "📱 App",
        "CONVERSIONS":           "🛒 Conversions",
        "LINK_CLICKS":           "🚦 Clics sur le lien",
        "REACH":                 "📣 Portée",
        "BRAND_AWARENESS":       "📣 Notoriété de la marque",
        "VIDEO_VIEWS":           "▶️ Vues de vidéo",
        "LEAD_GENERATION":       "🎯 Génération de leads",
        "MESSAGES":              "💬 Messages",
        "APP_INSTALLS":          "📱 Installations d'app",
        "PAGE_LIKES":            "👍 Mentions J'aime",
        "EVENT_RESPONSES":       "📅 Réponses événements",
        "POST_ENGAGEMENT":       "💬 Engagement posts",
        "STORE_VISITS":          "🏪 Visites en magasin",
        "PRODUCT_CATALOG_SALES": "🛒 Ventes catalogue",
    }

    # Unique objectives in data sorted by spend
    seen = {}
    for c in sorted(active, key=lambda x: x.get("spend", 0), reverse=True):
        obj = c.get("objective", "—")
        if obj not in seen:
            seen[obj] = _OBJ_LABELS.get(obj, obj)
    all_objectives = list(seen.keys())
    all_labels     = [seen[o] for o in all_objectives]

    selected_labels = st.multiselect(
        "Filtrer par objectif",
        options=all_labels,
        default=all_labels,
        label_visibility="collapsed",
        placeholder="Sélectionner les objectifs à afficher…",
        key="obj_filter_by_objective",
    )

    selected_objectives = [o for o, l in zip(all_objectives, all_labels) if l in selected_labels]

    if not selected_objectives:
        st.caption("Aucun objectif sélectionné.")
        return

    # Aggregate across all selected objectives
    group        = [c for c in active if c.get("objective") in selected_objectives]
    total_spend  = sum(c.get("spend", 0.0)       for c in group)
    total_clicks = sum(c.get("link_clicks", 0)    for c in group)   # inline_link_clicks
    total_imp    = sum(c.get("impressions", 0)    for c in group)
    total_conv   = sum(c.get("conversions", 0)    for c in group)
    n_camps      = len(group)
    # Single deduplicated API call for all selected campaign IDs combined
    selected_ids = tuple(
        c.get("campaign_id", "") for c in group if c.get("campaign_id")
    )
    if selected_ids and since and until:
        total_reach = _cached_reach_for_ids(selected_ids, since, until)
    else:
        # Fallback: sum pre-computed per-objective reach from API
        total_reach = sum(obj_reach.get(obj, 0) for obj in selected_objectives)

    w_ctr = round(total_clicks / total_imp * 100, 2) if total_imp   > 0 else 0.0
    w_cpc = round(total_spend  / total_clicks,    2) if total_clicks > 0 else 0.0
    w_cpa = round(total_spend  / total_conv,      2) if total_conv   > 0 else 0.0

    row1 = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:0.5rem;">
  {_kpi_card("📁", "Campagnes",         _fmt_int(n_camps))}
  {_kpi_card("🖱️", "Clics sur le lien", _fmt_int(total_clicks))}
  {_kpi_card("👁️", "Comptes touchés",   _fmt_int(total_reach))}
  {_kpi_card("📢", "Impressions",        _fmt_int(total_imp))}
</div>"""

    row2 = f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("💸", "Coût par clic",   _fmt_currency(w_cpc),       "#facc15", lower_is_better=True)}
  {_kpi_card("📈", "CTR",             _fmt_pct(w_ctr),             "#4ade80")}
  {_kpi_card("💰", "Montant dépensé", _fmt_currency(total_spend),  "#f97316", lower_is_better=True)}
  {_kpi_card("🎁", "Coût par vente",  _fmt_currency(w_cpa),        "#fb7185", lower_is_better=True)}
  {_kpi_card("✅", "Commandes",       _fmt_int(total_conv),         "#a78bfa")}
</div>"""

    st.markdown(row1 + row2, unsafe_allow_html=True)


def _render_top_campaigns(campaigns: list[dict]):
    """Top-3 campaigns podium cards — mirrors the report's slide 39 layout."""
    _section_header("🏆 TOP #3 CAMPAGNES PAR VENTES")

    if not campaigns:
        _no_data_banner("Aucune campagne à afficher.")
        return

    # Sort by commandes (conversions) desc, take top 3
    top = sorted(campaigns, key=lambda c: c.get("conversions", 0), reverse=True)[:3]

    # Fall back to spend ranking when no conversions are recorded
    use_commandes = any(c.get("conversions", 0) > 0 for c in top)
    if not use_commandes:
        top = sorted(campaigns, key=lambda c: c.get("spend", 0.0), reverse=True)[:3]

    # Pad to always have 3 slots
    while len(top) < 3:
        top.append({"name": "—", "conversions": 0, "spend": 0.0, "cpa": 0.0})

    # Podium style: #1 gold, #2 silver, #3 bronze
    _ranks = [
        ("#1", "#FFD700", "rgba(255,215,0,0.12)",  "rgba(255,215,0,0.35)"),   # gold
        ("#2", "#C0C0C0", "rgba(192,192,192,0.10)", "rgba(192,192,192,0.30)"), # silver
        ("#3", "#CD7F32", "rgba(205,127,50,0.10)",  "rgba(205,127,50,0.30)"),  # bronze
    ]

    _dark = st.session_state.get("theme", "dark") == "dark"
    _name_c  = "rgba(255,255,255,0.75)" if _dark else "#1f2937"
    _meta_c  = "rgba(255,255,255,0.4)"  if _dark else "#9ca3af"
    _div_brd = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"
    _sub_lc  = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"
    _sub_vc  = "rgba(255,255,255,0.7)"  if _dark else "#374151"

    cards_html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:0.5rem 0 1rem;">'

    for i, c in enumerate(top):
        rank_label, rank_color, bg_color, border_color = _ranks[i]
        name = c["name"]
        # Truncate long names to two lines visually
        display_name = name if len(name) <= 40 else name[:38] + "…"

        if use_commandes:
            metric_value = f"{c.get('conversions', 0):,}"
            metric_label = "commandes"
        else:
            metric_value = _fmt_currency(c.get("spend", 0.0))
            metric_label = "dépensé"

        spend_str = _fmt_currency(c.get("spend", 0.0))
        cpa_str   = _fmt_currency(c.get("cpa", 0.0))

        cards_html += f"""
<div style="background:{bg_color};border:1px solid {border_color};border-radius:14px;
            padding:1.2rem 1rem;text-align:center;position:relative;display:flex;
            flex-direction:column;align-items:center;gap:0.4rem;">
  <div style="font-size:1.6rem;font-weight:900;color:{rank_color};
              line-height:1;margin-bottom:0.2rem;">{rank_label}</div>
  <div style="font-size:0.78rem;color:{_name_c};font-weight:600;
              line-height:1.35;min-height:2.7rem;display:flex;align-items:center;
              justify-content:center;">{display_name}</div>
  <div style="font-size:2rem;font-weight:900;color:{rank_color};
              line-height:1.1;margin:0.3rem 0 0.1rem;">{metric_value}</div>
  <div style="font-size:0.7rem;color:{_meta_c};
              text-transform:uppercase;letter-spacing:0.06em;">{metric_label}</div>
  <div style="margin-top:0.5rem;width:100%;border-top:1px solid {_div_brd};
              padding-top:0.5rem;display:flex;justify-content:space-around;">
    <div style="text-align:center;">
      <div style="font-size:0.68rem;color:{_sub_lc};">Dépensé</div>
      <div style="font-size:0.82rem;font-weight:700;color:{_sub_vc};">{spend_str}</div>
    </div>
    <div style="text-align:center;">
      <div style="font-size:0.68rem;color:{_sub_lc};">Coût / vente</div>
      <div style="font-size:0.82rem;font-weight:700;color:{_sub_vc};">{cpa_str}</div>
    </div>
  </div>
</div>"""

    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


def _render_insights_panel(totals: dict, conv: dict):
    """Automated interpretation: CTR, CPC efficiency, conversion rate."""
    _section_header("🧠 Analyse automatique")

    ctr   = totals.get("ctr", 0.0)
    cpc   = totals.get("cpc", 0.0)
    cpa   = conv.get("cost_per_conversion", 0.0)
    clicks = totals.get("link_clicks", 0)
    total_conv = conv.get("total_conversions", 0)
    cvr   = round(total_conv / clicks * 100, 2) if clicks else 0.0

    insights: list[tuple[str, str, str]] = []

    # CTR benchmark (Meta average: 0.9–1.5 % for feed ads)
    if ctr == 0:
        insights.append(("⚪", "CTR", "Données non disponibles."))
    elif ctr >= 2.0:
        insights.append(("🟢", "CTR excellent",  f"{_fmt_pct(ctr)} — bien au-dessus de la moyenne (>2 %)."))
    elif ctr >= 1.0:
        insights.append(("🟡", "CTR correct",    f"{_fmt_pct(ctr)} — dans la norme (1–2 %). Optimisation possible."))
    else:
        insights.append(("🔴", "CTR faible",     f"{_fmt_pct(ctr)} — en dessous de 1 %. Revoir les visuels / ciblage."))

    # CPC benchmark
    if cpc == 0:
        insights.append(("⚪", "Coût par clic", "Données non disponibles."))
    elif cpc <= 0.50:
        insights.append(("🟢", "Coût par clic très efficace", f"{_fmt_currency(cpc)} — coût par clic très bas."))
    elif cpc <= 1.50:
        insights.append(("🟡", "Coût par clic modéré",        f"{_fmt_currency(cpc)} — acceptable selon le secteur."))
    else:
        insights.append(("🔴", "Coût par clic élevé",          f"{_fmt_currency(cpc)} — envisager d'affiner le ciblage."))

    # CPA
    if cpa > 0:
        insights.append(("💡", "Coût par vente", f"{_fmt_currency(cpa)} — comparez à la valeur moyenne d'une commande."))

    _dark  = st.session_state.get("theme", "dark") == "dark"
    _row_bg = "rgba(255,255,255,0.03)" if _dark else "#f8fafc"
    _lbl_c  = "rgba(255,255,255,0.75)" if _dark else "#111827"
    _txt_c  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"

    rows_html = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:0.6rem;'
        f'background:{_row_bg};border-radius:8px;'
        f'padding:0.55rem 0.8rem;margin-bottom:0.35rem;">'
        f'<span style="font-size:1rem;line-height:1.4;">{dot}</span>'
        f'<div><span style="font-size:0.78rem;font-weight:700;color:{_lbl_c};">{label}</span>'
        f'<span style="font-size:0.78rem;color:{_txt_c};"> — {text}</span></div>'
        f'</div>'
        for dot, label, text in insights
    )
    st.markdown(rows_html, unsafe_allow_html=True)


def _render_campaigns_table(campaigns: list[dict], adset_ad_data: dict | None = None):
    """All campaigns as expandable rows — each expands to show adsets, each adset expands to show ads."""
    _section_header("📋 Rapport Hebdomadaire Sales")

    if not campaigns:
        _no_data_banner("Aucune campagne à afficher pour cette période.")
        return

    # Keep only campaigns with actual activity
    total_all    = len(campaigns)
    campaigns    = [c for c in campaigns if c.get("spend", 0) > 0 or c.get("impressions", 0) > 0]
    total_active = len(campaigns)
    inactive     = total_all - total_active

    if not campaigns:
        _no_data_banner("Aucune campagne active pour cette période.")
        return

    # Build adset/ads lookup maps keyed by campaign_name
    adsets_by_campaign: dict[str, list] = {}
    ads_by_adset: dict[str, list] = {}
    if adset_ad_data:
        for a in adset_ad_data.get("adsets", []):
            cname = a.get("campaign_name", "")
            if cname:
                adsets_by_campaign.setdefault(cname, []).append(a)
        for a in adset_ad_data.get("ads", []):
            aid = a.get("adset_id", "")
            if aid:
                ads_by_adset.setdefault(str(aid), []).append(a)

    # ── Flat ads table — same columns as Meta CSV export ─────────────────────
    ads = (adset_ad_data or {}).get("ads", [])
    period = (adset_ad_data or {}).get("period", {})
    reporting_start = period.get("since", "—")
    reporting_end   = period.get("until", "—")

    # ── Shared column config (reused for flat table + expander tables) ────────
    def _csv_col_config():
        return {
            "Ad name":                              st.column_config.TextColumn("Ad name",                              width="large"),
            "Campaign name":                        st.column_config.TextColumn("Campaign name",                        width="large"),
            "Delivery status":                      st.column_config.TextColumn("Delivery status",                      width="medium"),
            "Delivery level":                       st.column_config.TextColumn("Delivery level",                       width="small"),
            "Ad set name":                          st.column_config.TextColumn("Ad set name",                          width="large"),
            "Objective":                            st.column_config.TextColumn("Objective",                            width="small"),
            "Result type":                          st.column_config.TextColumn("Result type",                          width="medium"),
            "Results":                              st.column_config.NumberColumn("Results",                            format="%d"),
            "Cost per result":                      st.column_config.NumberColumn("Cost per result",                    format="€%.2f"),
            "Amount spent (EUR)":                   st.column_config.NumberColumn("Amount spent (EUR)",                 format="€%.2f"),
            "Campaign Budget":                      st.column_config.NumberColumn("Campaign Budget",                    format="€%.2f"),
            "Campaign Budget Type":                 st.column_config.TextColumn("Campaign Budget Type",                 width="small"),
            "Ad Set Budget":                        st.column_config.TextColumn("Ad Set Budget"),
            "Ad Set Budget Type":                   st.column_config.TextColumn("Ad Set Budget Type",                   width="medium"),
            "Reach":                                st.column_config.NumberColumn("Reach",                              format="%d"),
            "Cost per 1,000 Meta Accounts reached": st.column_config.NumberColumn("Cost per 1,000 Meta Accounts reached", format="€%.2f"),
            "Impressions":                          st.column_config.NumberColumn("Impressions",                        format="%d"),
            "CPM (cost per 1,000 impressions)":     st.column_config.NumberColumn("CPM (cost per 1,000 impressions)",  format="€%.2f"),
            "Frequency":                            st.column_config.NumberColumn("Frequency",                         format="%.2f"),
            "Clicks (all)":                         st.column_config.NumberColumn("Clicks (all)",                      format="%d"),
            "CPC (all)":                            st.column_config.NumberColumn("CPC (all)",                         format="€%.2f"),
            "Link clicks":                          st.column_config.NumberColumn("Link clicks",                       format="%d"),
            "CPC (cost per link click)":            st.column_config.NumberColumn("CPC (cost per link click)",         format="€%.2f"),
            "CTR (all)":                            st.column_config.NumberColumn("CTR (all)",                         format="%.2f%%"),
            "CTR (link click-through rate)":        st.column_config.NumberColumn("CTR (link click-through rate)",     format="%.2f%%"),
            "Outbound clicks":                      st.column_config.NumberColumn("Outbound clicks",                   format="%d"),
            "Cost per outbound click":              st.column_config.NumberColumn("Cost per outbound click",           format="€%.2f"),
            "Website landing page views":           st.column_config.NumberColumn("Website landing page views",        format="%d"),
            "Cost per landing page view":           st.column_config.NumberColumn("Cost per landing page view",        format="€%.2f"),
            "Adds to cart":                         st.column_config.NumberColumn("Adds to cart",                      format="%d"),
            "Website adds to cart":                 st.column_config.NumberColumn("Website adds to cart",              format="%d"),
            "Cost per add to cart":                 st.column_config.NumberColumn("Cost per add to cart",              format="€%.2f"),
            "Checkouts initiated":                  st.column_config.NumberColumn("Checkouts initiated",               format="%d"),
            "Website checkouts initiated":          st.column_config.NumberColumn("Website checkouts initiated",       format="%d"),
            "Cost per checkout initiated":          st.column_config.NumberColumn("Cost per checkout initiated",       format="€%.2f"),
            "Purchases":                            st.column_config.NumberColumn("Purchases",                         format="%d"),
            "Website purchases":                    st.column_config.NumberColumn("Website purchases",                 format="%d"),
            "Cost per purchase":                    st.column_config.NumberColumn("Cost per purchase",                 format="€%.2f"),
            "Engagement rate ranking":              st.column_config.TextColumn("Engagement rate ranking",             width="medium"),
            "Quality ranking":                      st.column_config.TextColumn("Quality ranking",                     width="medium"),
            "Conversion rate ranking":              st.column_config.TextColumn("Conversion rate ranking",             width="medium"),
            "Reporting starts":                     st.column_config.TextColumn("Reporting starts",                    width="small"),
            "Reporting ends":                       st.column_config.TextColumn("Reporting ends",                      width="small"),
            "Start":                                st.column_config.TextColumn("Start",                               width="small"),
            "End":                                  st.column_config.TextColumn("End",                                 width="small"),
        }

    # ── Shared row builder for ad-level dicts ─────────────────────────────────
    def _build_ad_row(a):
        spend = a.get("spend", 0.0)
        conv  = a.get("conversions", 0)
        return {
            "Campaign name":                      a.get("campaign_name", "—"),
            "Ad set name":                        a.get("adset_name", "—"),
            "Ad name":                            a.get("ad_name", "—"),
            "Delivery status":                    a.get("delivery_status", "—"),
            "Delivery level":                     a.get("delivery_level", "ad"),
            "Objective":                          a.get("objective", "—"),
            "Result type":                        a.get("result_type", "—"),
            "Results":                            conv,
            "Cost per result":                    round(a.get("cpa", 0.0), 2),
            "Amount spent (EUR)":                 round(spend, 2),
            "Campaign Budget":                    round(a.get("campaign_budget", 0.0), 2),
            "Campaign Budget Type":               a.get("campaign_budget_type", "—"),
            "Ad Set Budget":                      round(a.get("adset_budget", 0.0), 2) if a.get("adset_budget", 0.0) > 0 else "—",
            "Ad Set Budget Type":                 a.get("adset_budget_type", "—"),
            "Reach":                              a.get("reach", 0),
            "Cost per 1,000 Meta Accounts reached": round(a.get("cpm_reach", 0.0), 2),
            "Impressions":                        a.get("impressions", 0),
            "CPM (cost per 1,000 impressions)":   round(a.get("cpm", 0.0), 2),
            "Frequency":                          round(a.get("frequency", 0.0), 2),
            "Clicks (all)":                       a.get("clicks", 0),
            "CPC (all)":                          round(a.get("cpc", 0.0), 2),
            "Link clicks":                        a.get("link_clicks", 0),
            "CPC (cost per link click)":          round(a.get("cpc_link", 0.0), 2),
            "CTR (all)":                          round(a.get("ctr", 0.0), 2),
            "CTR (link click-through rate)":      round(a.get("ctr_link", 0.0), 2),
            "Outbound clicks":                    a.get("outbound_clicks", 0),
            "Cost per outbound click":            round(a.get("cost_per_outbound", 0.0), 2),
            "Website landing page views":         a.get("landing_page_views", 0),
            "Cost per landing page view":         round(a.get("cost_per_lp_view", 0.0), 2),
            "Adds to cart":                       a.get("adds_to_cart", 0),
            "Website adds to cart":               a.get("adds_to_cart", 0),
            "Cost per add to cart":               round(a.get("cost_per_add_to_cart", 0.0), 2),
            "Checkouts initiated":                a.get("checkouts", 0),
            "Website checkouts initiated":        a.get("checkouts", 0),
            "Cost per checkout initiated":        round(a.get("cost_per_checkout", 0.0), 2),
            "Purchases":                          conv,
            "Website purchases":                  conv,
            "Cost per purchase":                  round(a.get("cpa", 0.0), 2),
            "Purchase ROAS (return on ad spend)": round(a.get("roas", 0.0), 2),
            "Website purchase value":             round(a.get("purchase_value", 0.0), 2),
            "Engagement rate ranking":            a.get("engagement_ranking", "—"),
            "Quality ranking":                    a.get("quality_ranking", "—"),
            "Conversion rate ranking":            a.get("conversion_ranking", "—"),
            # Video
            "Video plays":                        a.get("video_plays", 0),
            "ThruPlays":                          a.get("thruplays", 0),
            "Video plays at 25%":                 a.get("video_p25", 0),
            "Video plays at 50%":                 a.get("video_p50", 0),
            "Video plays at 75%":                 a.get("video_p75", 0),
            "Video plays at 100%":                a.get("video_p100", 0),
            "Video average play time (sec)":      a.get("video_avg_time", 0.0),
            # Engagement
            "Post engagement":                    a.get("post_engagement", 0),
            "Page engagement":                    a.get("page_engagement", 0),
            "Post reactions":                     a.get("post_reactions", 0),
            "Post comments":                      a.get("post_comments", 0),
            "Post shares":                        a.get("post_shares", 0),
            "Post saves":                         a.get("post_saves", 0),
            "Page likes":                         a.get("page_likes", 0),
            "Photo views":                        a.get("photo_views", 0),
            # Outbound CTR
            "Outbound CTR (click-through rate)":  round(a.get("outbound_ctr", 0.0), 4),
            # Leads & installs
            "Website leads":                      a.get("leads", 0),
            "Cost per lead":                      round(a.get("cost_per_lead", 0.0), 4),
            "App installs":                       a.get("app_installs", 0),
            "Cost per app install":               round(a.get("cost_per_app_install", 0.0), 4),
            "Reporting starts":                   reporting_start,
            "Reporting ends":                     reporting_end,
            "Start":                              a.get("campaign_start", "—"),
            "End":                                a.get("campaign_end", "—"),
        }

    # ── Shared row builder for adset-level dicts ──────────────────────────────
    def _build_adset_row(a):
        spend = a.get("spend", 0.0)
        imp   = a.get("impressions", 0)
        reach = a.get("reach", 0)
        lk    = a.get("link_clicks", 0)
        conv  = a.get("conversions", 0)
        cpa   = a.get("cpa", 0.0)
        cpm   = round(spend / imp * 1000, 2) if imp else 0.0
        cpm_r = round(spend / reach * 1000, 2) if reach else 0.0
        cpc_l = round(spend / lk, 2) if lk else 0.0
        ctr_l = round(lk / imp * 100, 2) if imp else 0.0
        return {
            "Campaign name":                      a.get("campaign_name", "—"),
            "Ad set name":                        a.get("adset_name", "—"),
            "Ad name":                            "—",
            "Delivery status":                    "—",
            "Delivery level":                     "adset",
            "Objective":                          "—",
            "Result type":                        "—",
            "Results":                            conv,
            "Cost per result":                    round(cpa, 2),
            "Amount spent (EUR)":                 round(spend, 2),
            "Campaign Budget":                    0.0,
            "Campaign Budget Type":               "—",
            "Ad Set Budget":                      "—",
            "Ad Set Budget Type":                 "—",
            "Reach":                              reach,
            "Cost per 1,000 Meta Accounts reached": cpm_r,
            "Impressions":                        imp,
            "CPM (cost per 1,000 impressions)":   cpm,
            "Frequency":                          round(a.get("frequency", 0.0), 2),
            "Clicks (all)":                       a.get("clicks", 0),
            "CPC (all)":                          round(a.get("cpc", 0.0), 2),
            "Link clicks":                        lk,
            "CPC (cost per link click)":          cpc_l,
            "CTR (all)":                          round(a.get("ctr", 0.0), 2),
            "CTR (link click-through rate)":      ctr_l,
            "Outbound clicks":                    0,
            "Cost per outbound click":            0.0,
            "Website landing page views":         0,
            "Cost per landing page view":         0.0,
            "Adds to cart":                       0,
            "Website adds to cart":               0,
            "Cost per add to cart":               0.0,
            "Checkouts initiated":                0,
            "Website checkouts initiated":        0,
            "Cost per checkout initiated":        0.0,
            "Purchases":                          conv,
            "Website purchases":                  conv,
            "Cost per purchase":                  round(cpa, 2),
            "Engagement rate ranking":            "—",
            "Quality ranking":                    "—",
            "Conversion rate ranking":            "—",
            "Reporting starts":                   reporting_start,
            "Reporting ends":                     reporting_end,
            "Start":                              "—",
            "End":                                "—",
        }

    if ads:
        # ── Objective filter ──────────────────────────────────────────────────
        _sel_objs: list[str] = []
        all_objectives = sorted(set(a.get("objective", "—") for a in ads if a.get("objective", "—") != "—"))
        if all_objectives:
            _sales_default = [o for o in all_objectives if "SALES" in o] or all_objectives
            _sel_objs = st.multiselect(
                "Filtrer par objectif",
                options=all_objectives,
                default=_sales_default,
                label_visibility="collapsed",
                placeholder="Sélectionner un ou plusieurs objectifs…",
                key="obj_filter_table",
            )
            ads = [a for a in ads if a.get("objective", "—") in _sel_objs] if _sel_objs else ads

        ad_rows = [
            _build_ad_row(a)
            for a in sorted(ads, key=lambda x: (x.get("campaign_created", ""), x.get("campaign_name", "")), reverse=True)
        ]

        _ads_df = pd.DataFrame(ad_rows)

        # ── Fixed column order matching Ads Manager CSV export ───────────────────
        _CSV_COLS = [
            "Ad name", "Campaign name", "Delivery status", "Delivery level", "Ad set name",
            "Objective", "Result type", "Results", "Cost per result", "Amount spent (EUR)",
            "Campaign Budget", "Campaign Budget Type", "Ad Set Budget", "Ad Set Budget Type",
            "Reach", "Cost per 1,000 Meta Accounts reached",
            "Impressions", "CPM (cost per 1,000 impressions)", "Frequency",
            "Clicks (all)", "CPC (all)", "Link clicks", "CPC (cost per link click)",
            "CTR (all)", "CTR (link click-through rate)",
            "Outbound clicks", "Cost per outbound click",
            "Website landing page views", "Cost per landing page view",
            "Adds to cart", "Website adds to cart", "Cost per add to cart",
            "Checkouts initiated", "Website checkouts initiated", "Cost per checkout initiated",
            "Purchases", "Website purchases", "Cost per purchase",
            "Engagement rate ranking", "Quality ranking", "Conversion rate ranking",
            "Reporting starts", "Reporting ends",
        ]
        _ads_display = _ads_df[[c for c in _CSV_COLS if c in _ads_df.columns]]

        # ── Excel export ──────────────────────────────────────────────────────
        _spacer, _dl_col = st.columns([3, 1])
        with _dl_col:
            try:
                st.download_button(
                    "📥 Télécharger en Excel",
                    data=_df_to_excel_bytes(_ads_display, sheet_name="Campagnes"),
                    file_name="campagnes_footland.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_campaigns_xlsx",
                    use_container_width=True,
                )
            except Exception as e:
                st.caption(f"Export Excel indisponible : {e}")

        st.dataframe(
            _ads_display,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="multi-row",
            column_config=_csv_col_config(),
        )

        # ── Campaign-level KPI table — same filter, right below ───────────────
        st.divider()
        _render_campaign_kpi_table(campaigns, adset_ad_data)
    else:
        _no_data_banner("Aucune donnée ads disponible — les données adset/ads se chargent séparément.")

    # ── One expander per campaign ──────────────────────────────────────────────
    for c in sorted(campaigns, key=lambda x: x.get("spend", 0.0), reverse=True):
        name   = c.get("name", "—")
        spend  = c.get("spend", 0.0)
        clicks = c.get("clicks", 0)
        conv   = c.get("conversions", 0)
        obj    = c.get("objective", "—")
        ctr    = c.get("ctr", 0.0)
        cpc    = c.get("cpc", 0.0)
        reach  = c.get("reach", 0)
        imp    = c.get("impressions", 0)
        cpa    = c.get("cpa", 0.0)
        freq   = c.get("frequency", 0.0)

        camp_adsets = sorted(
            adsets_by_campaign.get(name, []),
            key=lambda x: x.get("spend", 0), reverse=True
        )
        n_adsets = len(camp_adsets)
        adset_hint = f" · {n_adsets} adset{'s' if n_adsets != 1 else ''}" if n_adsets else ""

        label = (
            f"📁 {name}"
            f"  —  💰 €{spend:,.2f}"
            f"  ·  🖱️ {clicks:,} clics"
            f"  ·  ✅ {conv} cmd"
            f"{adset_hint}"
        )

        with st.expander(label, expanded=False):
            # Mini KPI row for this campaign
            st.markdown(
                f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.5rem;margin-bottom:0.8rem;">'
                f'{_kpi_card("💰", "Dépensé",     _fmt_currency(spend),  "#f97316")}'
                f'{_kpi_card("🖱️", "Clics",        _fmt_int(clicks))}'
                f'{_kpi_card("👁️", "Portée",       _fmt_int(reach))}'
                f'{_kpi_card("📈", "CTR",          _fmt_pct(ctr),         "#4ade80")}'
                f'{_kpi_card("💸", "CPC",          _fmt_currency(cpc),    "#facc15")}'
                f'</div>'
                f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.5rem;margin-bottom:1rem;">'
                f'{_kpi_card("📢", "Impressions",  _fmt_int(imp))}'
                f'{_kpi_card("🔁", "Répétition",   f"{freq:.2f}x")}'
                f'{_kpi_card("✅", "Commandes",    _fmt_int(conv),        "#a78bfa")}'
                f'{_kpi_card("🎁", "Coût/vente",  _fmt_currency(cpa),    "#fb7185")}'
                f'{_kpi_card("🎯", "Objectif",     obj[:20] if obj else "—")}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Adsets
            if camp_adsets:
                st.markdown(
                    '<div style="font-size:0.8rem;font-weight:700;'
                    'color:rgba(255,255,255,0.55);margin-bottom:0.4rem;">📦 ADSETS</div>',
                    unsafe_allow_html=True,
                )
                st.dataframe(
                    pd.DataFrame([_build_adset_row(a) for a in camp_adsets]),
                    use_container_width=True,
                    hide_index=True,
                    column_config=_csv_col_config(),
                )

                # Per-adset ads expander
                for adset in camp_adsets:
                    adset_id   = str(adset.get("adset_id", ""))
                    adset_name = adset.get("adset_name", "—")
                    adset_ads  = sorted(
                        ads_by_adset.get(adset_id, []),
                        key=lambda x: x.get("spend", 0), reverse=True
                    )
                    ads_label = f"🎨 {adset_name} — {len(adset_ads)} ad{'s' if len(adset_ads) != 1 else ''}"
                    with st.expander(ads_label, expanded=False):
                        if not adset_ads:
                            st.caption("Aucun ad pour cet adset.")
                        else:
                            st.dataframe(
                                pd.DataFrame([_build_ad_row(a) for a in adset_ads]),
                                use_container_width=True,
                                hide_index=True,
                                column_config=_csv_col_config(),
                            )
            else:
                st.caption("Aucune donnée adset disponible pour cette campagne.")


def _render_campaign_kpi_table(campaigns: list[dict], adset_ad_data: dict | None = None,
                               selected_objectives: list[str] | None = None):
    """Campaign-level KPI table mirroring the Meta Ads Manager CSV export columns."""
    active = [c for c in campaigns if c.get("spend", 0) > 0 or c.get("impressions", 0) > 0]
    if not active:
        return

    _section_header("📊 Rapport Hebdomadaire Notoriété & Engagement")

    # ── Own independent objective filter ──────────────────────────────────────
    _obj_order = ["OUTCOME_ENGAGEMENT", "OUTCOME_AWARENESS"]
    _obj_set = set(c.get("objective", "—") for c in active if c.get("objective", "—") != "—")
    all_obj = [o for o in _obj_order if o in _obj_set] + sorted(_obj_set - set(_obj_order))
    if all_obj:
        _non_sales_default = [o for o in all_obj if "SALES" not in o] or all_obj
        _sel = st.multiselect(
            "Filtrer par objectif",
            options=all_obj,
            default=_non_sales_default,
            label_visibility="collapsed",
            placeholder="Sélectionner un ou plusieurs objectifs…",
            key="obj_filter_camp_report",
        )
        if _sel:
            active = [c for c in active if c.get("objective", "—") in _sel]

    if not active:
        return

    period = (adset_ad_data or {}).get("period", {})
    reporting_start = period.get("since", "—")
    reporting_end   = period.get("until", "—")

    # Build campaign start/end dates from ad-level rows (already enriched with campaign metadata)
    camp_dates: dict[str, dict] = {}
    for a in (adset_ad_data or {}).get("ads", []):
        cname = a.get("campaign_name", "")
        if cname and cname not in camp_dates:
            camp_dates[cname] = {
                "start": a.get("campaign_start", "—"),
                "end":   a.get("campaign_end",   "—"),
            }

    # Fallback result-type map (used only if the API didn't resolve a result
    # type from the ad-set optimization goal).
    _RESULT_TYPE_MAP = {
        "OUTCOME_AWARENESS":     ("Reach",             "reach"),
        "OUTCOME_ENGAGEMENT":    ("Post engagements",  "post_engagement"),
        "OUTCOME_SALES":         ("Website purchases", "conversions"),
        "CONVERSIONS":           ("Website purchases", "conversions"),
        "OUTCOME_TRAFFIC":       ("Link clicks",       "link_clicks"),
        "OUTCOME_LEADS":         ("Leads",             "leads"),
        "OUTCOME_APP_PROMOTION": ("App installs",      "app_installs"),
    }

    rows = []
    for c in sorted(active, key=lambda x: x.get("spend", 0.0), reverse=True):
        obj   = c.get("objective", "—")
        spend = c.get("spend", 0.0)
        reach = c.get("reach", 0)
        lk    = c.get("link_clicks", 0)
        conv  = c.get("conversions", 0)
        imp   = c.get("impressions", 0)
        freq  = c.get("frequency", 0.0)
        name  = c.get("name", "—")

        # Prefer the result type/count resolved by the API from the optimization
        # goal; fall back to the objective-based map if absent.
        result_type = c.get("result_type") or "—"
        results     = c.get("results")
        if results is None:
            _rt, _src = _RESULT_TYPE_MAP.get(obj, ("—", ""))
            result_type = _rt
            results = c.get(_src, 0) if _src else 0
        cost_per_result = c.get("cost_per_result")
        if cost_per_result is None:
            cost_per_result = round(spend / results, 4) if results else 0.0
        cpm     = round(spend / imp * 1000, 4) if imp else 0.0
        cpc_lnk = round(spend / lk,         4) if lk  else 0.0
        dates   = camp_dates.get(name, {"start": "—", "end": "—"})

        rows.append({
            "Campaign name":                    name,
            "Objective":                        obj,
            "Reach":                            reach,
            "Impressions":                      imp,
            "Frequency":                        round(freq, 5),
            "Result type":                      result_type,
            "Results":                          results,
            "Amount spent (EUR)":               round(spend, 2),
            "Starts":                           dates["start"],
            "Ends":                             dates["end"],
            "Cost per result":                  cost_per_result,
            "Delivery status":                  c.get("delivery_status", "—"),
            "Delivery level":                   "campaign",
            "Link clicks":                      lk,
            "CPC (cost per link click)":        cpc_lnk,
            "CPM (cost per 1,000 impressions)": cpm,
            "CTR (all)":                        round(c.get("ctr", 0.0), 8),
            "Reporting starts":                 reporting_start,
            "Reporting ends":                   reporting_end,
        })

    if not rows:
        return

    _df = pd.DataFrame(rows)

    _KPI_COLS = [
        "Campaign name", "Objective", "Reach", "Impressions", "Frequency",
        "Result type", "Results", "Amount spent (EUR)", "Starts", "Ends",
        "Cost per result", "Delivery status", "Delivery level", "Link clicks",
        "CPC (cost per link click)", "CPM (cost per 1,000 impressions)",
        "CTR (all)", "Reporting starts", "Reporting ends",
    ]
    _df_display = _df[[c for c in _KPI_COLS if c in _df.columns]]

    _spacer, _dl_col = st.columns([3, 1])
    with _dl_col:
        try:
            st.download_button(
                "📥 Télécharger en Excel",
                data=_df_to_excel_bytes(_df_display, sheet_name="Rapport Campagnes"),
                file_name="rapport_campagnes_footland.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_camp_report_xlsx",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Export Excel indisponible : {e}")

    st.dataframe(
        _df_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        column_config={
            "Campaign name":                    st.column_config.TextColumn("Campaign name",                        width="large"),
            "Objective":                        st.column_config.TextColumn("Objective",                            width="medium"),
            "Reach":                            st.column_config.NumberColumn("Reach",                              format="%d"),
            "Impressions":                      st.column_config.NumberColumn("Impressions",                        format="%d"),
            "Frequency":                        st.column_config.NumberColumn("Frequency",                         format="%.5f"),
            "Result type":                      st.column_config.TextColumn("Result type",                         width="medium"),
            "Results":                          st.column_config.NumberColumn("Results",                            format="%d"),
            "Amount spent (EUR)":               st.column_config.NumberColumn("Amount spent (EUR)",                format="€%.2f"),
            "Starts":                           st.column_config.TextColumn("Starts",                               width="small"),
            "Ends":                             st.column_config.TextColumn("Ends",                                 width="small"),
            "Cost per result":                  st.column_config.NumberColumn("Cost per result",                   format="€%.4f"),
            "Delivery status":                  st.column_config.TextColumn("Delivery status",                     width="medium"),
            "Delivery level":                   st.column_config.TextColumn("Delivery level",                      width="small"),
            "Link clicks":                      st.column_config.NumberColumn("Link clicks",                       format="%d"),
            "CPC (cost per link click)":        st.column_config.NumberColumn("CPC (cost per link click)",        format="€%.4f"),
            "CPM (cost per 1,000 impressions)": st.column_config.NumberColumn("CPM (cost per 1,000 impressions)", format="€%.4f"),
            "CTR (all)":                        st.column_config.NumberColumn("CTR (all)",                         format="%.8f%%"),
            "Reporting starts":                 st.column_config.TextColumn("Reporting starts",                    width="small"),
            "Reporting ends":                   st.column_config.TextColumn("Reporting ends",                      width="small"),
        },
    )


def _render_demographics(demo: dict):
    """Age / gender bar chart from Marketing API paid reach."""
    _section_header("👥 DONNÉES DÉMOGRAPHIQUES")

    age_brackets    = demo.get("age_brackets", [])
    men_pcts        = demo.get("men", [])
    women_pcts      = demo.get("women", [])
    total_men_pct   = demo.get("total_men_pct", 0)
    total_women_pct = demo.get("total_women_pct", 0)

    if not age_brackets or not any(v > 0 for v in men_pcts + women_pcts):
        _no_data_banner("Données démographiques non disponibles pour cette période.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Hommes",
        x=age_brackets,
        y=men_pcts,
        marker_color="#7EC8E3",
        text=[f"{v}%" for v in men_pcts],
        textposition="outside",
        textfont=dict(size=11, color="rgba(255,255,255,0.6)"),
    ))
    fig.add_trace(go.Bar(
        name="Femmes",
        x=age_brackets,
        y=women_pcts,
        marker_color="#1C4E80",
        text=[f"{v}%" for v in women_pcts],
        textposition="outside",
        textfont=dict(size=11, color="rgba(255,255,255,0.6)"),
    ))
    _ymax = max(max(men_pcts + women_pcts, default=0) * 1.25, 10)
    fig.update_layout(**{
        **get_chart_layout(),
        "barmode": "group",
        "yaxis": dict(
            gridcolor="rgba(255,255,255,0.06)", showline=False,
            ticksuffix="%", range=[0, _ymax],
        ),
        "xaxis": dict(gridcolor="rgba(255,255,255,0.06)", showline=False),
        "showlegend": False,
        "margin": dict(l=0, r=0, t=20, b=40),
        "height": 320,
    })
    st.plotly_chart(fig, use_container_width=True)

    _dark   = st.session_state.get("theme", "dark") == "dark"
    _leg_c  = "rgba(255,255,255,0.7)" if _dark else "#374151"
    _note_c = "rgba(255,255,255,0.3)" if _dark else "#9ca3af"

    st.markdown(
        f'<div style="display:flex;justify-content:center;align-items:center;gap:2rem;margin-top:-8px;">'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<div style="width:24px;height:12px;background:#7EC8E3;border-radius:3px;"></div>'
        f'<span style="font-size:0.8rem;color:{_leg_c};">Hommes — <strong>{total_men_pct}%</strong></span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<div style="width:24px;height:12px;background:#1C4E80;border-radius:3px;"></div>'
        f'<span style="font-size:0.8rem;color:{_leg_c};">Femmes — <strong>{total_women_pct}%</strong></span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="font-size:0.7rem;color:{_note_c};text-align:center;margin-top:4px;">'
        f'* Basé sur la portée des campagnes payantes Footland (Marketing API)</p>',
        unsafe_allow_html=True,
    )


def _render_geographic(demo: dict):
    """Top cities and top countries from Marketing API paid reach."""
    _section_header("🌍 DONNÉES GÉOGRAPHIQUES")

    top_cities = demo.get("top_cities", [])

    if not top_cities:
        _no_data_banner("Données géographiques non disponibles pour cette période.")
        return

    _dark     = st.session_state.get("theme", "dark") == "dark"
    _geo_bg   = "rgba(255,255,255,0.04)" if _dark else "#f9fafb"
    _geo_brd  = "none"                    if _dark else "1px solid #e5e7eb"
    _title_c  = "#ffffff"                 if _dark else "#111827"
    _empty_c  = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"
    _name_c   = "rgba(255,255,255,0.8)"  if _dark else "#111827"
    _stat_c   = "rgba(255,255,255,0.5)"  if _dark else "#6b7280"
    _bar_bg   = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"
    _rank_low = "rgba(255,255,255,0.3)"  if _dark else "#d1d5db"

    def _geo_table(items: list, icon: str, title: str) -> str:
        if not items:
            return (
                f'<div style="background:{_geo_bg};border:{_geo_brd};border-radius:14px;padding:1.2rem;">'
                f'<p style="font-size:0.95rem;font-weight:700;color:{_title_c};margin:0 0 12px;">{icon} {title}</p>'
                f'<p style="font-size:0.8rem;color:{_empty_c};margin:0;">Aucune donnée disponible</p>'
                f'</div>'
            )
        rank_colors = ["#FFD700", "#C0C0C0", "#CD7F32"] + [_rank_low] * 7
        rows_html = ""
        for i, item in enumerate(items):
            bar_w = round(item["pct"] * 0.9, 1)
            rows_html += (
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                f'<span style="font-size:0.72rem;font-weight:700;color:{rank_colors[i]};width:16px;text-align:right;">#{i+1}</span>'
                f'<div style="flex:1;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:2px;">'
                f'<span style="font-size:0.78rem;color:{_name_c};">{item["name"]}</span>'
                f'<span style="font-size:0.78rem;color:{_stat_c};">{item["reach"]:,} impr. · {item["pct"]}%</span>'
                f'</div>'
                f'<div style="background:{_bar_bg};border-radius:4px;height:5px;">'
                f'<div style="background:#E8420A;width:{bar_w}%;height:5px;border-radius:4px;"></div>'
                f'</div></div></div>'
            )
        return (
            f'<div style="background:{_geo_bg};border:{_geo_brd};border-radius:14px;padding:1.2rem;">'
            f'<p style="font-size:0.95rem;font-weight:700;color:{_title_c};margin:0 0 14px;">{icon} {title}</p>'
            f'{rows_html}'
            f'</div>'
        )

    st.markdown(_geo_table(top_cities, "🏙️", "Top Villes / Régions"), unsafe_allow_html=True)


# ─── Public entry point ────────────────────────────────────────────────────────
def render_boost_tab(data: dict | None = None, demo: dict | None = None,
                     prev_data: dict | None = None,
                     since: str = "", until: str = "", adset_ad_data=None):
    """
    Render the full Boost (Ads Performance) tab.

    Parameters
    ----------
    data          : dict  — output of fetch_boost_insights()
    demo          : dict  — output of fetch_fb_demographics() (age/gender + geo)
    prev_data     : dict  — same shape as data but for the previous equivalent period
    adset_ad_data : dict  — output of fetch_adset_ad_insights()
    """
    if data is None:
        data = empty_boost_data()
    if demo is None:
        demo = {}

    totals    = data.get("totals",      {})
    conv      = data.get("conversions", {})
    campaigns   = data.get("campaigns",      [])
    obj_reach   = data.get("objective_reach", {})
    # Use dates passed directly from app.py (always available, not cache-dependent)
    _period_since = since or data.get("period", {}).get("since", "")
    _period_until = until or data.get("period", {}).get("until", "")

    prev_totals = (prev_data or {}).get("totals",      {})
    prev_conv   = (prev_data or {}).get("conversions", {})

    # Recompute campaigns_count live from campaigns list to stay consistent with PAR OBJECTIF
    _CONV_OBJ = {"CONVERSIONS", "OUTCOME_SALES"}
    conv = dict(conv)  # avoid mutating cached dict
    conv["campaigns_count"] = sum(
        1 for c in campaigns
        if c.get("objective") in _CONV_OBJ and (c.get("spend", 0) > 0 or c.get("impressions", 0) > 0)
    )

    # ── Context for AI chatbot ────────────────────────────────────────────────
    st.session_state["ctx_boost"] = {
        "period": f"{_period_since} → {_period_until}",
        "campaigns_count": totals.get("campaigns_count", 0),
        "link_clicks": totals.get("link_clicks", 0),
        "reach": totals.get("reach", 0),
        "impressions": totals.get("impressions", 0),
        "cpc": totals.get("cpc", 0.0),
        "ctr": totals.get("ctr", 0.0),
        "spend": totals.get("spend", 0.0),
        "frequency": totals.get("frequency", 0.0),
    }

    # Header
    _dark   = st.session_state.get("theme", "dark") == "dark"
    _hdr_c  = "#ffffff"                 if _dark else "#111827"
    _sub_c  = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"
    st.markdown(
        f'<p style="font-size:1.4rem;font-weight:800;letter-spacing:0.08em;'
        f'color:{_hdr_c};margin:0 0 0.2rem;">BOOST — ADS PERFORMANCE</p>'
        f'<p style="font-size:0.8rem;color:{_sub_c};margin:0 0 1rem;">'
        f'Performances publicitaires payantes · Meta Marketing API</p>',
        unsafe_allow_html=True,
    )

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Global",
        "🎯 Conversion",
        "🗂️ Par Objectif",
        "🏆 Top #3 Campagnes",
        "📋 Rapport",
        "👥 Démographie & Géo",
    ])

    with t1:
        _render_global_kpis(totals, prev_totals)
        st.divider()
        _render_conversion_campaigns(conv, prev_conv)

    with t2:
        _render_funnel(totals, campaigns)
        st.divider()
        _render_acquisition_kpis(totals, campaigns)

    with t3:
        _render_by_objective(campaigns, obj_reach,
                             {"since": _period_since, "until": _period_until})

    with t4:
        _render_top_campaigns(campaigns)

    with t5:
        _render_campaigns_table(campaigns, adset_ad_data=adset_ad_data)

    with t6:
        _render_demographics(demo)
        st.divider()
        _render_geographic(demo)
