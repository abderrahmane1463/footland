"""
components/alerts.py — Rule-based alerting for the Footland dashboard.

Detection is deliberately plain Python rather than AI. A threshold either fires
or it does not, identically on every run, and can be unit-tested. A model asked
"is anything wrong here?" would answer differently on identical data, which is
the wrong foundation for something meant to interrupt someone.

Thresholds come from Footland's own baseline — CPC ~0,005 EUR, CPM ~0,119 EUR,
cost per order 1,35-2,01 EUR — not from European benchmarks, which are off by
more than an order of magnitude on this market and would either never fire or
fire constantly.

Two market specifics are baked in:

- Cash on delivery. A Meta "purchase" is an order placed, not money received.
  Real cost per delivered order is materially higher than what is measured
  here, so the thresholds are deliberately loose.
- Objectives are not comparable. An awareness campaign has no orders by design
  and runs a CTR around 0,12 %; a sales campaign runs near 6,9 %. Rules that
  ignore that would condemn every awareness campaign permanently.

Currently LOG-ONLY: alerts render in the dashboard and print to the server log
so their firing frequency can be counted before anyone is notified. Anything
firing more than about twice a week is mistuned, not informative.
"""

import streamlit as st

# ─── Thresholds ───────────────────────────────────────────────────────────────
# Cost per order. Observed baseline across the Rapport tab: 1,35 EUR (Soldes
# Femme) to 2,01 EUR (Clarks). 3 EUR is therefore a real deviation, not noise.
COST_PER_ORDER_WARN = 3.0
COST_PER_ORDER_CRIT = 5.0

# Ignore small campaigns: a 12 EUR test with no orders yet is not a problem,
# and alerting on it is how an alert system gets muted.
MIN_SPEND_FOR_ORDER_ALERT = 50.0

# Saturation. Frequency was 1,52 and is now 1,89 — rising but not yet critical.
FREQUENCY_WARN = 2.5
FREQUENCY_CRIT = 3.0
# Neither signal proves much alone; together they are the specific signature of
# audience saturation, so the pair fires at a lower bar than either would.
SATURATION_FREQ_RISE_PCT = 15.0
SATURATION_CTR_DROP_PCT = 15.0

# Data integrity: page views far below sessions means tracking is broken, not
# that visitors saw nothing. Observed: 12 page views against 628 962 sessions.
GA4_MIN_PAGEVIEWS_PER_SESSION = 0.5
GA4_MIN_SESSIONS_TO_CHECK = 1000

# Objectives that are supposed to produce orders. Applying order-based rules to
# awareness or engagement campaigns would fire on every single one of them.
_ORDER_OBJECTIVES = {"OUTCOME_SALES", "CONVERSIONS"}

CRITICAL = "critical"
WARNING = "warning"


def _alert(rule: str, severity: str, title: str, detail: str, scope: str) -> dict:
    return {"rule": rule, "severity": severity, "title": title,
            "detail": detail, "scope": scope}


def _pct_change(current, previous) -> float | None:
    try:
        cur, prev = float(current), float(previous)
    except (TypeError, ValueError):
        return None
    if not prev:
        return None
    return (cur - prev) / abs(prev) * 100


# ─── Rule 1 — money burning ───────────────────────────────────────────────────
def check_cost_per_order(campaigns: list) -> list:
    """Sales campaigns whose cost per order has drifted, or that produce none.

    Only sales-objective campaigns are considered: an awareness campaign with
    zero orders is working as intended, not failing.
    """
    alerts = []
    for c in campaigns or []:
        if c.get("objective") not in _ORDER_OBJECTIVES:
            continue
        spend = c.get("spend", 0) or 0
        if spend < MIN_SPEND_FOR_ORDER_ALERT:
            continue

        name = (c.get("name") or "—")[:60]
        orders = c.get("conversions", 0) or 0

        if orders == 0:
            alerts.append(_alert(
                "cost_per_order", CRITICAL,
                "Campagne sans commande",
                f"« {name} » a dépensé {spend:.2f} EUR sans générer de commande.",
                "boost",
            ))
            continue

        cpo = spend / orders
        if cpo >= COST_PER_ORDER_CRIT:
            alerts.append(_alert(
                "cost_per_order", CRITICAL,
                "Coût par commande très élevé",
                f"« {name} » : {cpo:.2f} EUR par commande "
                f"({orders} commandes pour {spend:.2f} EUR). "
                f"Référence habituelle : 1,35 à 2,00 EUR.",
                "boost",
            ))
        elif cpo >= COST_PER_ORDER_WARN:
            alerts.append(_alert(
                "cost_per_order", WARNING,
                "Coût par commande en dérive",
                f"« {name} » : {cpo:.2f} EUR par commande "
                f"({orders} commandes pour {spend:.2f} EUR). "
                f"Référence habituelle : 1,35 à 2,00 EUR.",
                "boost",
            ))
    return alerts


# ─── Rule 2 — audience saturation ─────────────────────────────────────────────
def check_saturation(totals: dict, prev_totals: dict | None) -> list:
    """Frequency climbing while CTR falls — the signature of a worn audience."""
    alerts = []
    totals = totals or {}
    freq = totals.get("frequency", 0) or 0

    if freq >= FREQUENCY_CRIT:
        alerts.append(_alert(
            "saturation", CRITICAL,
            "Répétition critique",
            f"La répétition atteint {freq:.2f} : les mêmes personnes voient les "
            f"publicités trop souvent. Élargir le ciblage ou renouveler les créas.",
            "boost",
        ))
    elif freq >= FREQUENCY_WARN:
        alerts.append(_alert(
            "saturation", WARNING,
            "Répétition élevée",
            f"La répétition atteint {freq:.2f} (seuil d'alerte {FREQUENCY_WARN}).",
            "boost",
        ))

    # The combined signal, which catches saturation building before the
    # absolute threshold is reached.
    freq_var = _pct_change(freq, (prev_totals or {}).get("frequency"))
    ctr_var = _pct_change(totals.get("ctr"), (prev_totals or {}).get("ctr"))
    if (freq_var is not None and ctr_var is not None
            and freq_var >= SATURATION_FREQ_RISE_PCT
            and ctr_var <= -SATURATION_CTR_DROP_PCT):
        alerts.append(_alert(
            "saturation_trend", WARNING,
            "Signes de saturation d'audience",
            f"La répétition progresse de {freq_var:+.1f} % pendant que le CTR "
            f"recule de {ctr_var:+.1f} %. Les mêmes personnes sont exposées plus "
            f"souvent et cliquent moins — envisager un renouvellement des créas "
            f"ou un élargissement du ciblage.",
            "boost",
        ))
    return alerts


# ─── Rule 3 — ads pipeline integrity ──────────────────────────────────────────
def check_ads_pipeline(campaigns: list, adset_ad_data: dict | None) -> list:
    """Campaigns with delivery but no ad rows means the fetch failed.

    This exact situation left the Rapport tab empty for days while the banner
    blamed loading, because the underlying API error was swallowed into an
    empty result.
    """
    active = [c for c in (campaigns or [])
              if (c.get("spend", 0) or 0) > 0 or (c.get("impressions", 0) or 0) > 0]
    if not active:
        return []
    ads = (adset_ad_data or {}).get("ads") or []
    if ads:
        return []
    return [_alert(
        "ads_pipeline", CRITICAL,
        "Données publicitaires manquantes",
        f"{len(active)} campagnes ont diffusé sur la période mais aucune "
        f"publicité n'a été récupérée. La récupération a probablement échoué "
        f"(limite de requêtes Meta) — les tableaux Rapport sont incomplets. "
        f"Cliquer sur « 🔄 Refresh Data », puis vérifier les logs.",
        "boost",
    )]


# ─── Rule 4 — GA4 tracking integrity ──────────────────────────────────────────
def check_ga4_tracking(overview: dict | None) -> list:
    """Page views far below sessions means the page_view tag is broken.

    Observed on footland.dz: 12 page views reported against 628 962 sessions.
    Displayed as a KPI without comment, a figure like that quietly misleads.
    """
    ov = overview or {}
    sessions = ov.get("sessions", 0) or 0
    page_views = ov.get("page_views", 0) or 0
    if sessions < GA4_MIN_SESSIONS_TO_CHECK:
        return []
    if page_views >= sessions * GA4_MIN_PAGEVIEWS_PER_SESSION:
        return []
    return [_alert(
        "ga4_tracking", CRITICAL,
        "Suivi des pages vues défaillant",
        f"{page_views:,} pages vues déclarées pour {sessions:,} sessions — "
        f"un visiteur consulte au minimum une page. Le tag « page_view » du "
        f"site est probablement mal configuré : les indicateurs Pages vues et "
        f"Pages / Session ne sont pas exploitables.".replace(",", " "),
        "ga4",
    )]


# ─── Entry point ──────────────────────────────────────────────────────────────
def check_all(*, campaigns: list | None = None, totals: dict | None = None,
              prev_totals: dict | None = None,
              adset_ad_data: dict | None = None,
              ga4_overview: dict | None = None) -> list:
    """Run every rule. Each is independent — one raising must not silence the
    others, since the data-integrity rules matter most when something is
    already going wrong."""
    alerts = []
    for rule, args in (
        (check_cost_per_order, (campaigns,)),
        (check_saturation,     (totals, prev_totals)),
        (check_ads_pipeline,   (campaigns, adset_ad_data)),
        (check_ga4_tracking,   (ga4_overview,)),
    ):
        try:
            alerts.extend(rule(*args))
        except Exception as e:  # noqa: BLE001
            print(f"DEBUG alerts: rule {rule.__name__} failed: {e}")

    # Log-only phase: printed so firing frequency can be counted from the
    # server logs over a few weeks before anyone is notified.
    for a in alerts:
        print(f"ALERT [{a['severity']}] {a['rule']}: {a['title']} — {a['detail'][:120]}")
    return alerts


# ─── Rendering ────────────────────────────────────────────────────────────────
_STYLES = {
    CRITICAL: ("rgba(248,113,113,0.10)", "rgba(248,113,113,0.45)", "#f87171", "🔴"),
    WARNING:  ("rgba(250,204,21,0.10)",  "rgba(250,204,21,0.45)",  "#facc15", "🟡"),
}


def render_alerts(alerts: list, scope: str | None = None):
    """Render alerts for one scope. Renders nothing when there is nothing wrong."""
    shown = [a for a in (alerts or []) if scope is None or a.get("scope") == scope]
    if not shown:
        return

    # Critical first — the ordering is the triage.
    shown.sort(key=lambda a: 0 if a["severity"] == CRITICAL else 1)

    dark = st.session_state.get("theme", "dark") == "dark"
    text_c = "#e4e4e7" if dark else "#1f2937"

    blocks = []
    for a in shown:
        bg, border, accent, icon = _STYLES.get(a["severity"], _STYLES[WARNING])
        blocks.append(
            f'<div style="background:{bg};border-left:3px solid {border};'
            f'border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:0.5rem;">'
            f'<div style="font-size:0.85rem;font-weight:700;color:{accent};'
            f'margin-bottom:0.2rem;">{icon} {a["title"]}</div>'
            f'<div style="font-size:0.8rem;line-height:1.55;color:{text_c};">'
            f'{a["detail"]}</div></div>'
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)
