"""
views/analytics.py — Google Analytics 4 dashboard tab.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.ai_insights import render_ai_report
from components.alerts import check_all, publish_alerts, render_alerts
from components.charts import get_chart_layout


# ─── Helpers ───────────────────────────────────────────────────────────────────
def _fmt_int(v: int) -> str:
    return f"{int(v):,}"

def _fmt_pct(v: float) -> str:
    return f"{v:.2f}%"

def _fmt_dur(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s:02d}s"

def _kpi_card(icon: str, label: str, value: str, color: str | None = None) -> str:
    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg  = "rgba(255,255,255,0.05)" if _dark else "#ffffff"
    _brd = "none"                    if _dark else "1px solid #e5e7eb"
    _lc  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _vc  = color if color else ("#ffffff" if _dark else "#111827")
    return (
        f'<div style="background:{_bg};border:{_brd};border-radius:12px;'
        f'padding:0.9rem 1rem;text-align:center;">'
        f'<div style="font-size:0.72rem;color:{_lc};margin-bottom:0.25rem;">{icon} {label}</div>'
        f'<div style="font-size:1.3rem;font-weight:800;color:{_vc};white-space:nowrap;">{value}</div>'
        f'</div>'
    )

def _section_header(title: str):
    _brd = "rgba(255,255,255,0.15)"
    st.markdown(
        f'<div style="font-size:1.35rem;color:#ffffff;font-weight:700;'
        f'letter-spacing:0.05em;margin:1.8rem 0 0.8rem;border-bottom:2px solid {_brd};'
        f'padding-bottom:0.5rem;">{title}</div>',
        unsafe_allow_html=True,
    )

def _no_data(msg: str = "Aucune donnée disponible pour cette période."):
    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg  = "rgba(255,165,0,0.08)"  if _dark else "rgba(255,165,0,0.12)"
    _tc  = "rgba(255,165,0,0.9)"   if _dark else "#92400e"
    st.markdown(
        f'<div style="background:{_bg};border:1px solid rgba(255,165,0,0.3);'
        f'border-radius:10px;padding:1rem 1.2rem;color:{_tc};'
        f'font-size:0.85rem;margin:0.5rem 0 1rem;">⚠️ {msg}</div>',
        unsafe_allow_html=True,
    )


# ─── Section renderers ─────────────────────────────────────────────────────────
def _render_overview(ov: dict):
    _section_header("📊 VUE D'ENSEMBLE")
    if not ov:
        _no_data()
        return

    row1 = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:0.6rem;">
  {_kpi_card("👥", "Utilisateurs actifs",    _fmt_int(ov.get("active_users", 0)),     "#7dd3fc")}
  {_kpi_card("🆕", "Nouveaux utilisateurs",  _fmt_int(ov.get("new_users", 0)),         "#a78bfa")}
  {_kpi_card("🔄", "Sessions",               _fmt_int(ov.get("sessions", 0)),          "#4ade80")}
  {_kpi_card("✅", "Sessions engagées",      _fmt_int(ov.get("engaged_sessions", 0)),  "#34d399")}
</div>"""

    row2 = f"""
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("💡", "Taux d'engagement",  _fmt_pct(ov.get("engagement_rate", 0.0)),        "#4ade80")}
  {_kpi_card("↩️", "Taux de rebond",     _fmt_pct(ov.get("bounce_rate", 0.0)),             "#f87171")}
  {_kpi_card("⏱️", "Durée moyenne",      _fmt_dur(ov.get("avg_session_duration", 0.0)),    "#facc15")}
  {_kpi_card("📄", "Pages vues",         _fmt_int(ov.get("page_views", 0)),                "#fb923c")}
  {_kpi_card("📑", "Pages / Session",    f"{ov.get('pages_per_session', 0.0):.2f}",        "#e879f9")}
</div>"""

    st.markdown(row1 + row2, unsafe_allow_html=True)


def _render_traffic_sources(sources: list):
    _section_header("🚦 SOURCES DE TRAFIC")
    if not sources:
        _no_data()
        return

    _dark   = st.session_state.get("theme", "dark") == "dark"
    _bg     = "rgba(255,255,255,0.03)" if _dark else "#f9fafb"
    _brd    = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"
    _txt_c  = "#ffffff"                 if _dark else "#111827"
    _sub_c  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"

    _CHANNEL_ICONS = {
        "Organic Search":  "🔍",
        "Direct":          "🔗",
        "Organic Social":  "📱",
        "Paid Search":     "💰",
        "Paid Social":     "📢",
        "Referral":        "🔄",
        "Email":           "📧",
        "Unassigned":      "❓",
        "Organic Video":   "▶️",
        "Affiliates":      "🤝",
    }

    max_sessions = max(s["sessions"] for s in sources) or 1
    rows_html = ""
    for s in sources:
        bar_w = round(s["sessions"] / max_sessions * 100, 1)
        icon  = _CHANNEL_ICONS.get(s["channel"], "📊")
        rows_html += (
            f'<div style="margin-bottom:0.75rem;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
            f'<span style="font-size:0.8rem;color:{_txt_c};font-weight:600;">{icon} {s["channel"]}</span>'
            f'<span style="font-size:0.72rem;color:{_sub_c};">'
            f'{_fmt_int(s["sessions"])} sessions · {s["pct"]}% · '
            f'eng. {_fmt_pct(s["engagement_rate"])}'
            f'</span></div>'
            f'<div style="background:{_brd};border-radius:6px;height:8px;">'
            f'<div style="background:#E8420A;width:{bar_w}%;height:8px;border-radius:6px;"></div>'
            f'</div></div>'
        )

    st.markdown(
        f'<div style="background:{_bg};border:1px solid {_brd};border-radius:12px;padding:1.2rem 1.4rem;">'
        f'{rows_html}</div>',
        unsafe_allow_html=True,
    )


def _render_top_pages(pages: list):
    _section_header("📄 TOP PAGES")
    if not pages:
        _no_data()
        return

    df = pd.DataFrame([
        {
            "Page":           p["path"],
            "Titre":          (p["title"][:45] + "…") if len(p.get("title", "")) > 45 else p.get("title", "—"),
            "Vues":           p["views"],
            "Utilisateurs":   p["users"],
            "Durée moy.":     _fmt_dur(p["avg_duration"]),
            "Taux de rebond": f'{p["bounce_rate"]:.1f}%',
        }
        for p in pages
    ])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Page":           st.column_config.TextColumn("Page",           width="large"),
            "Titre":          st.column_config.TextColumn("Titre",          width="medium"),
            "Vues":           st.column_config.NumberColumn("Vues",         format="%d"),
            "Utilisateurs":   st.column_config.NumberColumn("Utilisateurs", format="%d"),
            "Durée moy.":     st.column_config.TextColumn("Durée moy.",     width="small"),
            "Taux de rebond": st.column_config.TextColumn("Rebond",         width="small"),
        },
    )


def _render_events(events: list):
    _section_header("⚡ ÉVÉNEMENTS")
    if not events:
        _no_data()
        return

    total_events  = sum(e["event_count"] for e in events) or 1
    total_users   = max(e["users"] for e in events) or 1
    total_revenue = sum(e["revenue"] for e in events)

    _dark = st.session_state.get("theme", "dark") == "dark"
    summary = f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("⚡", "Total événements",  f"{total_events:,}",        "#7dd3fc")}
  {_kpi_card("👥", "Utilisateurs",      f"{total_users:,}",         "#4ade80")}
  {_kpi_card("💰", "Revenu total",      f"{total_revenue:,.0f} DZD","#f97316")}
</div>"""
    st.markdown(summary, unsafe_allow_html=True)

    df = pd.DataFrame([
        {
            "#":                          i + 1,
            "Événement":                  e["event"],
            "Nombre d'événements":        e["event_count"],
            "% du total":                 f'{e["pct_events"]}%',
            "Utilisateurs":               e["users"],
            "Événements / utilisateur":   e["events_per_user"],
            "Revenu (DZD)":               e["revenue"],
        }
        for i, e in enumerate(events)
    ])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#":                        st.column_config.NumberColumn("#",                       width="small", format="%d"),
            "Événement":                st.column_config.TextColumn("Événement",                 width="medium"),
            "Nombre d'événements":      st.column_config.NumberColumn("Nombre d'événements",     format="%d"),
            "% du total":               st.column_config.TextColumn("% du total",                width="small"),
            "Utilisateurs":             st.column_config.NumberColumn("Utilisateurs",            format="%d"),
            "Événements / utilisateur": st.column_config.NumberColumn("Événements / utilisateur",format="%.2f"),
            "Revenu (DZD)":             st.column_config.NumberColumn("Revenu (DZD)",            format="%.0f"),
        },
    )


def _render_ecommerce_items(items: list):
    _section_header("🛍️ ACHATS D'E-COMMERCE — TOP ARTICLES")
    if not items or not any(i["viewed"] > 0 for i in items):
        _no_data("Données e-commerce non disponibles — vérifiez que le suivi des articles est configuré dans GA4.")
        return

    total_viewed   = sum(i["viewed"]      for i in items) or 1
    total_cart     = sum(i["add_to_cart"] for i in items) or 1
    total_purchase = sum(i["purchased"]   for i in items) or 1
    total_revenue  = sum(i["revenue"]     for i in items)

    _dark  = st.session_state.get("theme", "dark") == "dark"
    _bg    = "rgba(255,255,255,0.05)" if _dark else "#ffffff"
    _brd   = "none"                    if _dark else "1px solid #e5e7eb"
    _lc    = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _vc    = "#ffffff"                 if _dark else "#111827"

    summary = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_kpi_card("👁️", "Articles consultés",      f"{total_viewed:,}",        "#7dd3fc")}
  {_kpi_card("🛒", "Ajouts au panier",         f"{total_cart:,}",          "#4ade80")}
  {_kpi_card("✅", "Articles achetés",         f"{total_purchase:,}",      "#a78bfa")}
  {_kpi_card("💰", "Revenu total",             f"{total_revenue:,.0f} DZD","#f97316")}
</div>"""
    st.markdown(summary, unsafe_allow_html=True)

    df = pd.DataFrame([
        {
            "#":                     i + 1,
            "Article":               item["name"],
            "Consultés":             item["viewed"],
            "Ajoutés au panier":     item["add_to_cart"],
            "Achetés":               item["purchased"],
            "Revenu (DZD)":          item["revenue"],
        }
        for i, item in enumerate(items)
    ])
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#":                 st.column_config.NumberColumn("#",                  width="small", format="%d"),
            "Article":           st.column_config.TextColumn("Article",              width="large"),
            "Consultés":         st.column_config.NumberColumn("Consultés",          format="%d"),
            "Ajoutés au panier": st.column_config.NumberColumn("Ajoutés au panier",  format="%d"),
            "Achetés":           st.column_config.NumberColumn("Achetés",            format="%d"),
            "Revenu (DZD)":      st.column_config.NumberColumn("Revenu (DZD)",       format="%.0f"),
        },
    )


def _render_purchase_journey(pj: dict):
    _section_header("🛒 PARCOURS D'ACHAT")
    funnel    = pj.get("funnel", [])
    by_device = pj.get("by_device", {})

    if not funnel or not any(s["users"] > 0 for s in funnel):
        _no_data("Données parcours d'achat non disponibles — vérifiez que les événements e-commerce sont configurés dans GA4.")
        return

    _dark    = st.session_state.get("theme", "dark") == "dark"
    _bg      = "rgba(255,255,255,0.03)" if _dark else "#f9fafb"
    _brd     = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"
    _txt_c   = "#ffffff"                 if _dark else "#111827"
    _sub_c   = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _red_c   = "#f87171"

    # ── Overall funnel bars ───────────────────────────────────────────────────
    max_users = max(s["users"] for s in funnel) or 1
    rows_html = ""
    for i, step in enumerate(funnel):
        users   = step["users"]
        bar_pct = round(users / max_users * 100, 1)
        prev    = funnel[i - 1]["users"] if i > 0 else users
        abandon_pct = round((prev - users) / prev * 100, 1) if i > 0 and prev > 0 else None
        abandon_html = (
            f'<span style="font-size:0.65rem;color:{_red_c};margin-left:6px;">▼ {abandon_pct}% abandon</span>'
            if abandon_pct is not None else ""
        )
        rows_html += (
            f'<div style="margin-bottom:0.75rem;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">'
            f'<span style="font-size:0.8rem;color:{_txt_c};font-weight:600;">'
            f'{i+1}. {step["label"]}{abandon_html}</span>'
            f'<span style="font-size:0.78rem;color:{_sub_c};">{users:,} utilisateurs</span>'
            f'</div>'
            f'<div style="background:{_brd};border-radius:6px;height:10px;">'
            f'<div style="background:#E8420A;width:{bar_pct}%;height:10px;border-radius:6px;"></div>'
            f'</div></div>'
        )

    st.markdown(
        f'<div style="background:{_bg};border:1px solid {_brd};border-radius:12px;padding:1.2rem 1.4rem;">'
        f'{rows_html}</div>',
        unsafe_allow_html=True,
    )

    # ── Device breakdown table ────────────────────────────────────────────────
    if by_device:
        st.markdown("<br>", unsafe_allow_html=True)
        _DEVICE_ICONS = {"mobile": "📱", "desktop": "🖥️", "tablet": "📲", "smart tv": "📺"}
        step_events   = [s["event"] for s in funnel]
        step_labels   = [s["label"] for s in funnel]
        devices       = sorted(by_device.keys(), key=lambda d: by_device[d].get("session_start", 0), reverse=True)

        header_cols = ["Appareil"] + step_labels
        rows = []
        for device in devices:
            icon = _DEVICE_ICONS.get(device.lower(), "💻")
            row  = {"Appareil": f"{icon} {device.capitalize()}"}
            for event, label in zip(step_events, step_labels):
                row[label] = f"{by_device[device].get(event, 0):,}"
            rows.append(row)

        import pandas as pd
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Appareil": st.column_config.TextColumn("Appareil", width="small")},
        )


def _render_geography(geo: dict):
    _section_header("🌍 GÉOGRAPHIE")
    countries = geo.get("countries", [])
    cities    = geo.get("cities", [])
    if not countries and not cities:
        _no_data()
        return

    _dark   = st.session_state.get("theme", "dark") == "dark"
    _bg     = "rgba(255,255,255,0.03)" if _dark else "#f9fafb"
    _brd    = "rgba(255,255,255,0.08)" if _dark else "#e5e7eb"
    _txt_c  = "#ffffff"                 if _dark else "#111827"
    _sub_c  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _rank_c = ["#FFD700", "#C0C0C0", "#CD7F32"] + ["rgba(255,255,255,0.3)"] * 20

    def _geo_block(items: list, icon: str, title: str) -> str:
        if not items:
            return (
                f'<div style="background:{_bg};border:1px solid {_brd};border-radius:12px;padding:1.2rem;">'
                f'<p style="font-size:0.9rem;font-weight:700;color:{_txt_c};margin:0 0 8px;">{icon} {title}</p>'
                f'<p style="font-size:0.8rem;color:{_sub_c};margin:0;">Aucune donnée</p></div>'
            )
        max_u = max(i["users"] for i in items) or 1
        rows  = ""
        for i, item in enumerate(items[:10]):
            bar_w = round(item["users"] / max_u * 90, 1)
            rows += (
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">'
                f'<span style="font-size:0.72rem;font-weight:700;color:{_rank_c[i]};'
                f'width:18px;text-align:right;">#{i+1}</span>'
                f'<div style="flex:1;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:2px;">'
                f'<span style="font-size:0.78rem;color:{_txt_c};">{item["name"]}</span>'
                f'<span style="font-size:0.72rem;color:{_sub_c};">'
                f'{_fmt_int(item["users"])} · {item["pct"]}%</span>'
                f'</div>'
                f'<div style="background:{_brd};border-radius:4px;height:5px;">'
                f'<div style="background:#E8420A;width:{bar_w}%;height:5px;border-radius:4px;"></div>'
                f'</div></div></div>'
            )
        return (
            f'<div style="background:{_bg};border:1px solid {_brd};border-radius:12px;padding:1.2rem;">'
            f'<p style="font-size:0.9rem;font-weight:700;color:{_txt_c};margin:0 0 12px;">{icon} {title}</p>'
            f'{rows}</div>'
        )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(_geo_block(countries, "🌐", "Top Pays"), unsafe_allow_html=True)
    with col2:
        st.markdown(_geo_block(cities, "🏙️", "Top Villes"), unsafe_allow_html=True)


def _render_devices(devices: list):
    _section_header("📱 APPAREILS")
    if not devices:
        _no_data()
        return

    _dark   = st.session_state.get("theme", "dark") == "dark"
    _COLORS = ["#E8420A", "#7dd3fc", "#4ade80", "#a78bfa"]
    _ICONS  = {"mobile": "📱", "desktop": "🖥️", "tablet": "📲"}

    labels = [d["device"].capitalize() for d in devices]
    values = [d["users"] for d in devices]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker_colors=_COLORS[:len(labels)],
        textfont=dict(size=12),
        hovertemplate="%{label}<br>%{value:,} utilisateurs<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(**{
        **get_chart_layout(),
        "showlegend": True,
        "legend": dict(orientation="h", y=-0.1),
        "height": 280,
        "margin": dict(l=0, r=0, t=10, b=40),
    })
    st.plotly_chart(fig, use_container_width=True)

    _bg  = "rgba(255,255,255,0.05)" if _dark else "#ffffff"
    _brd = "none"                    if _dark else "1px solid #e5e7eb"
    _lc  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _vc  = "#ffffff"                 if _dark else "#111827"

    cards = ""
    for d in devices:
        icon = _ICONS.get(d["device"].lower(), "💻")
        cards += (
            f'<div style="background:{_bg};border:{_brd};border-radius:12px;padding:0.8rem;text-align:center;">'
            f'<div style="font-size:0.72rem;color:{_lc};">{icon} {d["device"].capitalize()}</div>'
            f'<div style="font-size:1.2rem;font-weight:800;color:{_vc};">{d["pct"]}%</div>'
            f'<div style="font-size:0.68rem;color:{_lc};">{_fmt_int(d["sessions"])} sessions</div>'
            f'<div style="font-size:0.68rem;color:{_lc};">Eng. {_fmt_pct(d["engagement_rate"])}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat({len(devices)},1fr);'
        f'gap:0.6rem;margin-top:0.5rem;">{cards}</div>',
        unsafe_allow_html=True,
    )


def _render_analysis(ov: dict):
    _section_header("🧠 ANALYSE AUTOMATIQUE")
    if not ov:
        _no_data()
        return

    _dark   = st.session_state.get("theme", "dark") == "dark"
    _row_bg = "rgba(255,255,255,0.03)" if _dark else "#f8fafc"
    _lbl_c  = "rgba(255,255,255,0.75)" if _dark else "#111827"
    _txt_c  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"

    bounce   = ov.get("bounce_rate", 0.0)
    duration = ov.get("avg_session_duration", 0.0)
    eng_rate = ov.get("engagement_rate", 0.0)
    pps      = ov.get("pages_per_session", 0.0)
    new_u    = ov.get("new_users", 0)
    total_u  = ov.get("active_users", 1) or 1
    new_pct  = round(new_u / total_u * 100, 1)

    insights: list[tuple[str, str, str]] = []

    if eng_rate >= 60:
        insights.append(("🟢", "Taux d'engagement excellent",   f"{_fmt_pct(eng_rate)} — visiteurs très engagés."))
    elif eng_rate >= 40:
        insights.append(("🟡", "Taux d'engagement correct",     f"{_fmt_pct(eng_rate)} — marge d'amélioration."))
    else:
        insights.append(("🔴", "Taux d'engagement faible",      f"{_fmt_pct(eng_rate)} — revoir l'expérience d'arrivée."))

    if bounce < 40:
        insights.append(("🟢", "Taux de rebond excellent",      f"{_fmt_pct(bounce)} — visiteurs qui explorent."))
    elif bounce < 60:
        insights.append(("🟡", "Taux de rebond correct",        f"{_fmt_pct(bounce)} — dans la norme (40–60 %)."))
    else:
        insights.append(("🔴", "Taux de rebond élevé",          f"{_fmt_pct(bounce)} — beaucoup repartent sans interagir."))

    if duration >= 120:
        insights.append(("🟢", "Bonne durée de session",        f"{_fmt_dur(duration)} — les visiteurs lisent le contenu."))
    elif duration >= 30:
        insights.append(("🟡", "Durée de session courte",       f"{_fmt_dur(duration)} — améliorer le contenu."))
    else:
        insights.append(("🔴", "Durée très courte",             f"{_fmt_dur(duration)} — les visiteurs ne restent pas."))

    if pps >= 3:
        insights.append(("🟢", "Navigation active",             f"{pps:.1f} pages/session — bonne exploration."))
    elif pps >= 1.5:
        insights.append(("🟡", "Navigation limitée",            f"{pps:.1f} pages/session — inciter à explorer davantage."))
    else:
        insights.append(("🔴", "Peu de pages visitées",         f"{pps:.1f} pages/session — améliorer les liens internes."))

    if new_pct > 80:
        insights.append(("💡", "Audience principalement nouvelle", f"{new_pct}% nouveaux — travailler la rétention."))
    elif new_pct > 50:
        insights.append(("💡", "Bon mix acquisition/fidélisation", f"{new_pct}% nouveaux / {100-new_pct:.0f}% récurrents."))
    else:
        insights.append(("💡", "Forte fidélisation",             f"{100-new_pct:.0f}% de visiteurs récurrents — audience fidèle."))

    rows_html = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:0.6rem;background:{_row_bg};'
        f'border-radius:8px;padding:0.55rem 0.8rem;margin-bottom:0.35rem;">'
        f'<span style="font-size:1rem;line-height:1.4;">{dot}</span>'
        f'<div><span style="font-size:0.78rem;font-weight:700;color:{_lbl_c};">{label}</span>'
        f'<span style="font-size:0.78rem;color:{_txt_c};"> — {text}</span></div>'
        f'</div>'
        for dot, label, text in insights
    )
    st.markdown(rows_html, unsafe_allow_html=True)


# ─── Public entry point ────────────────────────────────────────────────────────
def render_analytics_tab(ga4_data: dict, since: str = "", until: str = ""):
    _dark  = st.session_state.get("theme", "dark") == "dark"
    _hdr_c = "#ffffff"                 if _dark else "#111827"
    _sub_c = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"

    st.markdown(
        f'<p style="font-size:1.4rem;font-weight:800;letter-spacing:0.08em;'
        f'color:{_hdr_c};margin:0 0 0.2rem;">GOOGLE ANALYTICS 4</p>'
        f'<p style="font-size:0.8rem;color:{_sub_c};margin:0 0 1rem;">'
        f'Comportement des visiteurs · footland.dz</p>',
        unsafe_allow_html=True,
    )

    if not ga4_data or not ga4_data.get("overview"):
        _no_data("Données Google Analytics non disponibles. Vérifiez que le token GA4 est configuré.")
        return

    # ── Context for AI chatbot ────────────────────────────────────────────────
    _ov = ga4_data.get("overview", {})

    # Flags broken tracking before the reader takes the KPI cards at face value.
    publish_alerts("ga4", check_all(ga4_overview=_ov))

    _ctx_ga4 = {
        "period": f"{since} → {until}",
        "active_users": _ov.get("active_users", 0),
        "new_users": _ov.get("new_users", 0),
        "sessions": _ov.get("sessions", 0),
        "engaged_sessions": _ov.get("engaged_sessions", 0),
        "engagement_rate": _ov.get("engagement_rate", 0.0),
        "bounce_rate": _ov.get("bounce_rate", 0.0),
    }

    # Previous period, for the AI report's rise/fall analysis. GA4 is the only
    # source with no comparison already in scope, so fetch just the overview
    # block (cached) rather than the full eight-section payload.
    if since and until:
        try:
            from datetime import date, timedelta

            from api.ga4 import fetch_ga4_overview

            _s, _u = date.fromisoformat(since), date.fromisoformat(until)
            _span = (_u - _s).days + 1
            _prev_u = _s - timedelta(days=1)
            _prev_s = _prev_u - timedelta(days=_span - 1)

            @st.cache_data(ttl=3600, show_spinner=False)
            def _ga4_prev_overview(a: str, b: str) -> dict:
                return fetch_ga4_overview(a, b)

            _prev_ov = _ga4_prev_overview(str(_prev_s), str(_prev_u))
            if _prev_ov:
                _ctx_ga4["_prev"] = {
                    k: v for k, v in {
                        "active_users":     _prev_ov.get("active_users", 0),
                        "new_users":        _prev_ov.get("new_users", 0),
                        "sessions":         _prev_ov.get("sessions", 0),
                        "engaged_sessions": _prev_ov.get("engaged_sessions", 0),
                        "engagement_rate":  _prev_ov.get("engagement_rate", 0.0),
                        "bounce_rate":      _prev_ov.get("bounce_rate", 0.0),
                    }.items() if v
                }
                _ctx_ga4["period"] += f"  (comparé à {_prev_s} → {_prev_u})"
        except Exception as _e:  # noqa: BLE001 - comparison is optional
            print(f"DEBUG ga4 prev overview: {_e}")

    # Channel split is the single most telling figure on this tab — it shows how
    # much of the traffic is actually bought.
    _srcs = ga4_data.get("traffic_sources", []) or []
    if _srcs:
        _ctx_ga4["_notes"] = ["Répartition du trafic par canal (sessions) : " + " | ".join(
            f"{s.get('channel', '—')} {s.get('sessions', 0)}"
            for s in sorted(_srcs, key=lambda s: -s.get("sessions", 0))[:6]
        )]

    st.session_state["ctx_ga4"] = _ctx_ga4

    t1, t2, t3, t4 = st.tabs([
        "📊 Vue d'ensemble",
        "🛒 E-commerce",
        "⚡ Événements",
        "🌍 Audience",
    ])

    with t1:
        render_alerts()
        _render_overview(ga4_data.get("overview", {}))
        st.divider()
        _render_traffic_sources(ga4_data.get("traffic_sources", []))

    with t2:
        render_alerts()
        _render_purchase_journey(ga4_data.get("purchase_journey", {}))
        st.divider()
        _render_ecommerce_items(ga4_data.get("ecommerce_items", []))

    with t3:
        render_alerts()
        _render_events(ga4_data.get("events", []))

    with t4:
        render_alerts()
        _render_geography(ga4_data.get("geography", {}))
        st.divider()
        _render_devices(ga4_data.get("devices", []))


    # Discreet entry point at the bottom of the page.
    render_ai_report(
        "Google Analytics — trafic du site footland.dz",
        st.session_state.get("ctx_ga4"),
        key="ga4",
        kind="web",
    )
