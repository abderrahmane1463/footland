"""
api/ga4.py — Google Analytics 4 data fetching.
Uses OAuth token from ga4_token.json (local) or Streamlit secrets (cloud).
"""
import os
import json
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange, Dimension, Metric, OrderBy, RunReportRequest,
    FilterExpression, Filter,
)
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

GA4_PROPERTY_ID = "377768319"
_TOKEN_PATH     = "ga4_token.json"
_SCOPES         = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_credentials():
    token_data = None
    secrets_error = None

    try:
        import streamlit as st
        raw = st.secrets["ga4"]["token_json"]
        token_data = json.loads(raw)
    except Exception as e:
        secrets_error = str(e)

    if token_data is None:
        if not os.path.exists(_TOKEN_PATH):
            raise RuntimeError(
                f"No GA4 token: Streamlit secret failed ({secrets_error}), "
                f"and ga4_token.json not found locally."
            )
        with open(_TOKEN_PATH) as f:
            token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes", _SCOPES),
    )
    creds.refresh(Request())
    if os.path.exists(_TOKEN_PATH):
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def _prop():
    return f"properties/{GA4_PROPERTY_ID}"


# ─── Individual fetchers (all accept an already-built client) ──────────────────
def _fetch_overview(client, start: str, end: str) -> dict:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViews"),
            Metric(name="screenPageViewsPerSession"),
        ],
    )
    resp = client.run_report(req)
    if not resp.rows:
        return {}
    row = resp.rows[0].metric_values
    return {
        "active_users":         int(float(row[0].value)),
        "new_users":            int(float(row[1].value)),
        "sessions":             int(float(row[2].value)),
        "engaged_sessions":     int(float(row[3].value)),
        "engagement_rate":      round(float(row[4].value) * 100, 2),
        "bounce_rate":          round(float(row[5].value) * 100, 2),
        "avg_session_duration": round(float(row[6].value), 0),
        "page_views":           int(float(row[7].value)),
        "pages_per_session":    round(float(row[8].value), 2),
    }


def _fetch_traffic_sources(client, start: str, end: str) -> list:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[
            Metric(name="sessions"),
            Metric(name="activeUsers"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
        ],
        order_bys=[OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name="sessions"),
            desc=True,
        )],
        limit=10,
    )
    resp  = client.run_report(req)
    total = sum(int(float(r.metric_values[0].value)) for r in resp.rows) or 1
    result = []
    for row in resp.rows:
        sessions = int(float(row.metric_values[0].value))
        result.append({
            "channel":         row.dimension_values[0].value,
            "sessions":        sessions,
            "users":           int(float(row.metric_values[1].value)),
            "engagement_rate": round(float(row.metric_values[2].value) * 100, 2),
            "bounce_rate":     round(float(row.metric_values[3].value) * 100, 2),
            "pct":             round(sessions / total * 100, 1),
        })
    return result


def _fetch_top_pages(client, start: str, end: str, limit: int = 10) -> list:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="activeUsers"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
        order_bys=[OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
            desc=True,
        )],
        limit=limit,
    )
    resp = client.run_report(req)
    result = []
    for row in resp.rows:
        result.append({
            "path":        row.dimension_values[0].value,
            "title":       row.dimension_values[1].value,
            "views":       int(float(row.metric_values[0].value)),
            "users":       int(float(row.metric_values[1].value)),
            "avg_duration": round(float(row.metric_values[2].value), 0),
            "bounce_rate": round(float(row.metric_values[3].value) * 100, 2),
        })
    return result


def _fetch_geography(client, start: str, end: str) -> dict:
    req_country = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="country")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
        limit=10,
    )
    req_city = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="city")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="activeUsers"), desc=True)],
        limit=15,
    )
    resp_c  = client.run_report(req_country)
    resp_ci = client.run_report(req_city)

    total_c  = sum(int(float(r.metric_values[0].value)) for r in resp_c.rows)  or 1
    total_ci = sum(int(float(r.metric_values[0].value)) for r in resp_ci.rows) or 1

    countries = []
    for row in resp_c.rows:
        users = int(float(row.metric_values[0].value))
        countries.append({
            "name":     row.dimension_values[0].value,
            "users":    users,
            "sessions": int(float(row.metric_values[1].value)),
            "pct":      round(users / total_c * 100, 1),
        })

    cities = []
    for row in resp_ci.rows:
        name = row.dimension_values[0].value
        if name in ("(not set)", ""):
            continue
        users = int(float(row.metric_values[0].value))
        cities.append({
            "name":     name,
            "users":    users,
            "sessions": int(float(row.metric_values[1].value)),
            "pct":      round(users / total_ci * 100, 1),
        })

    return {"countries": countries, "cities": cities}


def _fetch_devices(client, start: str, end: str) -> list:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="deviceCategory")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="sessions"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
        ],
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
    )
    resp  = client.run_report(req)
    total = sum(int(float(r.metric_values[0].value)) for r in resp.rows) or 1
    result = []
    for row in resp.rows:
        users = int(float(row.metric_values[0].value))
        result.append({
            "device":          row.dimension_values[0].value,
            "users":           users,
            "sessions":        int(float(row.metric_values[1].value)),
            "engagement_rate": round(float(row.metric_values[2].value) * 100, 2),
            "bounce_rate":     round(float(row.metric_values[3].value) * 100, 2),
            "pct":             round(users / total * 100, 1),
        })
    return result


def _fetch_events(client, start: str, end: str) -> list:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="eventName")],
        metrics=[
            Metric(name="eventCount"),
            Metric(name="totalUsers"),
            Metric(name="eventCountPerUser"),
            Metric(name="totalRevenue"),
        ],
        order_bys=[OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name="eventCount"),
            desc=True,
        )],
    )
    resp = client.run_report(req)
    total_events = sum(int(float(r.metric_values[0].value)) for r in resp.rows) or 1
    total_users  = sum(int(float(r.metric_values[1].value)) for r in resp.rows) or 1
    result = []
    for row in resp.rows:
        event_count = int(float(row.metric_values[0].value))
        users       = int(float(row.metric_values[1].value))
        result.append({
            "event":             row.dimension_values[0].value,
            "event_count":       event_count,
            "users":             users,
            "events_per_user":   round(float(row.metric_values[2].value), 2),
            "revenue":           round(float(row.metric_values[3].value), 2),
            "pct_events":        round(event_count / total_events * 100, 2),
            "pct_users":         round(users / total_users * 100, 2),
        })
    return result


def _fetch_ecommerce_items(client, start: str, end: str, limit: int = 5000) -> list:
    req = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="itemName")],
        metrics=[
            Metric(name="itemsViewed"),
            Metric(name="itemsAddedToCart"),
            Metric(name="itemsPurchased"),
            Metric(name="itemRevenue"),
        ],
        order_bys=[OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name="itemsViewed"),
            desc=True,
        )],
        limit=limit,
    )
    resp = client.run_report(req)
    result = []
    for row in resp.rows:
        result.append({
            "name":        row.dimension_values[0].value,
            "viewed":      int(float(row.metric_values[0].value)),
            "add_to_cart": int(float(row.metric_values[1].value)),
            "purchased":   int(float(row.metric_values[2].value)),
            "revenue":     round(float(row.metric_values[3].value), 2),
        })
    return result


def _fetch_purchase_journey(client, start: str, end: str) -> dict:
    _EVENTS = ["session_start", "view_item", "add_to_cart", "begin_checkout", "purchase"]
    _event_filter = FilterExpression(
        filter=Filter(
            field_name="eventName",
            in_list_filter=Filter.InListFilter(values=_EVENTS),
        )
    )

    req_total = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="activeUsers")],
        dimension_filter=_event_filter,
    )
    req_device = RunReportRequest(
        property=_prop(),
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name="eventName"), Dimension(name="deviceCategory")],
        metrics=[Metric(name="activeUsers")],
        dimension_filter=_event_filter,
    )

    resp_total  = client.run_report(req_total)
    resp_device = client.run_report(req_device)

    totals = {}
    for row in resp_total.rows:
        totals[row.dimension_values[0].value] = int(float(row.metric_values[0].value))

    by_device = {}
    for row in resp_device.rows:
        event  = row.dimension_values[0].value
        device = row.dimension_values[1].value
        users  = int(float(row.metric_values[0].value))
        by_device.setdefault(device, {})[event] = users

    _STEPS = [
        ("session_start",  "Ouverture de session"),
        ("view_item",      "Affichage du produit"),
        ("add_to_cart",    "Ajout au panier"),
        ("begin_checkout", "Paiement initié"),
        ("purchase",       "Achat finalisé"),
    ]

    funnel = []
    for event_key, label in _STEPS:
        funnel.append({"event": event_key, "label": label, "users": totals.get(event_key, 0)})

    return {"funnel": funnel, "by_device": by_device}


# ─── Main entry point ──────────────────────────────────────────────────────────
def fetch_all_ga4_data(start: str, end: str) -> dict:
    """
    Fetch all GA4 sections in a single credential refresh.
    Partial failures are silently ignored — affected keys return empty data.
    """
    creds  = _get_credentials()
    client = BetaAnalyticsDataClient(credentials=creds)

    result = {
        "overview":         {},
        "traffic_sources":  [],
        "top_pages":        [],
        "geography":        {"countries": [], "cities": []},
        "devices":          [],
        "purchase_journey": {"funnel": [], "by_device": {}},
        "ecommerce_items":  [],
        "events":           [],
    }

    for key, fn in [
        ("overview",         lambda: _fetch_overview(client, start, end)),
        ("traffic_sources",  lambda: _fetch_traffic_sources(client, start, end)),
        ("top_pages",        lambda: _fetch_top_pages(client, start, end)),
        ("geography",        lambda: _fetch_geography(client, start, end)),
        ("devices",          lambda: _fetch_devices(client, start, end)),
        ("purchase_journey", lambda: _fetch_purchase_journey(client, start, end)),
        ("ecommerce_items",  lambda: _fetch_ecommerce_items(client, start, end)),
        ("events",           lambda: _fetch_events(client, start, end)),
    ]:
        try:
            result[key] = fn()
        except Exception as e:
            print(f"GA4 {key} error: {e}")

    return result


def fetch_ga4_overview(start: str, end: str) -> dict:
    """
    Fetch only the overview block for one date range.

    Used to pull the previous period for the AI analysis report without paying
    for the eight other sections of fetch_all_ga4_data(). Returns {} on failure
    so a missing comparison degrades the report rather than breaking the tab.
    """
    try:
        creds  = _get_credentials()
        client = BetaAnalyticsDataClient(credentials=creds)
        return _fetch_overview(client, start, end)
    except Exception as e:
        print(f"GA4 overview ({start}->{end}) error: {e}")
        return {}
