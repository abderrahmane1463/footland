"""
api/instagram.py — Instagram Graph API fetch functions (organic only).
"""

from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

from dateutil import parser as dateparser

from config import INSTAGRAM_USER_ID, IG_MEDIA_FIELDS
from api.base import _get, _date_range


# ─── Instagram — Profile & Insights ──────────────────────────────────────────
def fetch_ig_profile(days: int, start: str = None, end: str = None) -> dict:
    """
    Returns Instagram follower count and daily profile insights,
    applying the same robust 'Retry & Fallback' logic as the Facebook section.
    """
    since, until = _date_range(days, start, end)

    # Use timestamps for better API compatibility (from diagnostic)
    # until_ts_series gets +1 day so single-day periods (e.g. Yesterday where since==until)
    # produce a non-zero window for daily series calls — otherwise the API returns nothing.
    # until_ts_exact stays as-is for metric_type=total_value reach calls which require
    # a window of exactly ≤ 30 days — adding +1 day would push 30-day periods to 31 → 0.
    try:
        since_ts       = int(dateparser.parse(since).timestamp())
        until_ts       = int((dateparser.parse(until) + timedelta(days=1)).timestamp())  # for daily series
        until_ts_exact = int(dateparser.parse(until).timestamp())                         # for reach total_value
    except:
        since_ts = until_ts = until_ts_exact = since

    result = {
        "followers_count": 0,
        "reach": [],
        "impressions": [],
        "profile_views": [],
        "follower_series": [],
        "follower_additions": [],
        "period_reach": 0,
        "story_impressions": 0,
        "username": "footland"
    }

    # 1. Total Followers (Fallback logic like FB page_fans)
    try:
        data = _get(INSTAGRAM_USER_ID, {"fields": "followers_count,username"})
        result["followers_count"] = data.get("followers_count", 0)
        result["username"] = data.get("username", "footland")
    except Exception as e:
        print(f"DEBUG: IG followers snapshot error: {e}")

    # 2. Daily Visibility and Interaction Metrics
    # v22+: reach/views/profile_views/total_interactions require metric_type=time_series
    # for daily series (old period=day alone is rejected).
    # reach uses until_ts_exact to stay within the 30-day API window limit.
    metrics_to_fetch = {
        "reach":              ("reach",                    until_ts_exact),  # strict 30-day limit
        "views":              ("impressions",              until_ts),
        "profile_views":      ("profile_views",            until_ts),
        "total_interactions": ("total_interactions_series", until_ts),
    }
    for metric, (key, metric_until) in metrics_to_fetch.items():
        for m_type in ("time_series", "day"):
            # "time_series" is the v22+ way; "day" (no metric_type) is the legacy fallback
            params = {
                "metric": metric,
                "period": "day",
                "since":  since_ts,
                "until":  metric_until,
            }
            if m_type == "time_series":
                params["metric_type"] = "time_series"
            try:
                data = _get(f"{INSTAGRAM_USER_ID}/insights", params)
                for m in data.get("data", []):
                    if m["name"] == metric:
                        vals = [
                            {"date": v["end_time"][:10], "value": v["value"]}
                            for v in m.get("values", [])
                            if isinstance(v.get("value"), (int, float))
                        ]
                        if vals:
                            result[key] = vals
                if result[key]:
                    break   # got data — no need to try legacy fallback
            except Exception as e:
                print(f"DEBUG: IG {metric} ({m_type}) fetch error: {e}")
                if m_type == "time_series":
                    continue   # try legacy period=day
                # Final fallback: try 'impressions' if 'views' failed
                if metric == "views" and not result["impressions"]:
                    try:
                        data = _get(f"{INSTAGRAM_USER_ID}/insights", {
                            "metric": "impressions", "period": "day",
                            "metric_type": "time_series",
                            "since": since_ts, "until": until_ts,
                        })
                        for m in data.get("data", []):
                            result["impressions"] = [
                                {"date": v["end_time"][:10], "value": v["value"]}
                                for v in m.get("values", [])
                            ]
                    except Exception:
                        pass

    # profile_views fallback is now handled inside the metrics_to_fetch loop above

    # 3. Deduplicated Period Reach — try multiple approaches to get the closest
    # value to what Meta Business Suite reports.

    # period_reach — metric_type=total_value (deduplicated full-period aggregate)
    # Uses until_ts_exact (no +1 day) — API only accepts windows of ≤ 30 days.
    try:
        data_p = _get(f"{INSTAGRAM_USER_ID}/insights", {
            "metric": "reach",
            "period": "day",
            "metric_type": "total_value",
            "since": since_ts,
            "until": until_ts_exact,
        })
        for m in data_p.get("data", []):
            if m["name"] == "reach":
                tv = m.get("total_value", {})
                if isinstance(tv, dict):
                    val = tv.get("value", 0)
                elif isinstance(tv, (int, float)):
                    val = int(tv)
                else:
                    val = 0
                result["period_reach"] = val
                print(f"DEBUG IG reach total_value = {val}")
    except Exception as e:
        print(f"DEBUG: IG reach total_value error: {e}")

    # 4. Daily Follower Series — try multiple metric names across API versions
    for m_name in ["follower_count", "profile_follows", "total_followers_count"]:
        try:
            data = _get(f"{INSTAGRAM_USER_ID}/insights", {
                "metric": m_name,
                "period": "day",
                "since": since_ts,
                "until": until_ts,
            })
            for m in data.get("data", []):
                if m["name"] == m_name:
                    vals = m.get("values", [])
                    if vals:
                        result["follower_additions"] = [
                            {"date": v["end_time"][:10], "value": v["value"]}
                            for v in vals
                        ]
                        print(f"DEBUG IG follower series via '{m_name}': {len(vals)} points")
            if result["follower_additions"]:
                break
        except Exception as e:
            print(f"DEBUG: IG {m_name} error: {e}")

    # Fallback: try metric_type=total_value for follower_count
    if not result["follower_additions"]:
        try:
            data = _get(f"{INSTAGRAM_USER_ID}/insights", {
                "metric": "follower_count",
                "period": "day",
                "metric_type": "total_value",
                "since": since_ts,
                "until": until_ts,
            })
            for m in data.get("data", []):
                if m["name"] == "follower_count":
                    vals = m.get("values", [])
                    if vals:
                        result["follower_additions"] = [
                            {"date": v["end_time"][:10], "value": v["value"]}
                            for v in vals
                        ]
                        print(f"DEBUG IG follower_count total_value: {len(vals)} points")
        except Exception as e:
            print(f"DEBUG: IG follower_count total_value error: {e}")

    # 5. Stories Impressions — Stories are NOT included in the account-level
    #    impressions metric. Fetch active stories and sum their view counts.
    try:
        stories_data = _get(f"{INSTAGRAM_USER_ID}/stories", {
            "fields": "id,insights.metric(impressions,reach)",
            "limit": 100,
        })
        story_imp_total = 0
        for story in stories_data.get("data", []):
            ins_list = story.get("insights", {}).get("data", [])
            for item in ins_list:
                if item["name"] == "impressions":
                    val = item.get("values", [{}])[0].get("value", 0) if item.get("values") else 0
                    story_imp_total += val
        if story_imp_total:
            result["story_impressions"] = story_imp_total
            print(f"DEBUG IG story impressions = {story_imp_total}")
    except Exception as e:
        print(f"DEBUG: IG stories impressions error: {e}")

    result["follower_series"] = result["follower_additions"]
    return result


# ─── Instagram — Engagement ───────────────────────────────────────────────────
def fetch_ig_engagement(days: int, start: str = None, end: str = None) -> dict:
    """
    Returns aggregated Instagram engagement metrics, mirroring
    the Facebook interaction breakdown pattern.
    """
    since, until = _date_range(days, start, end)

    try:
        since_ts = int(dateparser.parse(since).timestamp())
        until_ts = int(dateparser.parse(until).timestamp())
    except:
        since_ts, until_ts = since, until

    result = {"likes": 0, "comments": 0, "shares": 0, "saves": 0, "total_interactions": 0, "views": 0, "daily": []}

    # v22+: all metrics require metric_type=total_value for period aggregation.
    # `views` = account-level total displays (posts + reels + stories) — single call,
    #   replaces the per-post summation approach entirely.
    # `total_interactions` fetched directly — may differ slightly from sum of individuals.
    metric_map = {
        "likes":              "likes",
        "comments":           "comments",
        "shares":             "shares",
        "saves":              "saves",
        "total_interactions": "total_interactions",
        "views":              "views",
    }

    # ── 1. Period totals (metric_type=total_value) ─────────────────────────────
    for metric, key in metric_map.items():
        try:
            data = _get(f"{INSTAGRAM_USER_ID}/insights", {
                "metric":      metric,
                "period":      "day",
                "metric_type": "total_value",
                "since":       since_ts,
                "until":       until_ts,
            })
            for m in data.get("data", []):
                if m["name"] == metric:
                    tv = m.get("total_value", {})
                    if isinstance(tv, dict):
                        result[key] = tv.get("value", 0)
                    elif isinstance(tv, (int, float)):
                        result[key] = int(tv)
        except Exception as e:
            print(f"DEBUG IG engagement total_value {metric}: {e}")

    # ── 2. Daily series (metric_type=time_series) — optional, for charts ──────
    for metric, key in metric_map.items():
        try:
            data = _get(f"{INSTAGRAM_USER_ID}/insights", {
                "metric":      metric,
                "period":      "day",
                "metric_type": "time_series",
                "since":       since_ts,
                "until":       until_ts,
            })
            for m in data.get("data", []):
                if m["name"] == metric:
                    vals = m.get("values", [])
                    result["daily"].extend([
                        {"date": v["end_time"][:10], "metric": key, "value": v["value"]}
                        for v in vals if isinstance(v.get("value"), (int, float))
                    ])
        except Exception:
            pass   # daily series is optional — totals already captured above

    return result


# ─── Instagram — Media / Top Posts ───────────────────────────────────────────
def fetch_ig_posts(days: int = None, start: str = None, end: str = None, limit: int = 20) -> list[dict]:
    """
    Returns Instagram media within the selected date range.
    """
    params = {"fields": IG_MEDIA_FIELDS, "limit": limit}
    if days or (start and end):
        since, until = _date_range(days or 30, start, end)
        params["since"] = since
        # Make end date inclusive for media list
        try:
            params["until"] = str((dateparser.parse(until) + timedelta(days=1)).date())
        except:
            params["until"] = until

    try:
        data = _get(f"{INSTAGRAM_USER_ID}/media", params)
        posts = data.get("data", [])

        def _process_ig_post(p):
            post_id    = p["id"]
            media_type = p.get("media_type", "")

            # ── Known API limitations (Meta Graph API for Business accounts) ──────
            #
            # like_count  : The API returns a privacy-filtered subset — NOT the same
            #               number shown publicly on Instagram (e.g. API returns 28,
            #               Instagram shows 1.4K). This is a Meta API restriction and
            #               cannot be bypassed. We mitigate it using total_interactions
            #               from insights (see below).
            #
            # comments_count: Same privacy filtering as like_count. Minor difference
            #               (e.g. 0 vs 2) — no reliable workaround available.
            #
            # impressions : Deprecated by Meta from v22+ for IMAGE and CAROUSEL posts.
            #               Returns a 400 error for those types — the metric no longer
            #               exists. Only VIDEO (video_views) and Reels (plays) still
            #               have a view-count equivalent. The only universal visibility
            #               metric remaining is `reach` (unique accounts that saw post).
            # ─────────────────────────────────────────────────────────────────────
            likes    = p.get("like_count", 0)
            comments = p.get("comments_count", 0)

            # ── Insights from /{post_id}/insights ────────────────────────────────
            # Waterfall: try the richest metric set first; on 400 try the next one.
            # Reels are returned as media_type=VIDEO with /reel/ in the permalink.
            impressions, reach, saves, shares, total_int_val = 0, 0, 0, 0, 0

            is_reel = (
                media_type in ("REEL", "IG_REEL")
                or "/reel/" in p.get("permalink", "")
            )
            # `views` is confirmed working for ALL post types (IMAGE, CAROUSEL, REEL, VIDEO).
            # Confirmed from live API tests:
            #   IMAGE    → views=1110  (impressions=400 deprecated, plays=400 invalid)
            #   CAROUSEL → views=4531  (impressions=400 deprecated)
            #   REEL     → views=2354  (plays=400 deprecated, impressions=400 not supported)
            # `video_views` kept for VIDEO as it measures plays ≥3s (more meaningful for video).
            if is_reel:
                metric_sets = [
                    "views,reach,saved,shares,total_interactions",
                    "reach,saved,shares,total_interactions",
                    "reach,saved",
                ]
            elif media_type == "VIDEO":
                metric_sets = [
                    "video_views,views,reach,saved,shares,total_interactions",
                    "views,reach,saved,shares,total_interactions",
                    "reach,saved",
                ]
            else:
                # IMAGE / CAROUSEL_ALBUM — `views` is the only view-count metric in v22+
                metric_sets = [
                    "views,reach,saved,shares,total_interactions",
                    "reach,saved,shares,total_interactions",
                    "reach,saved",
                ]

            for m_list in metric_sets:
                try:
                    d = _get(f"{post_id}/insights", {"metric": m_list})
                    if not d.get("data"):
                        continue
                    for item in d["data"]:
                        name = item.get("name", "")
                        val  = (item["values"][0].get("value", 0)
                                if item.get("values") else item.get("value", 0))
                        # `views` = v22+ unified view count (replaces impressions for images)
                        if name in ("impressions", "plays", "video_views", "views"):
                            impressions = max(impressions, val)
                        elif name == "reach":
                            reach = val
                        elif name == "saved":
                            saves = val
                        elif name == "shares":
                            shares = val
                        elif name == "total_interactions":
                            total_int_val = val
                    break
                except Exception as e:
                    err_txt = str(e)
                    if "400" in err_txt or "Unsupported" in err_txt or "invalid" in err_txt.lower():
                        continue
                    break

            # ── Like count correction via total_interactions ───────────────────
            # total_interactions (from Meta's analytics backend) = likes + comments
            # + saves + shares. It is NOT subject to the same privacy filtering as
            # like_count, so we can infer a more accurate likes figure from it.
            # We only override like_count when the inferred value is higher.
            if total_int_val > 0:
                inferred = max(0, total_int_val - comments - saves - shares)
                if inferred > likes:
                    likes = inferred

            # Extract hour + weekday from full timestamp for heatmap
            _ts = p.get("timestamp", "")
            try:
                from datetime import datetime as _dt
                _parsed = _dt.strptime(_ts[:19], "%Y-%m-%dT%H:%M:%S")
                _post_hour    = _parsed.hour
                _post_weekday = _parsed.weekday()   # 0=Mon … 6=Sun
            except Exception:
                _post_hour, _post_weekday = -1, -1

            return {
                "id":               p.get("id", ""),
                "text":             p.get("caption", "")[:120] if p.get("caption") else "",
                "created_time":     _ts[:10],
                "media_type":       p.get("media_type", ""),
                "thumbnail":        p.get("thumbnail_url") or p.get("media_url", ""),
                "permalink":        p.get("permalink", ""),
                "reach":            reach,
                "impressions":      impressions,
                "reactions":        likes,
                "comments":         comments,
                "saves":            saves,
                "shares":           shares,
                "total_interactions": likes + comments + saves + shares,
                "post_hour":        _post_hour,
                "post_weekday":     _post_weekday,
            }

        # Parallelize the insight fetching (Restored for speed)
        with ThreadPoolExecutor(max_workers=20) as executor:
            parsed = list(executor.map(_process_ig_post, posts))

        return parsed
    except Exception as e:
        print(f"DEBUG: IG posts error: {e}")
        return []


# ─── Instagram — Post totals (all posts in period) ───────────────────────────
def fetch_ig_post_totals(days: int = None, start: str = None, end: str = None) -> dict:
    """
    Paginates through ALL Instagram posts in the period, fetches per-post
    impressions via insights, and returns summed KPI totals.

    Used for the 📢 Impressions KPI so the value covers all posts, not
    just the 20 shown in the Top Content tab.
    """
    since, until = _date_range(days or 30, start, end)
    try:
        until_incl = str((dateparser.parse(until) + timedelta(days=1)).date())
    except Exception:
        until_incl = until

    params = {
        "fields": "id,timestamp,media_type,permalink",
        "limit":  100,
        "since":  since,
        "until":  until_incl,
    }

    all_posts = []
    for _ in range(10):          # max 10 pages = 1 000 posts safety cap
        try:
            data = _get(f"{INSTAGRAM_USER_ID}/media", params)
        except Exception as e:
            print(f"DEBUG fetch_ig_post_totals page error: {e}")
            break
        posts = data.get("data", [])
        if not posts:
            break
        all_posts.extend(posts)
        next_url    = data.get("paging", {}).get("next")
        next_cursor = data.get("paging", {}).get("cursors", {}).get("after")
        if not next_url or not next_cursor:
            break
        params = {**params, "after": next_cursor}

    def _get_views_per_post(p):
        """
        Return the view count for a single post — used to total the 📢 Vues KPI.

        Confirmed working metrics per post type (live API test, v19 / v22 rules):
          IMAGE    → `views`       (impressions=400 deprecated, plays=400 invalid)
          CAROUSEL → `views`       (impressions=400 deprecated)
          REEL     → `views`       (plays=400 deprecated, impressions=400 unsupported)
          VIDEO    → `video_views` preferred (plays ≥3s), then `views`, then `reach`
        """
        post_id    = p["id"]
        media_type = p.get("media_type", "")
        is_reel = (
            media_type in ("REEL", "IG_REEL")
            or "/reel/" in p.get("permalink", "")
        )
        if is_reel or media_type not in ("VIDEO",):
            # IMAGE / CAROUSEL / REEL — `views` is the only view metric in v22+
            metric_sets = ["views,reach", "reach"]
        else:
            # VIDEO: video_views (plays ≥3s) is more meaningful; views as fallback
            metric_sets = ["video_views,views,reach", "views,reach", "reach"]

        for m_list in metric_sets:
            try:
                d = _get(f"{post_id}/insights", {"metric": m_list})
                val = 0
                for item in d.get("data", []):
                    name = item.get("name", "")
                    v = (item["values"][0].get("value", 0)
                         if item.get("values") else item.get("value", 0))
                    if name in ("video_views", "views"):
                        val = max(val, v)
                    elif name == "reach" and val == 0:
                        val = v
                if d.get("data"):
                    return val
            except Exception as e:
                err_txt = str(e)
                if "400" in err_txt or "Unsupported" in err_txt:
                    continue
                break
        return 0

    total_reach = 0
    total_posts = len(all_posts)

    if all_posts:
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(_get_views_per_post, all_posts))
        total_reach = sum(results)

    print(f"DEBUG fetch_ig_post_totals: {total_posts} posts, {total_reach} total views")
    return {
        "total_posts":  total_posts,
        # Sum of per-post `views` across all posts in the period.
        # `views` confirmed working for IMAGE, CAROUSEL, REEL, VIDEO (v22+).
        "total_impressions": total_reach,
    }


# ─── Instagram — Conversations (Community Management) ─────────────────────────
def fetch_ig_conversations(days: int = 30, start: str = None, end: str = None, limit: int = 25) -> dict:
    """
    Returns Instagram DM thread metadata for community management stats.
    Uses the same /conversations endpoint as Facebook with platform=instagram.
    Requires instagram_manage_messages permission on the connected page.
    """
    from config import FACEBOOK_PAGE_ID

    since, until = _date_range(days, start, end)

    result = {
        "total_threads": 0,
        "new_threads": 0,
        "replied_threads": 0,
        "response_times_minutes": [],
        "recent_unanswered": [],
    }

    try:
        data = _get(f"{FACEBOOK_PAGE_ID}/conversations", {
            "platform": "instagram",
            "fields": "id,updated_time,messages{created_time,from,message}",
            "limit": limit,
        })
        threads = data.get("data", [])
        result["total_threads"] = len(threads)

        for thread in threads:
            msgs = thread.get("messages", {}).get("data", [])

            # Count threads whose first message falls within the date range
            if msgs:
                first_msg_date = msgs[-1].get("created_time", "")[:10]
                if since <= first_msg_date <= until:
                    result["new_threads"] += 1

            if len(msgs) < 2:
                result["recent_unanswered"].append({
                    "text": msgs[0].get("message", "")[:80] if msgs else "",
                    "time": thread.get("updated_time", "")[:16],
                })
                continue

            # Check if page replied (sender id matches page)
            page_replied = any(
                str(m.get("from", {}).get("id", "")) == str(FACEBOOK_PAGE_ID)
                for m in msgs
            )
            if page_replied:
                result["replied_threads"] += 1
                first_msg_time = dateparser.parse(msgs[-1]["created_time"])
                page_reply = next(
                    (m for m in reversed(msgs)
                     if str(m.get("from", {}).get("id", "")) == str(FACEBOOK_PAGE_ID)),
                    None,
                )
                if page_reply:
                    reply_time = dateparser.parse(page_reply["created_time"])
                    delta_minutes = (reply_time - first_msg_time).total_seconds() / 60
                    if delta_minutes >= 0:
                        result["response_times_minutes"].append(delta_minutes)
            else:
                result["recent_unanswered"].append({
                    "text": msgs[0].get("message", "")[:80] if msgs else "",
                    "time": thread.get("updated_time", "")[:16],
                })

    except Exception as e:
        print(f"DEBUG: IG conversations error: {e}")

    return result
