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
            if resp.status_code == 429:
                time.sleep(RETRY_BACKOFF ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            print(f"DEBUG ads: request failed (attempt {attempt}): {exc}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF ** attempt)

    return {}


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
def _get_footland_ids() -> list:
    """Fetch all Footland campaign IDs from the ad account."""
    try:
        resp = _get_ads(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,name",
            "limit":  500,
        })
        all_camps = resp.get("data", [])
        ids = [c["id"] for c in all_camps if any(kw in c.get("name", "") for kw in FOOTLAND_CAMPAIGN_KEYWORDS)]
        print(f"DEBUG boost: {len(ids)} Footland campaign IDs found")
        return ids
    except Exception as e:
        print(f"DEBUG boost: _get_footland_ids error: {e}")
        return []


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
        resp_meta = _get_ads(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,effective_status,daily_budget,lifetime_budget",
            "limit":  500,
        })
        for c in resp_meta.get("data", []):
            cid = c.get("id", "")
            daily    = _safe_float(c.get("daily_budget",    0)) / 100
            lifetime = _safe_float(c.get("lifetime_budget", 0)) / 100
            if daily > 0:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": daily, "budget_type": "Daily"}
            elif lifetime > 0:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": lifetime, "budget_type": "Lifetime"}
            else:
                _camp_meta[cid] = {"status": c.get("effective_status", "—"),
                                   "budget": 0.0, "budget_type": "—"}
    except Exception as e:
        print(f"DEBUG boost: campaign meta fetch error: {e}")

    if not footland_ids:
        return out

    _FILTERING = json.dumps([{
        "field":    "campaign.id",
        "operator": "IN",
        "value":    footland_ids,
    }])

    # ── 2. Account-level deduplicated reach (Footland only) ───────────────────
    try:
        # Use a more explicit time_range parameter for account insights
        resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
            "level":         "account",
            "fields":        "reach",
            "filtering":     _FILTERING,
            "time_range":    time_range,
        })
        rows_acc = resp.get("data", [])
        if rows_acc:
            out["totals"]["reach"] = _safe_int(rows_acc[0].get("reach"))
    except Exception as e:
        print(f"DEBUG boost: account-level reach error: {e}")

    # ── 3. Campaign-level insights (Footland only) ────────────────────────────
    try:
        # Ensure the time_range is strictly passed to prevent lifetime defaults
        resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "campaign",
            "fields":     _FIELDS,
            "filtering":  _FILTERING,
            "time_range": time_range,
            "limit":      500,
        })
        rows = resp.get("data", [])

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
            cost_lp_val     = _cost_for_type(cpa_list, _LANDING_PAGE_TYPES)
            cost_cart_val   = _cost_for_type(cpa_list, _ADD_TO_CART_TYPES)
            cost_chk_val    = _cost_for_type(cpa_list, _CHECKOUT_TYPES)
            cpm_val         = round(spend_val / imp_val * 1000, 4) if imp_val else 0.0
            cpc_link_val    = round(spend_val / link_clicks_val, 4) if link_clicks_val else 0.0
            ctr_link_val    = round(link_clicks_val / imp_val * 100, 4) if imp_val else 0.0
            cost_out_val    = round(spend_val / outbound_val, 4) if outbound_val else 0.0

            meta = _camp_meta.get(camp_id, {})

            campaigns.append({
                "campaign_id":            camp_id,
                "name":                   r.get("campaign_name", "—"),
                "objective":              objective,
                "delivery_status":        meta.get("status", "—"),
                "budget":                 meta.get("budget", 0.0),
                "budget_type":            meta.get("budget_type", "—"),
                "spend":                  spend_val,
                "conversions":            purchases,
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

    # insights-level filter (campaign.id is valid here)
    _FILTERING = json.dumps([{
        "field":    "campaign.id",
        "operator": "IN",
        "value":    footland_ids,
    }])
    # non-insights endpoints use campaign_id (no dot notation)
    _CAMP_ID_FILTER = json.dumps([{
        "field":    "campaign_id",
        "operator": "IN",
        "value":    footland_ids,
    }])
    footland_set = set(footland_ids)

    # ── 1. Campaign metadata (objective, status, budget) ──────────────────────
    # Fetch ALL campaigns (no filter — id-based filter not supported here),
    # then keep only Footland ones.
    _camp_meta: dict[str, dict] = {}
    try:
        resp = _get_ads(f"{AD_ACCOUNT_ID}/campaigns", {
            "fields": "id,objective,effective_status,daily_budget,lifetime_budget,created_time,start_time,stop_time",
            "limit":  500,
        })
        for c in resp.get("data", []):
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
        resp = _get_ads(f"{AD_ACCOUNT_ID}/adsets", {
            "fields":    "id,campaign_id,daily_budget,lifetime_budget,start_time,end_time",
            "filtering": _CAMP_ID_FILTER,
            "limit":     500,
        })
        for a in resp.get("data", []):
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
        resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "adset",
            "fields":     _ADSET_FIELDS,
            "filtering":  _FILTERING,
            "time_range": time_range,
            "limit":      500,
        })
        for r in resp.get("data", []):
            adsets.append(_parse_adset_row(r))
        print(f"DEBUG adset insights: {len(adsets)} adsets")
    except Exception as e:
        print(f"DEBUG adset insights error: {e}")

    # ── Ad level ──────────────────────────────────────────────────────────────
    ads = []
    try:
        resp = _get_ads(f"{AD_ACCOUNT_ID}/insights", {
            "level":      "ad",
            "fields":     _AD_FIELDS,
            "filtering":  _FILTERING,
            "time_range": time_range,
            "limit":      500,
        })
        for r in resp.get("data", []):
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
