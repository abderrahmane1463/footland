"""
api/boost.py — Meta Marketing API fetch functions (paid campaigns).

The _assert_not_blocked() guard from api/base.py is intentionally NOT used
here. The ad account in BLOCKED_AD_ACCOUNTS is "blocked" only for organic
endpoints (fetch_fb_*, fetch_ig_*) to enforce the organic-only constraint.
This module is the single authorised place to query it.

Required token permissions: ads_read (the long-lived page token in config.py
must have been generated with this scope, or a User token with ads_read must
replace it for this endpoint).
"""

import json
import time
import requests
from datetime import datetime, timezone

from config import (
    ADS_ACCESS_TOKEN,
    FACEBOOK_PAGE_ID,
    FOOTLAND_CAMPAIGN_KEYWORDS,
    GRAPH_BASE_URL,
    BLOCKED_AD_ACCOUNTS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from api.base import _date_range

# The page's ad account — intentionally queried here (Boost tab only)
AD_ACCOUNT_ID = BLOCKED_AD_ACCOUNTS[0]   # "act_765947885726761"

# Meta action types that represent a purchase / conversion.
# Use only "purchase" (the unified de-duplicated count Meta exposes).
# "offsite_conversion.fb_pixel_purchase" is the same event and would double-count.
_PURCHASE_TYPES        = {"purchase"}
_ADD_TO_CART_TYPES     = {"offsite_conversion.fb_pixel_add_to_cart"}
_CHECKOUT_TYPES        = {"offsite_conversion.fb_pixel_initiate_checkout"}
_LANDING_PAGE_TYPES    = {"landing_page_view"}
_POST_ENGAGEMENT_TYPES = {"post_engagement"}
_PAGE_ENGAGEMENT_TYPES = {"page_engagement"}
_POST_REACTION_TYPES   = {"post_reaction"}
_POST_COMMENT_TYPES    = {"comment"}
_POST_SHARE_TYPES      = {"post"}
_POST_SAVE_TYPES       = {"onsite_conversion.post_save"}
_PAGE_LIKE_TYPES       = {"like"}
_PHOTO_VIEW_TYPES      = {"photo_view"}
_LEAD_TYPES            = {"lead", "offsite_conversion.fb_pixel_lead"}
_APP_INSTALL_TYPES     = {"mobile_app_install", "app_install"}
# Campaign objectives that count as "conversion" campaigns
_CONV_OBJECTIVES = {"CONVERSIONS", "OUTCOME_SALES"}

# Meta ad-set optimization_goal → ("Result type" label, key into the result-source dict).
# This mirrors how Ads Manager picks the Results column: it follows the
# optimization goal, NOT just the campaign objective. e.g. an OUTCOME_AWARENESS
# campaign optimized for video views reports "2-Second Continuous Video View",
# while one optimized for reach reports "Reach".
_OPTIM_RESULT_MAP = {
    "REACH":                             ("Reach",                          "reach"),
    "IMPRESSIONS":                       ("Impressions",                    "impressions"),
    "TWO_SECOND_CONTINUOUS_VIDEO_VIEWS": ("2-Second Continuous Video View", "video_2s"),
    "THRUPLAY":                          ("ThruPlays",                      "thruplays"),
    "POST_ENGAGEMENT":                   ("Post engagements",               "post_engagement"),
    "PAGE_LIKES":                        ("Page likes",                     "page_likes"),
    "LINK_CLICKS":                       ("Link clicks",                    "link_clicks"),
    "LANDING_PAGE_VIEWS":                ("Landing page views",             "landing_page_views"),
    "OFFSITE_CONVERSIONS":               ("Website purchases",              "purchases"),
    "LEAD_GENERATION":                   ("Leads",                          "leads"),
    "QUALITY_LEAD":                      ("Leads",                          "leads"),
    "APP_INSTALLS":                      ("App installs",                   "app_installs"),
}

# Fallback result type by objective when no optimization_goal is available.
_OBJECTIVE_RESULT_MAP = {
    "OUTCOME_AWARENESS":     ("Reach",             "reach"),
    "OUTCOME_ENGAGEMENT":    ("Post engagements",  "post_engagement"),
    "OUTCOME_SALES":         ("Website purchases", "purchases"),
    "CONVERSIONS":           ("Website purchases", "purchases"),
    "OUTCOME_TRAFFIC":       ("Link clicks",       "link_clicks"),
    "OUTCOME_LEADS":         ("Leads",             "leads"),
    "OUTCOME_APP_PROMOTION": ("App installs",      "app_installs"),
}


def _derive_delivery_status(effective_status: str, stop_time: str) -> str:
    """Map Meta effective_status (+ schedule) to the lowercase delivery label
    Ads Manager shows: active / recently_completed / completed / paused / …"""
    es = (effective_status or "").upper()
    if es == "ACTIVE" and stop_time:
        try:
            stop_dt = datetime.fromisoformat(stop_time.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if stop_dt < now:
                days = (now - stop_dt).days
                return "recently_completed" if days <= 10 else "completed"
        except Exception:
            pass
    return {
        "ACTIVE":          "active",
        "PAUSED":          "paused",
        "CAMPAIGN_PAUSED": "paused",
        "ADSET_PAUSED":    "paused",
        "ARCHIVED":        "archived",
        "DELETED":         "deleted",
        "IN_PROCESS":      "in_process",
        "WITH_ISSUES":     "with_issues",
        "DISAPPROVED":     "with_issues",
    }.get(es, es.lower() or "—")


# Meta's app-level throttle. Backoff is deliberately steeper than the generic
# one: once the app limit is hit, retrying quickly just deepens the hole.
RATE_LIMIT_BACKOFF = 4.0
_RATE_LIMIT_CODES = {4, 17, 32, 613}  # app / user / page request limits


def _is_rate_limited(resp) -> bool:
    """True when Meta is throttling us.

    Meta returns its rate limits as HTTP 403 with an error code (4 =
    "Application request limit reached"), not as 429, so status alone is not
    enough to tell throttling apart from a genuine permission error.
    """
    if resp.status_code not in (400, 403, 429):
        return False
    try:
        err = resp.json().get("error", {})
    except Exception:  # noqa: BLE001 - non-JSON error body
        return False
    return err.get("code") in _RATE_LIMIT_CODES or bool(err.get("is_transient"))


# ─── Internal HTTP layer (no block-guard) ─────────────────────────────────────
def _get_ads(endpoint: str, params: dict) -> dict:
    """
    GET against the Meta Marketing API with retry + backoff.
    Bypasses _assert_not_blocked() — this is intentional (see module docstring).
    """
    url = f"{GRAPH_BASE_URL}/{endpoint.lstrip('/')}"
    full_params = {**params, "access_token": ADS_ACCESS_TOKEN}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=full_params, timeout=REQUEST_TIMEOUT)
            if resp.status_code not in (200, 400):
                print(f"DEBUG ads: HTTP {resp.status_code} on {endpoint}: {resp.text[:200]}")

            # Meta signals its app-level rate limit as 403 with code 4
            # ("Application request limit reached", is_transient), not 429.
            # Without this it was treated as a hard failure and never retried.
            if resp.status_code == 429 or _is_rate_limited(resp):
                if attempt < MAX_RETRIES:
                    time.sleep(RATE_LIMIT_BACKOFF ** attempt)
                    continue

            # 4xx other than rate limiting is deterministic — a malformed or
            # over-long request fails identically on every attempt, so retrying
            # only wastes round-trips (and burns more rate-limit budget).
            if 400 <= resp.status_code < 500 and not _is_rate_limited(resp):
                resp.raise_for_status()

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError:
            raise
        except requests.exceptions.RequestException as exc:
            print(f"DEBUG ads: request failed (attempt {attempt}): {exc}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF ** attempt)

    return {}


def _get_ads_all_pages(endpoint: str, params: dict, max_pages: int = 40) -> list:
    """
    GET against the Meta Marketing API, following `paging.next` until
    exhausted (or max_pages reached). Returns the concatenated `data` list.

    Without this, any edge with more rows than the requested `limit` would
    silently drop everything past the first page — e.g. older campaigns in
    a shared agency ad account that has accumulated more than 500 campaigns
    across all of its clients.
    """
    resp = _get_ads(endpoint, params)
    all_data: list = list(resp.get("data", []))
    next_url = resp.get("paging", {}).get("next")
    pages = 1

    while next_url and pages < max_pages:
        pages += 1
        page_json: dict = {}
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = requests.get(next_url, timeout=REQUEST_TIMEOUT)
                if r.status_code == 429:
                    time.sleep(RETRY_BACKOFF ** attempt)
                    continue
                r.raise_for_status()
                page_json = r.json()
                break
            except requests.exceptions.RequestException as exc:
                print(f"DEBUG ads: pagination request failed (attempt {attempt}): {exc}")
                if attempt == MAX_RETRIES:
                    page_json = {}
                else:
                    time.sleep(RETRY_BACKOFF ** attempt)

        all_data.extend(page_json.get("data", []))
        next_url = page_json.get("paging", {}).get("next")

    return all_data


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _purchases(actions: list) -> int:
    return sum(
        int(float(a.get("value", 0)))
        for a in (actions or [])
        if a.get("action_type") in _PURCHASE_TYPES
    )


def _action_count(actions: list, types: set) -> int:
    return sum(
        int(float(a.get("value", 0)))
        for a in (actions or [])
        if a.get("action_type") in types
    )


def _outbound_clicks_count(field_val) -> int:
    """outbound_clicks comes as [{"action_type": "outbound_click", "value": "N"}]."""
    if not field_val:
        return 0
    return sum(int(float(v.get("value", 0))) for v in field_val)


def _cpa(cost_per_action: list) -> float:
    for item in (cost_per_action or []):
        if item.get("action_type") in _PURCHASE_TYPES:
            return float(item.get("value", 0.0))
    return 0.0


def _cost_for_type(cost_per_action: list, types: set) -> float:
    for item in (cost_per_action or []):
        if item.get("action_type") in types:
            return float(item.get("value", 0.0))
    return 0.0


def _purchase_value(action_values: list) -> float:
    """Sum of purchase revenue from action_values (Meta Pixel purchase event value)."""
    return sum(
        float(a.get("value", 0))
        for a in (action_values or [])
        if a.get("action_type") in _PURCHASE_TYPES
    )


def _video_action_val(field) -> int:
    """Sum values from a Meta video action list field (e.g. video_play_actions)."""
    if not field or not isinstance(field, list):
        return 0
    return sum(int(float(v.get("value", 0))) for v in field)


def _video_avg_time(field) -> float:
    """Average video play time in seconds from video_avg_time_watched_actions."""
    if not field or not isinstance(field, list):
        return 0.0
    return round(sum(float(v.get("value", 0)) for v in field), 2)


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


# ─── Shared helpers ───────────────────────────────────────────────────────────
# The campaign list is the same for every fetch on a page load, but each caller
# used to re-request it — 16 times in one observed session. Since pagination was
# added, each of those walks all ~2 100 campaigns (~5 requests), so the list
# alone cost ~80 calls per load and was the main reason Meta started returning
# "Application request limit reached". It changes slowly, so cache it.
_IDS_CACHE_TTL = 900  # seconds
_ids_cache: dict[str, tuple[float, list]] = {}


def _get_footland_ids(force: bool = False) -> list:
    """All Footland campaign IDs in the ad account, cached for _IDS_CACHE_TTL."""
    cached = _ids_cache.get("ids")
    if cached and not force and (time.time() - cached[0]) < _IDS_CACHE_TTL:
        return cached[1]

    try:
        all_camps = _get_ads_all_pages(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,name",
            "limit":  500,
        })
        ids = [c["id"] for c in all_camps if any(kw in c.get("name", "") for kw in FOOTLAND_CAMPAIGN_KEYWORDS)]
        print(f"DEBUG boost: {len(ids)} Footland campaign IDs found (out of {len(all_camps)} total in account)")
        if ids:
            _ids_cache["ids"] = (time.time(), ids)
        return ids
    except Exception as e:
        print(f"DEBUG boost: _get_footland_ids error: {e}")
        # Serve a stale list rather than nothing — an empty list makes every
        # downstream call return no data at all.
        return cached[1] if cached else []


def _is_footland(name: str) -> bool:
    return any(kw in (name or "") for kw in FOOTLAND_CAMPAIGN_KEYWORDS)


def _active_footland_ids(time_range: str) -> list:
    """Footland campaign IDs that actually ran during the period.

    A single UNFILTERED campaign-level insights call returns only campaigns
    with delivery in the window — account-wide, but that is a few hundred rows,
    one page — and the Footland ones are picked out by name in Python.

    This exists because filtering by the ~1 100 lifetime campaign IDs meant
    either a 32 KB URL (rejected outright) or eight batched requests per call
    site, which tripped Meta's app-level request limit. Asking about the ~60
    campaigns that actually ran costs one request and one batch downstream.

    Memoised per period — several call sites need the same list.
    """
    cache_key = f"active_ids::{time_range}"
    cached = _ids_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _IDS_CACHE_TTL:
        return cached[1]

    try:
        rows = _get_ads_all_pages(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "campaign",
            "fields":     "campaign_id,campaign_name",
            "time_range": time_range,
            "limit":      500,
        })
        ids = [r.get("campaign_id") for r in rows
               if r.get("campaign_id") and _is_footland(r.get("campaign_name"))]
        print(f"DEBUG boost: {len(ids)} Footland campaigns active in period "
              f"(of {len(rows)} account-wide)")
        if ids:
            _ids_cache[cache_key] = (time.time(), ids)
        return ids
    except Exception as e:
        print(f"DEBUG boost: _active_footland_ids error: {e}")
        return []


# Meta rejects very long URLs (the 1 133-ID filter produced a 32 KB URL and a
# flat 400), so ID filters are sent in batches and the rows concatenated.
_FILTER_CHUNK = 150


def _cached_account_fetch(cache_key: str, endpoint: str, params: dict) -> list:
    """Paginated fetch of account-wide metadata, memoised for _IDS_CACHE_TTL.

    These calls carry no time_range, so they return the same rows for the
    current period and the previous-period comparison — fetching them twice per
    page load was pure waste against Meta's request budget.
    """
    cached = _ids_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < _IDS_CACHE_TTL:
        return cached[1]
    rows = _get_ads_all_pages(endpoint, params)
    if rows:
        _ids_cache[cache_key] = (time.time(), rows)
    return rows


def _get_ads_filtered(endpoint: str, params: dict, field: str, ids: list) -> list:
    """Paginated GET filtered by a list of IDs, sent in URL-safe batches."""
    if not ids:
        return []
    rows: list = []
    for i in range(0, len(ids), _FILTER_CHUNK):
        batch = ids[i:i + _FILTER_CHUNK]
        rows.extend(_get_ads_all_pages(endpoint, {
            **params,
            "filtering": json.dumps([{"field": field, "operator": "IN", "value": batch}]),
        }))
    return rows


# ─── Public fetch function ────────────────────────────────────────────────────
def fetch_boost_insights(
    days: int = 30,
    start: str = None,
    end: str = None,
) -> dict:
    """
    Fetch paid campaign performance from the Meta Marketing API.

    Returns a dict with the same shape as views/boost.py:empty_boost_data()
    so the UI can be called identically whether data is real or placeholder.

    Parameters
    ----------
    days  : fallback window if start/end are not provided
    start : ISO date string "YYYY-MM-DD"
    end   : ISO date string "YYYY-MM-DD"
    """
    since, until = _date_range(days, start, end)
    time_range   = f'{{"since":"{since}","until":"{until}"}}'

    # Fields requested from every campaign row
    # clicks              = ALL clicks on the ad (reactions, comments, profile, link, etc.)
    # inline_link_clicks  = clicks that go to the destination URL only (used for conversions)
    _FIELDS = (
        "campaign_id,campaign_name,objective,"
        "impressions,reach,clicks,inline_link_clicks,"
        "spend,cpc,ctr,frequency,"
        "outbound_clicks,"
        "video_continuous_2_sec_watched_actions,video_thruplay_watched_actions,"
        "quality_ranking,engagement_rate_ranking,conversion_rate_ranking,"
        "actions,cost_per_action_type,action_values"
    )

    # ── Initialise output with zero defaults ──────────────────────────────────
    out = {
        "totals": {
            "campaigns_count": 0,
            "link_clicks":     0,
            "reach":           0,
            "impressions":     0,
            "cpc":             0.0,
            "ctr":             0.0,
            "spend":           0.0,
            "frequency":       0.0,
        },
        "conversions": {
            "campaigns_count":     0,
            "link_clicks":         0,
            "reach":               0,
            "impressions":         0,
            "cpc":                 0.0,
            "ctr":                 0.0,
            "spend":               0.0,
            "frequency":           0.0,
            "cost_per_conversion": 0.0,
            "total_conversions":   0,
        },
        "campaigns": [],
        "period": {"since": since, "until": until},
    }

    # ── 1. Resolve Footland campaign IDs + status/budget ─────────────────────
    footland_ids = _get_footland_ids()

    # Fetch delivery status and budget per campaign
    _camp_meta: dict[str, dict] = {}
    try:
        camps_meta_data = _cached_account_fetch(
            "camp_meta", f"{AD_ACCOUNT_ID}/campaigns",
            {"fields": "id,effective_status,daily_budget,lifetime_budget,stop_time",
             "limit": 500},
        )
        for c in camps_meta_data:
            cid = c.get("id", "")
            daily    = _safe_float(c.get("daily_budget",    0)) / 100
            lifetime = _safe_float(c.get("lifetime_budget", 0)) / 100
            stop     = c.get("stop_time", "")
            if daily > 0:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": daily, "budget_type": "Daily", "stop_time": stop}
            elif lifetime > 0:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": lifetime, "budget_type": "Lifetime", "stop_time": stop}
            else:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": 0.0, "budget_type": "—", "stop_time": stop}
    except Exception as e:
        print(f"DEBUG boost: campaign meta fetch error: {e}")

    # Fetch each campaign's optimization goal (from its ad sets). Ads Manager
    # derives the Results column from this, not from the campaign objective.
    _camp_optim: dict[str, str] = {}
    try:
        # Unfiltered this walks every adset in a 2 100-campaign account — the
        # single largest source of requests here. Restricted to the campaigns
        # that ran in the period, it is one batch.
        adsets_optim_data = _get_ads_filtered(
            f"{AD_ACCOUNT_ID}/adsets",
            {"fields": "campaign_id,optimization_goal", "limit": 500},
            "campaign.id", _active_footland_ids(time_range),
        )
        for a in adsets_optim_data:
            cid = a.get("campaign_id", "")
            goal = a.get("optimization_goal", "")
            if cid and goal and cid not in _camp_optim:
                _camp_optim[cid] = goal
    except Exception as e:
        print(f"DEBUG boost: adset optimization_goal fetch error: {e}")

    if not footland_ids:
        return out

    # NOTE: account-level deduplicated reach is fetched further down, once the
    # campaign rows reveal which campaigns were actually active in the period.
    # Asking for it up front meant filtering on all ~1 100 lifetime campaign IDs,
    # which produced a 32 KB URL that Meta rejected outright. It also cannot be
    # split into batches: separate dedup figures cannot be summed without
    # double-counting people reached by campaigns in different batches.

    # ── 2. Campaign-level insights (Footland only) ────────────────────────────
    try:
        # Fetched UNFILTERED and narrowed by name in Python. Meta only returns
        # campaigns with delivery in the window, so this is one page rather than
        # eight batched requests filtered on every lifetime campaign ID — and
        # request volume is what was tripping the app-level rate limit.
        _all_rows = _get_ads_all_pages(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "campaign",
            "fields":     _FIELDS,
            "time_range": time_range,
            "limit":      500,
        })
        rows = [r for r in _all_rows if _is_footland(r.get("campaign_name"))]
        print(f"DEBUG boost: {len(rows)} Footland campaign rows "
              f"(of {len(_all_rows)} account-wide) for {since}→{until}")

        campaigns    = []
        conv_ids:    list[str]        = []   # campaign IDs with conversion objective
        obj_camp_ids: dict[str, list] = {}   # objective → [campaign_ids] for dedup reach
        # Accumulators — reach excluded (comes from dedup account-level call)
        t_clicks = t_imp = 0
        t_spend  = 0.0
        t_purchase_value = 0.0
        t_lp = t_cart = t_chk = t_purchases = 0
        t_cpcs:  list[float] = []
        t_ctrs:  list[float] = []
        t_freqs: list[float] = []
        # Conversion-objective accumulators
        cv_clicks = cv_imp = cv_purchases = 0
        cv_spend  = 0.0
        cv_purchase_value = 0.0
        cv_cpcs:  list[float] = []
        cv_ctrs:  list[float] = []
        cv_freqs: list[float] = []

        for r in rows:
            objective  = r.get("objective", "")
            actions    = r.get("actions") or []
            cpa_list   = r.get("cost_per_action_type") or []
            purchases  = _purchases(actions)
            cpa_val    = _cpa(cpa_list)
            spend_val  = _safe_float(r.get("spend"))
            cpc_val    = _safe_float(r.get("cpc"))
            ctr_val    = _safe_float(r.get("ctr"))
            freq_val   = _safe_float(r.get("frequency"))
            clicks_val      = _safe_int(r.get("clicks"))
            link_clicks_val = _safe_int(r.get("inline_link_clicks"))
            reach_val  = _safe_int(r.get("reach"))
            imp_val    = _safe_int(r.get("impressions"))
            camp_id    = r.get("campaign_id", "")

            # New fields from expanded API call
            action_values_list = r.get("action_values") or []
            purch_value_val = _purchase_value(action_values_list)
            roas_val        = round(purch_value_val / spend_val, 2) if spend_val else 0.0
            outbound_val    = _outbound_clicks_count(r.get("outbound_clicks"))
            lp_views_val    = _action_count(actions, _LANDING_PAGE_TYPES)
            add_cart_val    = _action_count(actions, _ADD_TO_CART_TYPES)
            checkout_val    = _action_count(actions, _CHECKOUT_TYPES)
            post_eng_val    = _action_count(actions, _POST_ENGAGEMENT_TYPES)
            video_2s_val    = _video_action_val(r.get("video_continuous_2_sec_watched_actions"))
            thruplay_val    = _video_action_val(r.get("video_thruplay_watched_actions"))
            leads_val       = _action_count(actions, _LEAD_TYPES)
            app_installs_val = _action_count(actions, _APP_INSTALL_TYPES)
            page_likes_val  = _action_count(actions, _PAGE_LIKE_TYPES)
            cost_lp_val     = _cost_for_type(cpa_list, _LANDING_PAGE_TYPES)
            cost_cart_val   = _cost_for_type(cpa_list, _ADD_TO_CART_TYPES)
            cost_chk_val    = _cost_for_type(cpa_list, _CHECKOUT_TYPES)
            cost_post_eng_val = _cost_for_type(cpa_list, _POST_ENGAGEMENT_TYPES)
            cpm_val         = round(spend_val / imp_val * 1000, 4) if imp_val else 0.0
            cpc_link_val    = round(spend_val / link_clicks_val, 4) if link_clicks_val else 0.0
            ctr_link_val    = round(link_clicks_val / imp_val * 100, 4) if imp_val else 0.0
            cost_out_val    = round(spend_val / outbound_val, 4) if outbound_val else 0.0

            meta = _camp_meta.get(camp_id, {})

            # Result type & Results — follow the ad-set optimization goal
            # (Ads Manager behaviour), falling back to the campaign objective.
            _result_sources = {
                "reach":              reach_val,
                "impressions":        imp_val,
                "video_2s":           video_2s_val,
                "thruplays":          thruplay_val,
                "post_engagement":    post_eng_val,
                "page_likes":         page_likes_val,
                "link_clicks":        link_clicks_val,
                "landing_page_views": lp_views_val,
                "purchases":          purchases,
                "leads":              leads_val,
                "app_installs":       app_installs_val,
            }
            _goal = _camp_optim.get(camp_id, "")
            _rt_map = _OPTIM_RESULT_MAP.get(_goal) or _OBJECTIVE_RESULT_MAP.get(objective)
            if _rt_map:
                result_type_val, _src_key = _rt_map
                results_val = _result_sources.get(_src_key, 0)
            else:
                result_type_val, results_val = "—", 0
            cost_per_result_val = round(spend_val / results_val, 4) if results_val else 0.0

            delivery_val = _derive_delivery_status(meta.get("status", ""), meta.get("stop_time", ""))

            campaigns.append({
                "campaign_id":            camp_id,
                "name":                   r.get("campaign_name", "—"),
                "objective":              objective,
                "optimization_goal":      _goal,
                "delivery_status":        delivery_val,
                "budget":                 meta.get("budget", 0.0),
                "budget_type":            meta.get("budget_type", "—"),
                "spend":                  spend_val,
                "conversions":            purchases,
                "result_type":            result_type_val,
                "results":                results_val,
                "cost_per_result":        cost_per_result_val,
                "video_2s_views":         video_2s_val,
                "thruplays":              thruplay_val,
                "leads":                  leads_val,
                "app_installs":           app_installs_val,
                "post_engagement":        post_eng_val,
                "cost_per_post_engagement": cost_post_eng_val,
                "cpa":                    cpa_val if cpa_val else (spend_val / purchases if purchases else 0.0),
                "clicks":                 clicks_val,
                "link_clicks":            link_clicks_val,
                "cpc_link":               cpc_link_val,
                "ctr_link":               ctr_link_val,
                "reach":                  reach_val,
                "impressions":            imp_val,
                "cpc":                    cpc_val,
                "ctr":                    ctr_val,
                "frequency":              freq_val,
                "cpm":                    cpm_val,
                "outbound_clicks":        outbound_val,
                "cost_per_outbound":      cost_out_val,
                "landing_page_views":     lp_views_val,
                "cost_per_lp_view":       cost_lp_val,
                "adds_to_cart":           add_cart_val,
                "cost_per_add_to_cart":   cost_cart_val,
                "checkouts":              checkout_val,
                "cost_per_checkout":      cost_chk_val,
                "purchase_value":          purch_value_val,
                "roas":                   roas_val,
                "quality_ranking":        r.get("quality_ranking", "—"),
                "engagement_ranking":     r.get("engagement_rate_ranking", "—"),
                "conversion_ranking":     r.get("conversion_rate_ranking", "—"),
            })

            if camp_id:
                obj_camp_ids.setdefault(objective, []).append(camp_id)

            t_clicks         += link_clicks_val
            t_imp            += imp_val
            t_spend          += spend_val
            t_purchase_value += purch_value_val
            t_lp             += lp_views_val
            t_cart           += add_cart_val
            t_chk            += checkout_val
            t_purchases      += purchases
            if cpc_val:  t_cpcs.append(cpc_val)
            if ctr_val:  t_ctrs.append(ctr_val)
            if freq_val: t_freqs.append(freq_val)

            if objective in _CONV_OBJECTIVES:
                cv_clicks         += link_clicks_val
                cv_imp            += imp_val
                cv_spend          += spend_val
                cv_purchases      += purchases
                cv_purchase_value += purch_value_val
                if camp_id:  conv_ids.append(camp_id)
                if cpc_val:  cv_cpcs.append(cpc_val)
                if ctr_val:  cv_ctrs.append(ctr_val)
                if freq_val: cv_freqs.append(freq_val)

        # ── Account-level deduplicated reach (Footland, active campaigns) ─────
        # Filtered on the campaigns that actually returned data for this period
        # (tens of IDs) rather than every campaign ever created (~1 100), which
        # is what made this URL too long for Meta to accept.
        _active_ids = [cid for ids in obj_camp_ids.values() for cid in ids]
        if _active_ids:
            try:
                resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
                    "level":      "account",
                    "fields":     "reach",
                    "filtering":  json.dumps([{
                        "field": "campaign.id", "operator": "IN", "value": _active_ids
                    }]),
                    "time_range": time_range,
                })
                rows_acc = resp.get("data", [])
                if rows_acc:
                    out["totals"]["reach"] = _safe_int(rows_acc[0].get("reach"))
            except Exception as e:
                print(f"DEBUG boost: account-level reach error: {e}")

        # Deduplicated reach for conversion campaigns only
        cv_reach = 0
        if conv_ids:
            try:
                resp_cv = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
                    "level":      "account",
                    "fields":     "reach",
                    "filtering":  json.dumps([{
                        "field": "campaign.id", "operator": "IN", "value": conv_ids
                    }]),
                    "time_range": time_range,
                })
                rows_cv = resp_cv.get("data", [])
                if rows_cv:
                    cv_reach = _safe_int(rows_cv[0].get("reach"))
            except Exception as e:
                print(f"DEBUG boost: conv dedup reach error: {e}")

        # Deduplicated reach per objective (for PAR OBJECTIF section)
        objective_reach: dict[str, int] = {}
        for obj, ids in obj_camp_ids.items():
            if not ids:
                continue
            try:
                resp_obj = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
                    "level":      "account",
                    "fields":     "reach",
                    "filtering":  json.dumps([{
                        "field": "campaign.id", "operator": "IN", "value": ids
                    }]),
                    "time_range": time_range,
                })
                rows_obj = resp_obj.get("data", [])
                if rows_obj:
                    objective_reach[obj] = _safe_int(rows_obj[0].get("reach"))
            except Exception as e:
                print(f"DEBUG boost: obj reach error ({obj}): {e}")
        out["objective_reach"] = objective_reach

        out["campaigns"] = campaigns
        active_count = sum(1 for c in campaigns if c["spend"] > 0 or c["impressions"] > 0)

        # Frequency = total_impressions / deduplicated_reach
        # Per-campaign frequency values must NOT be averaged (that ignores campaign size).
        # The account-level deduplicated reach was already fetched above.
        dedup_reach = out["totals"].get("reach", 0)
        total_freq  = round(t_imp / dedup_reach, 2) if dedup_reach else 0.0
        cv_freq     = round(cv_imp / cv_reach,   2) if cv_reach    else 0.0

        # CPC: weighted by clicks (not a simple average)
        # CTR: weighted by impressions
        total_cpc = round(t_spend  / t_clicks,  2) if t_clicks else 0.0
        total_ctr = round(t_clicks / t_imp * 100, 2) if t_imp  else 0.0
        cv_cpc    = round(cv_spend  / cv_clicks,  2) if cv_clicks else 0.0
        cv_ctr    = round(cv_clicks / cv_imp * 100, 2) if cv_imp  else 0.0

        total_roas = round(t_purchase_value / t_spend, 2) if t_spend else 0.0
        cv_roas    = round(cv_purchase_value / cv_spend, 2) if cv_spend else 0.0

        out["totals"].update({
            "campaigns_count":  active_count,
            "link_clicks":      t_clicks,
            # reach already set by account-level dedup call above — preserved
            "impressions":      t_imp,
            "spend":            t_spend,
            "cpc":              total_cpc,
            "ctr":              total_ctr,
            "frequency":        total_freq,
            "purchase_value":   t_purchase_value,
            "roas":             total_roas,
            "landing_page_views": t_lp,
            "adds_to_cart":     t_cart,
            "checkouts":        t_chk,
            "purchases":        t_purchases,
        })

        cv_count = sum(1 for c in campaigns if c["objective"] in _CONV_OBJECTIVES)
        out["conversions"].update({
            "campaigns_count":     cv_count,
            "link_clicks":         cv_clicks,
            "reach":               cv_reach,   # deduplicated
            "impressions":         cv_imp,
            "spend":               cv_spend,
            "cpc":                 cv_cpc,
            "ctr":                 cv_ctr,
            "frequency":           cv_freq,
            "total_conversions":   cv_purchases,
            "cost_per_conversion": cv_spend / cv_purchases if cv_purchases else 0.0,
            "purchase_value":      cv_purchase_value,
            "roas":                cv_roas,
        })

    except Exception as e:
        print(f"DEBUG boost: campaign insights error: {e}")

    return out


def fetch_adset_ad_insights(
    days: int = 30,
    start: str = None,
    end: str = None,
) -> dict:
    """
    Fetch adset-level and ad-level insights for all Footland campaigns.
    Returns {"adsets": [...], "ads": [...], "period": {"since": ..., "until": ...}}
    Ad rows mirror the columns of the Meta Ads Manager CSV export.
    """
    since, until = _date_range(days, start, end)
    time_range   = f'{{"since":"{since}","until":"{until}"}}'

    footland_ids = _get_footland_ids()
    if not footland_ids:
        return {"adsets": [], "ads": [], "period": {"since": since, "until": until}}

    # Only campaigns that ran in this period can have adsets or ads to report,
    # so the heavy calls below filter on those (~60 IDs) instead of every
    # campaign ever created (~1 100). Falls back to the full list if the probe
    # fails, since batching keeps that correct even though it is slower.
    period_ids = _active_footland_ids(time_range) or footland_ids

    # Filters are built per batch inside _get_ads_filtered(). Both the
    # insights and /adsets edges want "campaign.id" (dot notation): the
    # /adsets edge accepts "campaign_id" without error but silently returns
    # zero rows, which is why adset budgets were always blank.
    footland_set = set(footland_ids)

    # ── 1. Campaign metadata (objective, status, budget) ──────────────────────
    # Fetch ALL campaigns (no filter — id-based filter not supported here),
    # then keep only Footland ones.
    _camp_meta: dict[str, dict] = {}
    try:
        all_camps_meta = _get_ads_all_pages(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,objective,effective_status,daily_budget,lifetime_budget,created_time,start_time,stop_time",
            "limit":  500,
        })
        for c in all_camps_meta:
            cid = c.get("id", "")
            if cid not in footland_set:
                continue
            # Meta returns budgets in cents (smallest currency unit) → divide by 100 for euros
            daily = _safe_float(c.get("daily_budget",    0)) / 100
            life  = _safe_float(c.get("lifetime_budget", 0)) / 100
            _camp_meta[cid] = {
                "objective":    c.get("objective", "—"),
                "status":       c.get("effective_status", "—"),
                "budget":       daily if daily > 0 else life,
                "budget_type":  "Daily" if daily > 0 else ("Lifetime" if life > 0 else "—"),
                "created_time": c.get("created_time", ""),
                "start_time":   c.get("start_time", ""),
                "stop_time":    c.get("stop_time", ""),
            }
        print(f"DEBUG adset_ad: campaign meta loaded for {len(_camp_meta)} campaigns")
    except Exception as e:
        print(f"DEBUG adset_ad: campaign meta error: {e}")

    # ── 2. Adset metadata (budget) ────────────────────────────────────────────
    _adset_meta: dict[str, dict] = {}
    try:
        all_adsets_meta = _get_ads_filtered(
            f"{AD_ACCOUNT_ID}/adsets",
            {"fields": "id,campaign_id,daily_budget,lifetime_budget,start_time,end_time",
             "limit": 500},
            "campaign.id", period_ids,
        )
        for a in all_adsets_meta:
            aid   = a.get("id", "")
            daily = _safe_float(a.get("daily_budget",    0)) / 100
            life  = _safe_float(a.get("lifetime_budget", 0)) / 100
            if daily > 0:
                _adset_meta[aid] = {"budget": daily, "budget_type": "Daily"}
            elif life > 0:
                _adset_meta[aid] = {"budget": life, "budget_type": "Lifetime"}
            else:
                _adset_meta[aid] = {"budget": 0.0, "budget_type": "Using campaign budget"}
            _adset_meta[aid]["end_time"]   = a.get("end_time", "")
            _adset_meta[aid]["start_time"] = a.get("start_time", "")
        print(f"DEBUG adset_ad: adset meta loaded for {len(_adset_meta)} adsets")
    except Exception as e:
        print(f"DEBUG adset_ad: adset meta error: {e}")

    # ── 3. Ad delivery status — derived from campaign status + impressions ────
    # Meta's /ads endpoint requires special permissions; instead we derive
    # status from the campaign effective_status we already have.
    _STATUS_MAP = {
        "ACTIVE":        "active",
        "PAUSED":        "inactive",
        "CAMPAIGN_PAUSED": "inactive",
        "ADSET_PAUSED":  "inactive",
        "DELETED":       "deleted",
        "ARCHIVED":      "archived",
        "IN_PROCESS":    "in_process",
        "WITH_ISSUES":   "with_issues",
    }

    # ── Insight field strings ─────────────────────────────────────────────────
    _ADSET_FIELDS = (
        "campaign_id,campaign_name,adset_id,adset_name,"
        "impressions,reach,clicks,inline_link_clicks,"
        "spend,cpc,ctr,frequency,"
        "actions,cost_per_action_type"
    )
    _AD_FIELDS = (
        "campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,"
        "impressions,reach,clicks,inline_link_clicks,"
        "spend,cpc,ctr,frequency,"
        "outbound_clicks,"
        "video_play_actions,video_p25_watched_actions,video_p50_watched_actions,"
        "video_p75_watched_actions,video_p100_watched_actions,"
        "video_avg_time_watched_actions,video_thruplay_watched_actions,"
        "quality_ranking,engagement_rate_ranking,conversion_rate_ranking,"
        "actions,cost_per_action_type,action_values"
    )

    def _parse_adset_row(r):
        return {
            "campaign_id":   r.get("campaign_id", ""),
            "campaign_name": r.get("campaign_name", "—"),
            "adset_id":      r.get("adset_id", ""),
            "adset_name":    r.get("adset_name", "—"),
            "impressions":   _safe_int(r.get("impressions")),
            "reach":         _safe_int(r.get("reach")),
            "clicks":        _safe_int(r.get("clicks")),
            "link_clicks":   _safe_int(r.get("inline_link_clicks")),
            "spend":         _safe_float(r.get("spend")),
            "cpc":           _safe_float(r.get("cpc")),
            "ctr":           _safe_float(r.get("ctr")),
            "frequency":     _safe_float(r.get("frequency")),
            "conversions":   _purchases(r.get("actions")),
            "cpa":           _cpa(r.get("cost_per_action_type")),
        }

    def _parse_ad_row(r):
        actions  = r.get("actions") or []
        cpa_list = r.get("cost_per_action_type") or []
        spend    = _safe_float(r.get("spend"))
        imp      = _safe_int(r.get("impressions"))
        reach    = _safe_int(r.get("reach"))
        lk       = _safe_int(r.get("inline_link_clicks"))
        out      = _outbound_clicks_count(r.get("outbound_clicks"))
        conv     = _purchases(actions)
        cpa_val  = _cpa(cpa_list)
        lp       = _action_count(actions, _LANDING_PAGE_TYPES)
        cart     = _action_count(actions, _ADD_TO_CART_TYPES)
        chk      = _action_count(actions, _CHECKOUT_TYPES)
        camp_id  = r.get("campaign_id", "")
        adset_id = r.get("adset_id", "")
        ad_id    = r.get("ad_id", "")

        # Video metrics
        vid_plays  = _video_action_val(r.get("video_play_actions"))
        vid_p25    = _video_action_val(r.get("video_p25_watched_actions"))
        vid_p50    = _video_action_val(r.get("video_p50_watched_actions"))
        vid_p75    = _video_action_val(r.get("video_p75_watched_actions"))
        vid_p100   = _video_action_val(r.get("video_p100_watched_actions"))
        vid_time   = _video_avg_time(r.get("video_avg_time_watched_actions"))
        thruplays  = _video_action_val(r.get("video_thruplay_watched_actions"))

        # Engagement breakdown
        post_eng   = _action_count(actions, _POST_ENGAGEMENT_TYPES)
        page_eng   = _action_count(actions, _PAGE_ENGAGEMENT_TYPES)
        reactions  = _action_count(actions, _POST_REACTION_TYPES)
        comments   = _action_count(actions, _POST_COMMENT_TYPES)
        shares     = _action_count(actions, _POST_SHARE_TYPES)
        saves      = _action_count(actions, _POST_SAVE_TYPES)
        page_likes = _action_count(actions, _PAGE_LIKE_TYPES)
        photo_views= _action_count(actions, _PHOTO_VIEW_TYPES)
        leads      = _action_count(actions, _LEAD_TYPES)
        app_inst   = _action_count(actions, _APP_INSTALL_TYPES)

        # Cost per lead / install
        cost_lead = _cost_for_type(cpa_list, _LEAD_TYPES) or (round(spend / leads, 4) if leads else 0.0)
        cost_app  = _cost_for_type(cpa_list, _APP_INSTALL_TYPES) or (round(spend / app_inst, 4) if app_inst else 0.0)

        # ROAS & purchase value
        action_values_list = r.get("action_values") or []
        purch_value = _purchase_value(action_values_list)
        roas        = round(purch_value / spend, 2) if spend else 0.0

        camp  = _camp_meta.get(camp_id, {})
        adset = _adset_meta.get(adset_id, {})

        def _fmt_date(iso: str) -> str:
            return iso[:10] if iso and len(iso) >= 10 else "—"

        _start = camp.get("start_time", "")
        _end   = camp.get("stop_time", "")

        return {
            "ad_id":               ad_id,
            "ad_name":             r.get("ad_name", "—"),
            "campaign_id":         camp_id,
            "campaign_name":       r.get("campaign_name", "—"),
            "campaign_created":    camp.get("created_time", ""),
            "campaign_start":      _fmt_date(_start),
            "campaign_end":        _fmt_date(_end),
            "delivery_status":     _STATUS_MAP.get(camp.get("status", ""), "not_delivering") if imp > 0 else ("inactive" if camp.get("status") == "PAUSED" else "not_delivering"),
            "delivery_level":      "ad",
            "adset_id":            adset_id,
            "adset_name":          r.get("adset_name", "—"),
            "objective":           camp.get("objective", "—"),
            "result_type":         "Website purchases" if camp.get("objective", "") in ("OUTCOME_SALES", "CONVERSIONS") else ("Website purchases" if conv > 0 else "—"),
            "conversions":         conv,
            "cpa":                 cpa_val if cpa_val else (round(spend / conv, 2) if conv else 0.0),
            "spend":               spend,
            "campaign_budget":     camp.get("budget", 0.0),
            "campaign_budget_type":camp.get("budget_type", "—"),
            "adset_budget":        adset.get("budget", 0.0),
            "adset_budget_type":   adset.get("budget_type", "—"),
            "reach":               reach,
            "cpm_reach":           round(spend / reach * 1000, 4) if reach else 0.0,
            "impressions":         imp,
            "cpm":                 round(spend / imp * 1000, 4) if imp else 0.0,
            "frequency":           _safe_float(r.get("frequency")),
            "clicks":              _safe_int(r.get("clicks")),
            "cpc":                 _safe_float(r.get("cpc")),
            "link_clicks":         lk,
            "cpc_link":            round(spend / lk, 4) if lk else 0.0,
            "ctr":                 _safe_float(r.get("ctr")),
            "ctr_link":            round(lk / imp * 100, 4) if imp else 0.0,
            "outbound_clicks":     out,
            "outbound_ctr":        round(out / imp * 100, 4) if imp else 0.0,
            "cost_per_outbound":   round(spend / out, 4) if out else 0.0,
            "landing_page_views":  lp,
            "cost_per_lp_view":    _cost_for_type(cpa_list, _LANDING_PAGE_TYPES) or (round(spend / lp, 4) if lp else 0.0),
            "adds_to_cart":        cart,
            "cost_per_add_to_cart":_cost_for_type(cpa_list, _ADD_TO_CART_TYPES) or (round(spend / cart, 4) if cart else 0.0),
            "checkouts":           chk,
            "cost_per_checkout":   _cost_for_type(cpa_list, _CHECKOUT_TYPES) or (round(spend / chk, 4) if chk else 0.0),
            "quality_ranking":     r.get("quality_ranking", "—"),
            "engagement_ranking":  r.get("engagement_rate_ranking", "—"),
            "conversion_ranking":  r.get("conversion_rate_ranking", "—"),
            # Video
            "video_plays":         vid_plays,
            "video_p25":           vid_p25,
            "video_p50":           vid_p50,
            "video_p75":           vid_p75,
            "video_p100":          vid_p100,
            "video_avg_time":      vid_time,
            "thruplays":           thruplays,
            # Engagement breakdown
            "post_engagement":     post_eng,
            "page_engagement":     page_eng,
            "post_reactions":      reactions,
            "post_comments":       comments,
            "post_shares":         shares,
            "post_saves":          saves,
            "page_likes":          page_likes,
            "photo_views":         photo_views,
            # Leads & installs
            "leads":               leads,
            "cost_per_lead":       cost_lead,
            "app_installs":        app_inst,
            "cost_per_app_install":cost_app,
            # Revenue
            "purchase_value":      purch_value,
            "roas":                roas,
        }

    # ── Adset level ───────────────────────────────────────────────────────────
    adsets = []
    try:
        adset_rows = _get_ads_filtered(
            f"{AD_ACCOUNT_ID}/insights",
            {"level": "adset", "fields": _ADSET_FIELDS,
             "time_range": time_range, "limit": 500},
            "campaign.id", period_ids,
        )
        for r in adset_rows:
            adsets.append(_parse_adset_row(r))
        print(f"DEBUG adset insights: {len(adsets)} adsets")
    except Exception as e:
        print(f"DEBUG adset insights error: {e}")

    # ── Ad level ──────────────────────────────────────────────────────────────
    ads = []
    try:
        ad_rows = _get_ads_filtered(
            f"{AD_ACCOUNT_ID}/insights",
            {"level": "ad", "fields": _AD_FIELDS,
             "time_range": time_range, "limit": 500},
            "campaign.id", period_ids,
        )
        for r in ad_rows:
            ads.append(_parse_ad_row(r))
        print(f"DEBUG ad insights: {len(ads)} ads")
    except Exception as e:
        print(f"DEBUG ad insights error: {e}")

    return {
        "adsets":  adsets,
        "ads":     ads,
        "period":  {"since": since, "until": until},
    }


def fetch_reach_for_ids(camp_ids: tuple, since: str, until: str) -> int:
    """
    Fetch deduplicated reach for a specific set of campaign IDs.
    Used by PAR OBJECTIF to get accurate combined reach for selected objectives.
    camp_ids must be a tuple (hashable) for st.cache_data.
    """
    if not camp_ids:
        return 0
    try:
        time_range = f'{{"since":"{since}","until":"{until}"}}'
        resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "account",
            "fields":     "reach",
            "filtering":  json.dumps([{
                "field": "campaign.id", "operator": "IN", "value": list(camp_ids)
            }]),
            "time_range": time_range,
        })
        rows = resp.get("data", [])
        if rows:
            return _safe_int(rows[0].get("reach"))
    except Exception as e:
        print(f"DEBUG boost: fetch_reach_for_ids error: {e}")
    return 0
