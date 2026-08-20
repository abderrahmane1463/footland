# Footland Analytics Dashboard

A Streamlit dashboard for **organic** social media analytics (Facebook, Instagram),
paid Boost/Ads performance, and Google Analytics — built for Footland (sporting
goods retailer).

## Quick Start

```bash
pip install -r requirements.txt
export FOOTLAND_TOKEN="<meta-graph-api-long-lived-page-access-token>"
streamlit run app.py
```

The dashboard runs at `http://localhost:8501`.

See `.env.example` for the full list of environment variables required
(Supabase cache, Meta Graph API, Groq chatbot, Google Analytics).

## Architecture

```
app.py                    Streamlit entry point — routing, theming, prefetch threads
  ├── components/
  │   ├── sidebar.py       Platform selector, date range picker, refresh button
  │   ├── chatbot.py        Floating AI assistant (Groq / GPT-OSS)
  │   ├── ai_insights.py    Per-platform AI analysis report (trends + reco)
  │   ├── charts.py         Shared Plotly chart helpers
  │   └── skeleton.py        Loading-state shimmer placeholders
  ├── views/
  │   ├── facebook.py        Facebook tab (Audience, Engagement, Visibility, Posts, Community)
  │   ├── instagram.py       Instagram tab
  │   ├── boost.py           Paid Ads / Boost tab (Marketing API)
  │   ├── analytics.py       Google Analytics (GA4) tab
  │   ├── login.py           Supabase-auth login screen
  │   └── documentation.py   In-app documentation tab
  ├── api/
  │   ├── base.py            Shared HTTP helper (_get, retry/backoff, date utils)
  │   ├── facebook.py        Facebook Graph API endpoints
  │   ├── instagram.py       Instagram Graph API endpoints
  │   ├── boost.py           Marketing API endpoints (Boost tab only)
  │   └── ga4.py              Google Analytics Data API v1beta
  ├── db.py                  Supabase REST cache layer (metric_cache table)
  ├── auth.py                Supabase Auth (login, role lookup)
  ├── fetcher.py             Standalone script — pre-warms Supabase cache (cron / GitHub Actions)
  ├── ga4_auth.py            One-time OAuth flow for Google Analytics
  └── config.py              Constants, credentials, metric name lists
```

## Key Constraints

- **Organic-only**: `act_765947885726761` (the agency's shared ad account) is
  blocklisted in `config.py` / enforced by `api/base.py::_assert_not_blocked()`.
  Never fetch or display data from it outside the dedicated Boost tab's own
  Footland-only filtering.
- **No database migrations**: Supabase `metric_cache` table is created once via
  `python db_setup.py`. All other data comes live from Meta Graph API v19.0 and
  the GA4 Data API, cached in Supabase.
- **Date handling**: all date calculations use `datetime.now(timezone.utc)`.

## Caching

- Supabase (`db.py`) is a **permanent** cache — rolling periods ("Last 30 Days")
  are cached forever under a stable key and only refreshed on demand.
- `st.cache_data(ttl=900)` (15 min) wraps most per-session reads; demographics
  use a 60-minute TTL.
- The **"🔄 Refresh Data"** button invalidates the current platform/period in
  Supabase and clears Streamlit's cache.
- `fetcher.py` can be run on a schedule (see `.github/workflows/fetch.yml`) to
  pre-populate Supabase for every date-range preset.

## AI features

The analysis reports run on **DeepSeek** (`deepseek-v4-flash`, `DEEPSEEK_API_KEY`)
and fall back to **Groq** (`openai/gpt-oss-120b`, `GROQ_API_KEY`) if DeepSeek is
unreachable or its prepaid balance runs out. The chatbot runs on Groq only.

Two provider gotchas worth keeping:

- **`deepseek-v4-flash`, not `v4-pro`.** Pro spends its budget reasoning —
  4 773 reasoning tokens for *less* output than flash — takes over two minutes,
  and returns a completely empty message at `max_tokens=3000`.
- **Token budgets differ per provider.** DeepSeek needs 8 000 (flash used 3 153
  on one report); Groq rejects that ceiling with HTTP 413 and keeps 3 000.

**Analysis report** (`components/ai_insights.py`) — a "Générer le rapport
d'analyse" button on each platform produces a downloadable report that
interprets the numbers: what rose, what fell, the likely causes, and
recommendations. Three rules make it trustworthy:

- *Python computes, the model interprets.* Every value and variation is
  calculated in code; the model is forbidden from doing arithmetic. Left to
  itself it invented "0,022 EUR par impression" — wrong by 100x.
- *Deltas are the point.* Each `ctx_*` payload carries `_prev` (previous-period
  values under the same keys). Without them the model can only restate the KPI
  cards; with them it can explain a movement.
- *Paid traffic is disclosed.* Page reach and views include ads, so when the
  Boost tab has loaded, the ad-spend trend is passed along and the report must
  separate genuine organic performance from budget-driven lift.

Generation is cached on the KPI payload, so a period costs one API call however
often Streamlit reruns; changing period resets the button so a stale report
never sits under new figures.

**Floating chatbot** (`components/chatbot.py`) — bottom-right, toggled from the
sidebar; answers questions about the data currently on screen.

See the in-app **Documentation** tab for details.

## Logging

`log_refresh()` in `app.py` appends every manual refresh event to
`AI_CONTEXT_LOG.md`, automatically trimmed to the most recent 200 entries.

## Scratch Utilities

`scratch/` (gitignored, not tracked) is for one-off diagnostic scripts and is
not part of the app — do not import from it.
