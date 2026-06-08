import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed

import db
from components.charts import get_chart_layout, series_to_df, safe_sum, render_top3_podium
from components.skeleton import skeleton_dashboard_html, skeleton_charts_html


# ─── Cached fetchers ──────────────────────────────────────────────────────────
@st.cache_data(ttl=None, show_spinner=False)
def get_ig_profile(days, start=None, end=None):
    return db.get_ig_profile(days, start, end)

@st.cache_data(ttl=None, show_spinner=False)
def get_ig_engagement(days, start=None, end=None):
    return db.get_ig_engagement(days, start, end)

@st.cache_data(ttl=None, show_spinner=False)
def get_ig_posts(days, start=None, end=None):
    return db.get_ig_posts(days, start, end)


# ─── Post card helper ─────────────────────────────────────────────────────────
def _render_ig_post_card(post: dict):
    _dark = st.session_state.get("theme", "dark") == "dark"

    thumbnail = post.get("thumbnail", "")
    text      = post.get("text", "")[:100] or "*(No caption)*"
    date      = post.get("created_time", "")
    reacs     = post.get("reactions", 0)
    comms     = post.get("comments", 0)
    saves     = post.get("saves", 0)
    shares    = post.get("shares", 0)
    total     = post.get("total_interactions", 0)
    imp_val   = post.get("impressions", 0)
    reach_val = post.get("reach", 0)
    permalink = post.get("permalink", "#")

    # ── Theme tokens ──
    _cell_bg   = "rgba(255,255,255,0.05)" if _dark else "#f8fafc"
    _cell_brd  = "" if _dark else "border:1px solid #e5e7eb;"
    _cell_lc   = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _cell_vc   = "#ffffff" if _dark else "#111827"
    _date_c    = "rgba(255,255,255,0.45)" if _dark else "#9ca3af"
    _text_c    = "rgba(255,255,255,0.85)" if _dark else "#111827"
    _no_img_bg = "rgba(255,255,255,0.05)" if _dark else "#f3f4f6"
    _no_img_tc = "rgba(255,255,255,0.3)"  if _dark else "#d1d5db"
    _total_lc  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
    _total_bg  = "rgba(232,66,10,0.15)"   if _dark else "rgba(232,66,10,0.08)"

    if thumbnail:
        st.image(thumbnail, use_container_width=True)
    else:
        st.markdown(
            f'<div style="height:160px;background:{_no_img_bg};'
            f'border-radius:12px;display:flex;align-items:center;'
            f'justify-content:center;color:{_no_img_tc};">📷 No image</div>',
            unsafe_allow_html=True
        )

    st.markdown(
        f'<p style="font-size:0.75rem;color:{_date_c};margin:0.3rem 0 0.1rem;">{date}</p>'
        f'<p style="font-size:0.82rem;color:{_text_c};line-height:1.4;margin-bottom:0.5rem;">{text}</p>',
        unsafe_allow_html=True
    )

    def _cell(icon, label, value, color=None):
        _vc = color if color else _cell_vc
        return (
            f'<div style="background:{_cell_bg};{_cell_brd}border-radius:8px;padding:0.5rem 0.6rem;">'
            f'<div style="font-size:0.7rem;color:{_cell_lc};">{icon} {label}</div>'
            f'<div style="font-size:1rem;font-weight:700;color:{_vc};">{value:,}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.4rem;margin:0.5rem 0;">'
        f'{_cell("📢", "Impressions", imp_val)}'
        f'{_cell("👁️", "Couverture",  reach_val)}'
        f'{_cell("❤️", "Réactions",   reacs, "#f87171")}'
        f'{_cell("💬", "Commentaires",comms, "#a78bfa")}'
        f'{_cell("🔖", "Enregistrements", saves, "#60a5fa")}'
        f'{_cell("↗️", "Partages",    shares, "#34d399")}'
        f'</div>'
        f'<div style="background:{_total_bg};border-radius:8px;padding:0.5rem 0.7rem;margin-bottom:0.5rem;">'
        f'<div style="font-size:0.7rem;color:{_total_lc};">⚡ Total interactions</div>'
        f'<div style="font-size:1.1rem;font-weight:800;color:#FF6B35;">{total:,}</div>'
        f'</div>'
        f'<a href="{permalink}" target="_blank" style="font-size:0.75rem;color:#6c8ebf;text-decoration:none;">'
        f'🔗 Voir la publication</a><br><br>',
        unsafe_allow_html=True
    )


# ─── Main render function ─────────────────────────────────────────────────────
def render_instagram_dashboard(period_label: str, days: int, start_date, end_date, log_refresh_fn):
    st.warning("⚠️ Under repair. Will be fixed soon.")
    # ── Compute previous equivalent period dates ──────────────────────────────
    from datetime import datetime as _vdt, timedelta as _vtd, timezone as _vtz
    if start_date and end_date:
        _s    = _vdt.strptime(start_date, "%Y-%m-%d").date()
        _e    = _vdt.strptime(end_date,   "%Y-%m-%d").date()
        _span = (_e - _s).days + 1
        _prev_e = _s - _vtd(days=1)
        _prev_s = _prev_e - _vtd(days=_span - 1)
    else:
        _prev_e = _vdt.now(_vtz.utc).date() - _vtd(days=days)
        _prev_s = _prev_e - _vtd(days=days - 1)
    _prev_start, _prev_end = str(_prev_s), str(_prev_e)

    # ── Phase 1: skeleton → all KPI + post data ──────────────────────────────
    # prev_posts (only needed for engagement deltas) is deferred to phase 2.
    _skel = st.empty()
    _skel.markdown(skeleton_dashboard_html(n_kpis=4), unsafe_allow_html=True)

    fast_fetchers = {
        "profile":      lambda: get_ig_profile(days, start_date, end_date),
        "eng":          lambda: get_ig_engagement(days, start_date, end_date),
        "posts":        lambda: get_ig_posts(days, start_date, end_date),
        "prev_profile": lambda: get_ig_profile(days, _prev_start, _prev_end),
    }
    fast = {}
    with ThreadPoolExecutor(max_workers=len(fast_fetchers)) as pool:
        futs = {pool.submit(fn): key for key, fn in fast_fetchers.items()}
        for fut in as_completed(futs):
            key = futs[fut]
            try:
                fast[key] = fut.result()
            except Exception as e:
                print(f"DEBUG ig fast fetch {key} error: {e}")
                fast[key] = {} if key != "posts" else []

    ig_profile   = fast["profile"]
    ig_eng       = fast["eng"]
    ig_posts     = fast["posts"]
    prev_profile = fast.get("prev_profile", {})

    followers          = ig_profile.get("followers_count") or 0
    follower_additions = ig_profile.get("follower_additions", [])
    total_ig_reach     = ig_profile.get("period_reach", 0) or safe_sum(ig_profile.get("reach", []))

    # Reach availability — Instagram's metric_type=total_value only works for ≤ 30 days
    from datetime import datetime as _vdt2
    if start_date and end_date:
        _ig_w = (_vdt2.strptime(end_date, "%Y-%m-%d").date()
               - _vdt2.strptime(start_date, "%Y-%m-%d").date()).days + 1
    else:
        _ig_w = days
    _ig_reach_unavailable = _ig_w > 30
    _ig_reach_display = "—" if _ig_reach_unavailable else f"{total_ig_reach:,}"
    _ig_reach_note    = "ℹ️ Indisponible pour cette période" if _ig_reach_unavailable else None

    # Account-level views — single API call: /{ig_user_id}/insights?metric=views
    # &period=day&metric_type=total_value — covers posts + reels + stories.
    total_ig_views = ig_eng.get("views", 0)

    # Use account-level insights (metric_type=total_value) — covers ALL posts in the period,
    # not just the 20 shown in the Top Content tab. Falls back to per-post sums only if
    # the account insights call returned 0 (e.g. API error or very short period).
    total_ig_likes    = ig_eng.get("likes",    0) or sum(p.get("reactions", 0) for p in ig_posts)
    total_ig_comments = ig_eng.get("comments", 0) or sum(p.get("comments",  0) for p in ig_posts)
    total_ig_shares   = ig_eng.get("shares",   0) or sum(p.get("shares",    0) for p in ig_posts)
    total_ig_saves    = ig_eng.get("saves",    0) or sum(p.get("saves",     0) for p in ig_posts)
    # total_interactions fetched directly from API (may differ slightly from the sum above)
    total_ig_interactions = (
        ig_eng.get("total_interactions", 0)
        or (total_ig_likes + total_ig_comments + total_ig_shares + total_ig_saves)
    )

    ig_eng_rate = (
        round(total_ig_interactions / total_ig_reach * 100, 2)
        if total_ig_reach and not _ig_reach_unavailable else 0.0
    )
    _ig_eng_rate_display = "—" if _ig_reach_unavailable else f"{ig_eng_rate}%"

    # ── Delta helpers ─────────────────────────────────────────────────────────
    def _d(curr, prev):
        try:
            return round((curr - prev) / abs(prev) * 100, 1) if prev else None
        except Exception:
            return None

    _prev_followers  = prev_profile.get("followers_count") or 0
    _prev_ig_reach   = prev_profile.get("period_reach", 0) or safe_sum(prev_profile.get("reach", []))
    # prev_posts loads in phase 2 — engagement deltas computed after charts render
    _prev_ig_views        = 0
    _prev_ig_likes        = 0
    _prev_ig_comments     = 0
    _prev_ig_shares       = 0
    _prev_ig_saves        = 0
    _prev_ig_interactions = 0

    # ── KPI Grid ──────────────────────────────────────────────────────────────
    _dark = st.session_state.get("theme", "dark") == "dark"
    def _ig_kpi(icon, label, value, color=None, delta=None, note=None):
        _bg  = "rgba(255,255,255,0.05)" if _dark else "#ffffff"
        _brd = "none" if _dark else "1px solid #e5e7eb"
        _lc  = "rgba(255,255,255,0.45)" if _dark else "#6b7280"
        _nc  = "rgba(255,255,255,0.3)"  if _dark else "#9ca3af"
        _vc  = color if color else ("#ffffff" if _dark else "#111827")
        if delta is not None:
            _dc = "#4ade80" if delta > 0 else "#f87171" if delta < 0 else "#a1a1aa"
            _arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            _sign  = "+" if delta > 0 else ""
            _delta_html = (
                f'<div style="font-size:0.65rem;color:{_dc};margin-top:0.15rem;">'
                f'{_arrow} {_sign}{delta:.1f}%</div>'
            )
        else:
            _delta_html = ""
        _note_html = (
            f'<div style="font-size:0.62rem;color:{_nc};margin-top:0.15rem;'
            f'white-space:normal;line-height:1.35;">{note}</div>'
        ) if note else ""
        return (
            f'<div style="background:{_bg};border:{_brd};border-radius:12px;'
            f'padding:0.9rem 1rem;text-align:center;">'
            f'<div style="font-size:0.72rem;color:{_lc};'
            f'margin-bottom:0.25rem;">{icon} {label}</div>'
            f'<div style="font-size:1.35rem;font-weight:800;color:{_vc};'
            f'white-space:nowrap;">{value}</div>'
            f'{_delta_html}'
            f'{_note_html}'
            f'</div>'
        )

    # Clear phase 1 skeleton, render KPI row in its place
    _skel.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin-bottom:0.6rem;">
  {_ig_kpi("👥", "Followers",         f"{followers:,}",       delta=_d(followers,             _prev_followers))}
  {_ig_kpi("📝", "Publications",      str(len(ig_posts)),     delta=None)}
  {_ig_kpi("📊", "Taux d'engagement", _ig_eng_rate_display, "#facc15")}
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.6rem;margin-bottom:0.6rem;">
  {_ig_kpi("👁️", "Couvertures",        _ig_reach_display, note=_ig_reach_note,
           delta=None if _ig_reach_unavailable else _d(total_ig_reach, _prev_ig_reach))}
  {_ig_kpi("👁️", "Vues",               f"{total_ig_views:,}",      delta=_d(total_ig_views,       _prev_ig_views))}
  {_ig_kpi("🔖", "Enregistrements",    f"{total_ig_saves:,}", "#60a5fa", delta=_d(total_ig_saves,  _prev_ig_saves))}
</div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.6rem;margin-bottom:1rem;">
  {_ig_kpi("🔥", "Total interactions", f"{total_ig_interactions:,}", "#FF6B35", delta=_d(total_ig_interactions, _prev_ig_interactions))}
  {_ig_kpi("❤️", "Réactions",   f"{total_ig_likes:,}",    "#f87171", delta=_d(total_ig_likes,    _prev_ig_likes))}
  {_ig_kpi("💬", "Commentaires", f"{total_ig_comments:,}", "#a78bfa", delta=_d(total_ig_comments, _prev_ig_comments))}
  {_ig_kpi("↗️", "Partages",     f"{total_ig_shares:,}",   "#34d399", delta=_d(total_ig_shares,   _prev_ig_shares))}
</div>
""", unsafe_allow_html=True)

    st.divider()

    # ── Phase 2: chart skeleton → prev_posts (for engagement deltas) ─────────
    _chart_skel = st.empty()
    _chart_skel.markdown(skeleton_charts_html(n_charts=2, n_cards=3), unsafe_allow_html=True)

    prev_ig_posts = get_ig_posts(days, _prev_start, _prev_end)

    _chart_skel.markdown('<div style="display:none"></div>', unsafe_allow_html=True)

    log_refresh_fn(
        "Instagram", period_label, "✅ Data Loaded",
        f"Followers: {followers}, Posts: {len(ig_posts)}, Reach: {total_ig_reach}"
    )

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab1, tab2 = st.tabs([
        "📡Visibility", "💬Engagement"
    ])

    # ── TAB 1: Engagement ─────────────────────────────────────────────────────
    with tab2:
        # Build daily series from posts
        _ci_d, _likes_d, _comms_d, _saves_d = {}, {}, {}, {}
        for p in ig_posts:
            d = p.get("created_time", "")[:10]
            if not d:
                continue
            _ci_d[d]    = _ci_d.get(d, 0)    + p.get("total_interactions", 0)
            _likes_d[d] = _likes_d.get(d, 0) + p.get("reactions", 0)
            _comms_d[d] = _comms_d.get(d, 0) + p.get("comments", 0)
            _saves_d[d] = _saves_d.get(d, 0) + p.get("saves", 0)

        def _make_series(mapping):
            if not mapping:
                return pd.DataFrame()
            return pd.DataFrame(
                [{"date": pd.Timestamp(k), "value": v}
                 for k, v in sorted(mapping.items())]
            )

        ci_df    = _make_series(_ci_d)
        likes_df = _make_series(_likes_d)
        comms_df = _make_series(_comms_d)
        saves_df = _make_series(_saves_d)

        # Fill full date range with zeros
        if not ci_df.empty and (start_date or days):
            _range_start = (pd.Timestamp(start_date) if start_date else pd.Timestamp.now() - pd.Timedelta(days=days)).normalize()
            _range_end   = (pd.Timestamp(end_date)   if end_date   else pd.Timestamp.now()).normalize()
            _full_range  = pd.DataFrame({"date": pd.date_range(_range_start, _range_end, freq="D")})
            ci_df    = _full_range.merge(ci_df,    on="date", how="left").fillna(0)
            likes_df = _full_range.merge(likes_df, on="date", how="left").fillna(0)
            comms_df = _full_range.merge(comms_df, on="date", how="left").fillna(0)
            saves_df = _full_range.merge(saves_df, on="date", how="left").fillna(0)

        if not ci_df.empty:
            # Dynamic Y-axis ceiling scaled to actual data — no hardcoded minimums
            _y1_raw = max(
                float(ci_df["value"].max()) if not ci_df.empty else 0,
                float(likes_df["value"].max()) if not likes_df.empty else 0,
            )
            _y1_max = max(_y1_raw * 1.3, 10)

            _y2_raw = max(
                float(comms_df["value"].max()) if not comms_df.empty else 0,
                float(saves_df["value"].max()) if not saves_df.empty else 0,
            )
            _y2_max = max(_y2_raw * 1.5, 5)

            fig_eng = go.Figure()
            # ── Primary axis (left): Total interactions + Réactions ──────────
            fig_eng.add_trace(go.Scatter(
                x=ci_df["date"], y=ci_df["value"],
                name="Total interactions",
                line=dict(color="#FF6B35", width=3), mode="lines",
                yaxis="y1",
            ))
            fig_eng.add_trace(go.Scatter(
                x=likes_df["date"], y=likes_df["value"],
                name="Réactions",
                line=dict(color="#f87171", width=2), mode="lines",
                yaxis="y1",
            ))
            # ── Secondary axis (right): Commentaires + Enregistrements ───────
            fig_eng.add_trace(go.Scatter(
                x=comms_df["date"], y=comms_df["value"],
                name="Commentaires (→)",
                line=dict(color="#a78bfa", width=2, dash="dot"), mode="lines",
                yaxis="y2",
            ))
            fig_eng.add_trace(go.Scatter(
                x=saves_df["date"], y=saves_df["value"],
                name="Enregistrements (→)",
                line=dict(color="#60a5fa", width=2, dash="dot"), mode="lines",
                yaxis="y2",
            ))
            fig_eng.update_layout(**{
                **get_chart_layout(),
                "yaxis": dict(
                    gridcolor="rgba(255,255,255,0.06)" if _dark else "#e5e7eb", showline=False,
                    tickformat=",", range=[0, _y1_max],
                    title=dict(text="Interactions", font=dict(size=10, color="rgba(255,255,255,0.3)" if _dark else "#9ca3af")),
                ),
                "yaxis2": dict(
                    overlaying="y", side="right",
                    gridcolor="rgba(255,255,255,0)", showline=False,
                    tickformat=",", range=[0, _y2_max],
                    title=dict(text="Commentaires / Enreg.", font=dict(size=10, color="rgba(255,255,255,0.3)" if _dark else "#9ca3af")),
                ),
                "xaxis": dict(
                    gridcolor="rgba(255,255,255,0.06)", showline=False,
                    tickmode="array",
                    tickvals=[ci_df["date"].iloc[i]
                              for i in range(0, len(ci_df), max(len(ci_df)//6, 1))][:7],
                    tickangle=0,
                ),
                "showlegend": True,
                "legend": dict(
                    orientation="h", yanchor="bottom", y=-0.28,
                    xanchor="center", x=0.5,
                    font=dict(size=11, color="rgba(255,255,255,0.6)" if _dark else "#6b7280"),
                    bgcolor="rgba(0,0,0,0)",
                ),
                "margin": dict(l=0, r=40, t=10, b=70),
                "height": 320,
            })
            st.plotly_chart(fig_eng, width="stretch")

            ei1, ei2, ei3, ei4 = st.columns(4)
            ei1.metric("Total interactions", f"{total_ig_interactions:,}")
            ei2.metric("Réactions",          f"{total_ig_likes:,}")
            ei3.metric("Commentaires",       f"{total_ig_comments:,}")
            ei4.metric("Enregistrements",    f"{total_ig_saves:,}")
        else:
            st.info("No engagement data available for this period.")

        # ── Best Time to Post heatmap (admin only) ────────────────────────────
        _is_admin = st.session_state.get("user", {}).get("role") == "admin"
        if _is_admin:
            st.divider()
            st.markdown(
                f'<div style="text-align:center;margin:0.5rem 0 1rem;">'
                f'<span style="font-size:1.1rem;font-weight:700;text-transform:uppercase;'
                f'letter-spacing:0.08em;color:{"#ffffff" if _dark else "#111827"};">'
                f'⏰ Meilleur moment pour publier</span>'
                f'<div style="height:3px;width:60px;background:linear-gradient(90deg,#E8420A,#FF6B35);'
                f'border-radius:2px;margin:0.4rem auto 0;"></div></div>',
                unsafe_allow_html=True,
            )
            _hm_posts = [p for p in ig_posts if p.get("post_hour", -1) >= 0]
            if _hm_posts:
                st.markdown(
                    f'<div style="font-size:0.75rem;color:{"rgba(255,255,255,0.45)" if _dark else "#6b7280"};text-align:center;margin-bottom:0.8rem;">'
                    f'Interactions moyennes par heure et jour de publication (UTC) — basé sur {len(_hm_posts)} publications</div>',
                    unsafe_allow_html=True,
                )

                _days_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
                _hours   = list(range(24))
                _totals = [[0.0] * 24 for _ in range(7)]
                _counts = [[0]   * 24 for _ in range(7)]
                for p in _hm_posts:
                    d, h = p["post_weekday"], p["post_hour"]
                    if 0 <= d <= 6 and 0 <= h <= 23:
                        _totals[d][h] += p.get("total_interactions", 0)
                        _counts[d][h] += 1

                _matrix    = []
                _text_mat  = []
                for d in range(7):
                    _row, _trow = [], []
                    for h in range(24):
                        if _counts[d][h] > 0:
                            avg = round(_totals[d][h] / _counts[d][h], 1)
                            _row.append(avg)
                            _trow.append(f"{avg:.0f} interactions<br>{_counts[d][h]} post(s)")
                        else:
                            _row.append(None)
                            _trow.append("")
                    _matrix.append(_row)
                    _text_mat.append(_trow)

                fig_hm = go.Figure(data=go.Heatmap(
                    z=_matrix,
                    x=[f"{h:02d}h" for h in _hours],
                    y=_days_fr,
                    text=_text_mat,
                    hovertemplate="<b>%{y} %{x}</b><br>%{text}<extra></extra>",
                    colorscale=[
                        [0.0,  "rgba(232,66,10,0.08)"],
                        [0.25, "rgba(232,66,10,0.3)"],
                        [0.5,  "rgba(232,66,10,0.55)"],
                        [0.75, "rgba(232,66,10,0.8)"],
                        [1.0,  "#E8420A"],
                    ],
                    showscale=True,
                    colorbar=dict(
                        title=dict(text="Moy. interactions", font=dict(size=11)),
                        thickness=12, len=0.8,
                    ),
                    xgap=2, ygap=2,
                ))
                fig_hm.update_layout(**{
                    **get_chart_layout(),
                    "height": 300,
                    "margin": dict(l=0, r=60, t=10, b=40),
                    "xaxis": dict(side="bottom", tickfont=dict(size=10), showline=False),
                    "yaxis": dict(tickfont=dict(size=11), showline=False, autorange="reversed"),
                })
                st.plotly_chart(fig_hm, width="stretch")

                _best_val, _best_d, _best_h = 0, 0, 0
                for d in range(7):
                    for h in range(24):
                        if _counts[d][h] > 0:
                            avg = _totals[d][h] / _counts[d][h]
                            if avg > _best_val:
                                _best_val, _best_d, _best_h = avg, d, h
                if _best_val > 0:
                    _note_bg = "rgba(232,66,10,0.08)" if _dark else "rgba(232,66,10,0.06)"
                    _note_tc = "rgba(255,255,255,0.7)" if _dark else "#374151"
                    st.markdown(
                        f'<div style="background:{_note_bg};border-left:3px solid #E8420A;'
                        f'border-radius:0 8px 8px 0;padding:0.6rem 1rem;margin-top:0.5rem;'
                        f'font-size:0.85rem;color:{_note_tc};">'
                        f'🏆 Meilleur créneau : <b style="color:#E8420A;">{_days_fr[_best_d]} à {_best_h:02d}h</b> '
                        f'— moyenne de <b style="color:#E8420A;">{_best_val:.0f} interactions</b> par publication.'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                _nb = "rgba(232,66,10,0.08)" if _dark else "rgba(232,66,10,0.06)"
                _tc = "rgba(255,255,255,0.7)" if _dark else "#374151"
                st.markdown(
                    f'<div style="background:{_nb};border-left:3px solid #E8420A;border-radius:0 8px 8px 0;'
                    f'padding:0.8rem 1.2rem;font-size:0.9rem;color:{_tc};">'
                    f'🔄 Cliquez sur <b>Refresh Data</b> dans la barre latérale pour activer ce graphique.'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── TAB 2: Visibility ─────────────────────────────────────────────────────
    with tab1:
        reach_df = series_to_df(ig_profile.get("reach", []))

        # ── Fallbacks: build daily series from per-post data when account-level
        #    API series are blocked/empty. Posts are grouped by publication date.
        def _posts_daily(metric: str) -> pd.DataFrame:
            """Aggregate per-post metric by date → DataFrame with date/value columns."""
            _d: dict = {}
            for p in ig_posts:
                _date = p.get("created_time", "")[:10]
                if _date:
                    _d[_date] = _d.get(_date, 0) + p.get(metric, 0)
            if not _d:
                return pd.DataFrame()
            return pd.DataFrame(
                [{"date": pd.Timestamp(k), "value": v} for k, v in sorted(_d.items())]
            )

        _reach_from_posts = False

        if reach_df.empty and ig_posts:
            reach_df = _posts_daily("reach")
            _reach_from_posts = not reach_df.empty

        # ── Reach chart ──
        if not reach_df.empty:
            _reach_src = (
                ' <span style="font-size:0.62rem;color:rgba(255,165,0,0.7);'
                'font-weight:400;letter-spacing:0;">(estimé — agrégé depuis les publications)</span>'
                if _reach_from_posts else ""
            )
            _vis_hdr_c   = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"
            _vis_hdr_brd = "rgba(255,255,255,0.08)"  if _dark else "#e5e7eb"
            st.markdown(
                f'<div style="font-size:0.68rem;color:{_vis_hdr_c};'
                f'text-transform:uppercase;letter-spacing:0.08em;'
                f'margin:0 0 0.6rem;border-bottom:1px solid {_vis_hdr_brd};'
                f'padding-bottom:0.4rem;">👁️ COUVERTURES (REACH){_reach_src}</div>',
                unsafe_allow_html=True
            )
            fig_reach = go.Figure()
            fig_reach.add_trace(go.Scatter(
                x=reach_df["date"], y=reach_df["value"],
                name="Reach", fill="tozeroy",
                line=dict(color="#6366f1", width=2),
                fillcolor="rgba(99,102,241,0.15)",
                mode="lines+markers",
                marker=dict(size=4, color="#6366f1"),
            ))
            fig_reach.update_layout(**{
                **get_chart_layout(),
                "showlegend": False,
                "margin": dict(l=0, r=0, t=10, b=30),
                "height": 220,
            })
            st.plotly_chart(fig_reach, width="stretch")

            r1, r2, r3 = st.columns(3)
            r1.metric("Total Reach",       f"{total_ig_reach:,}")
            _peak_r = reach_df.loc[reach_df["value"].idxmax()]
            r2.metric("Pic", _peak_r["date"].strftime("%b %d"), delta=f"{int(_peak_r['value']):,}")
            r3.metric("Moy. journalière",  f"{int(reach_df['value'].mean()):,}")

        if reach_df.empty:
            st.info("No visibility data available for this period.")

