"""
components/ai_insights.py — AI-generated analysis reports for each platform.

Produces a client-facing report that interprets the KPIs: what moved, why it
probably moved, and what to do about it. Generated on demand behind a button.

Design rules learned the hard way:

1. Python computes every number; the model only interprets. Left to itself the
   model invented "0,022 EUR par impression" (wrong by 100x). It is forbidden
   from doing arithmetic and may only restate figures it was handed.
2. Deltas are the whole point. Without a previous period the model can only
   restate the KPI cards — it cannot explain a rise or a fall.
3. Reach and views on a Facebook/Instagram page include paid traffic. When ad
   spend is known, it is passed as context so the report does not credit a
   budget increase to organic performance.
"""

import os
import time

import requests
import streamlit as st

from components.chatbot import GROQ_MODELS, _get_api_key, _md_to_html

try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq may not be installed yet
    Groq = None


# ─── Model providers ──────────────────────────────────────────────────────────
# DeepSeek is the primary: on the same payload it produced a visibly sharper
# report than gpt-oss (it read the CTR drop as a frequency effect rather than
# creative fatigue, and warned against judging awareness campaigns on CTR).
# Groq stays as the fallback so reports still generate if DeepSeek is down or
# the prepaid balance runs out.
#
# v4-flash, not v4-pro: pro spends its budget reasoning (4 773 reasoning tokens
# for LESS output than flash), takes over two minutes, and returned a
# completely empty message at max_tokens=3000.
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# Token budgets are per provider and deliberately different.
# DeepSeek needs headroom: flash spent 3 153 completion tokens on a Boost
# report, so a 3 000 ceiling truncated it mid-sentence.
# Groq rejects that same ceiling outright (HTTP 413 Payload Too Large), and
# gpt-oss only used 1 247 tokens for a full report anyway — so it keeps 3 000.
DEEPSEEK_MAX_TOKENS = 8000
GROQ_MAX_TOKENS = 3000
REQUEST_TIMEOUT = 180


def _get_deepseek_key() -> str | None:
    """Read DEEPSEEK_API_KEY from st.secrets first, then the environment."""
    try:
        key = st.secrets["DEEPSEEK_API_KEY"]
        if key:
            return key
    except Exception:  # noqa: BLE001 - secrets file may not exist at all
        pass
    return os.environ.get("DEEPSEEK_API_KEY")


# Keys carrying structure rather than a KPI value.
PREV_KEY = "_prev"
NOTES_KEY = "_notes"
_INTERNAL_KEYS = {PREV_KEY, NOTES_KEY}


# Human-readable labels with units. The model may not compute anything, so it
# can only reproduce the units it is handed — without these it writes
# "CTR est de 1.48" instead of "CTR de 1,48 %".
_KPI_LABELS = {
    "period":               "Période analysée",
    # shared
    "reach":                "Portée — comptes uniques touchés",
    "impressions":          "Impressions — affichages totaux",
    "engagement_rate":      "Taux d'engagement (%)",
    "posts_count":          "Publications publiées",
    "total_interactions":   "Interactions totales",
    "comments":             "Commentaires",
    "shares":               "Partages",
    "followers":            "Abonnés",
    # Facebook
    "new_followers":        "Nouveaux abonnés",
    "unfollows":            "Désabonnements",
    "content_interactions": "Interactions sur le contenu",
    "reactions":            "Réactions",
    # Instagram
    "views":                "Vues",
    "saves":                "Enregistrements",
    "likes":                "J'aime",
    # Boost / Meta Ads
    "campaigns_count":      "Campagnes actives",
    "link_clicks":          "Clics sur le lien",
    "cpc":                  "CPC — coût par clic (EUR)",
    "ctr":                  "CTR — taux de clic (%)",
    "spend":                "Montant dépensé (EUR)",
    "frequency":            "Répétition — impressions par personne touchée",
    "conversions":          "Commandes (achats)",
    "cpa":                  "Coût par acquisition (EUR)",
    # Google Analytics
    "active_users":         "Utilisateurs actifs",
    "new_users":            "Nouveaux utilisateurs",
    "sessions":             "Sessions",
    "engaged_sessions":     "Sessions engagées",
    "bounce_rate":          "Taux de rebond (%)",
    "page_views":           "Pages vues",
}


# ─── Prompt ───────────────────────────────────────────────────────────────────
_COMMON_RULES = """Tu es analyste senior en marketing digital. Tu rédiges un RAPPORT destiné au
client final (Footland, détaillant d'articles de sport en Algérie).

RÈGLES ABSOLUES :
- Tous les chiffres te sont fournis DÉJÀ CALCULÉS, variations comprises. Tu ne dois
  JAMAIS calculer une nouvelle valeur (ratio, moyenne, pourcentage, division).
  Reprends exclusivement les valeurs fournies, avec leur unité.
- Ton rôle est d'EXPLIQUER les hausses et les baisses en croisant les indicateurs
  entre eux, pas de les répéter. Quand tu avances une cause, dis clairement qu'il
  s'agit d'une hypothèse.
- Ne compare jamais le CTR entre objectifs différents : une campagne notoriété
  optimise la portée, pas le clic. Signale ce piège si c'est pertinent.
- Si un indicateur est absent ou nul, ignore-le. N'invente aucune donnée.
- Français professionnel, direct, sans jargon inutile. Pas de conclusion générique."""

_STRUCTURES = {
    "ads": """STRUCTURE EXACTE :
## Synthèse
(3-4 lignes : la tendance générale de la période)

## Ce qui a évolué et pourquoi
(les mouvements majeurs, chacun expliqué en croisant les indicateurs)

## Ce qui fonctionne / ce qui sous-performe
(campagnes concrètes, nommées quand elles sont fournies)

## Recommandations
(3 à 4 actions concrètes et priorisées)""",

    "social": """STRUCTURE EXACTE :
## Synthèse
(3-4 lignes : la tendance générale de la période)

## Ce qui a évolué et pourquoi
(les mouvements majeurs, chacun expliqué en croisant les indicateurs)

## Organique vs poussé par la publicité
(distingue ce qui relève vraiment de l'organique — interactions, abonnements,
enregistrements, commentaires — de ce qui est probablement porté par le budget
publicitaire. Sois explicite : la portée et les vues incluent le trafic payant.)

## Recommandations
(3 à 4 actions concrètes et priorisées)""",

    "web": """STRUCTURE EXACTE :
## Synthèse
(3-4 lignes : la tendance générale de la période)

## Ce qui a évolué et pourquoi
(les mouvements majeurs, chacun expliqué en croisant les indicateurs)

## Dépendance aux canaux
(d'où vient réellement le trafic, et quel risque cela représente)

## Recommandations
(3 à 4 actions concrètes et priorisées)""",
}


# ─── Payload building (all arithmetic happens here, never in the model) ───────
def _fmt(value) -> str:
    """Format a number the way the dashboard shows it.

    Sub-unit values keep four decimals: a CPC of 0,005 EUR rounded to two
    decimals reads "0,01" and its previous period "0,00", which would tell the
    client their clicks were free.
    """
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        decimals = 4 if 0 < abs(value) < 1 else 2
        return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return str(value)


def _variation(current, previous) -> str | None:
    """Percent change, computed in Python so the model never has to."""
    try:
        cur, prev = float(current), float(previous)
    except (TypeError, ValueError):
        return None
    if not prev:
        return None
    pct = (cur - prev) / abs(prev) * 100
    return f"{'+' if pct >= 0 else ''}{pct:.1f} %"


def build_payload(ctx: dict) -> str:
    """Turn a ctx_* dict into labelled lines carrying units and variations."""
    prev = ctx.get(PREV_KEY) or {}
    notes = ctx.get(NOTES_KEY) or []

    lines = []
    for key, value in ctx.items():
        if key in _INTERNAL_KEYS or value in (None, ""):
            continue
        label = _KPI_LABELS.get(key, key)
        if key == "period":
            lines.append(f"- {label} : {value}")
            continue

        row = f"- {label} : {_fmt(value)}"
        if key in prev and prev[key] not in (None, ""):
            row += f" (période précédente : {_fmt(prev[key])}"
            var = _variation(value, prev[key])
            row += f", variation : {var})" if var else ")"
        lines.append(row)

    payload = "\n".join(lines)
    if notes:
        payload += "\n\nCONTEXTE :\n" + "\n".join(f"- {n}" for n in notes)
    return payload


def paid_spend_note() -> list[str]:
    """Cross-platform context: if the Boost tab has been loaded, surface the ad
    spend trend so an organic report doesn't credit a budget rise to content."""
    boost = st.session_state.get("ctx_boost") or {}
    spend = boost.get("spend")
    prev_spend = (boost.get(PREV_KEY) or {}).get("spend")
    if not spend or not prev_spend:
        return []
    var = _variation(spend, prev_spend)
    if not var:
        return []
    return [
        f"Sur la même période, le budget publicitaire Meta a évolué de {var} "
        f"({_fmt(spend)} EUR contre {_fmt(prev_spend)} EUR). "
        f"La portée et les vues de la page incluent ce trafic payant."
    ]


# ─── Generation ───────────────────────────────────────────────────────────────
class _ReportError(RuntimeError):
    """Raised when no model produced a report.

    Raising rather than returning empty keeps failures out of the Streamlit
    cache, so a transient problem retries instead of being frozen for the TTL.
    """


def _try_deepseek(system: str, user: str) -> str:
    """Primary provider. Returns "" if unavailable so the caller falls back."""
    key = _get_deepseek_key()
    if not key:
        return ""

    for attempt in range(2):
        try:
            resp = requests.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                    "temperature": 0.4,
                    "max_tokens": DEEPSEEK_MAX_TOKENS,
                },
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if resp.status_code == 402:
                # Prepaid balance exhausted — no point retrying, fall back.
                print("DEBUG ai_insights: DeepSeek balance exhausted")
                return ""
            resp.raise_for_status()
            return (resp.json()["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:  # noqa: BLE001
            print(f"DEBUG ai_insights: DeepSeek failed: {exc}")
            return ""
    return ""


def _try_groq(system: str, user: str) -> str:
    """Fallback provider. Returns "" if unavailable."""
    api_key = _get_api_key()
    if not api_key or Groq is None:
        return ""

    client = Groq(api_key=api_key)
    for model in GROQ_MODELS:
        # Several reports in a row hit the free-tier rate limit, so back off
        # before falling through to the smaller model.
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    temperature=0.4,
                    max_tokens=GROQ_MAX_TOKENS,
                )
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
                break  # empty reply ⇒ next model, not the same one again
            except Exception as exc:  # noqa: BLE001
                if "429" in str(exc) or "rate_limit" in str(exc).lower():
                    time.sleep(3 * (attempt + 1))
                    continue
                print(f"DEBUG ai_insights: Groq {model} failed: {exc}")
                break
    return ""


@st.cache_data(ttl=3600, show_spinner=False)
def _generate(section_label: str, payload: str, kind: str) -> str:
    """Generate one report, DeepSeek first then Groq.

    Cached on (section, payload, kind) — the payload holds every value and
    variation, so the key changes exactly when the data does.
    """
    system = f"{_COMMON_RULES}\n\n{_STRUCTURES.get(kind, _STRUCTURES['social'])}"
    user = f"PLATEFORME / SECTION : {section_label}\n\nINDICATEURS :\n{payload}"

    for provider in (_try_deepseek, _try_groq):
        content = provider(system, user)
        if content:
            return content

    raise _ReportError("no provider returned a report")


# ─── Rendering ────────────────────────────────────────────────────────────────
def _card_html(body_html: str, dark: bool) -> str:
    if dark:
        bg      = "linear-gradient(135deg, rgba(232,66,10,0.10) 0%, rgba(232,66,10,0.02) 100%)"
        border  = "rgba(232,66,10,0.35)"
        text_c  = "#e4e4e7"
        muted_c = "rgba(255,255,255,0.40)"
    else:
        bg      = "linear-gradient(135deg, rgba(232,66,10,0.07) 0%, rgba(232,66,10,0.01) 100%)"
        border  = "rgba(232,66,10,0.28)"
        text_c  = "#1f2937"
        muted_c = "#9ca3af"

    return (
        f'<div style="background:{bg};border:1px solid {border};border-radius:14px;'
        f'padding:1.2rem 1.4rem;margin:0.4rem 0 1rem;">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.8rem;">'
        f'<div style="width:26px;height:26px;border-radius:50%;'
        f'background:linear-gradient(135deg,#E8420A,#C1320A);display:flex;'
        f'align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">🧠</div>'
        f'<span style="font-size:0.95rem;font-weight:700;color:#E8420A;'
        f'letter-spacing:0.02em;">Rapport d\'analyse</span></div>'
        f'<div style="font-size:0.88rem;line-height:1.75;color:{text_c};">{body_html}</div>'
        f'<div style="font-size:0.72rem;color:{muted_c};margin-top:1rem;font-style:italic;">'
        f'Les chiffres proviennent du dashboard ; l\'IA les interprète. Les causes '
        f'avancées sont des hypothèses déduites de la corrélation entre indicateurs — '
        f'à recouper avec votre connaissance métier (changements de créas, '
        f'opérations commerciales, saisonnalité).</div>'
        f'</div>'
    )


def render_ai_report(section_label: str, ctx: dict | None, *, key: str,
                     kind: str = "social", extra_notes: list[str] | None = None):
    """Render an on-demand analysis report for one platform.

    Shows a button; the report is generated only when asked for, then stays
    visible until the underlying numbers change — a period change brings the
    button back rather than leaving a stale report under new figures.

    Renders nothing when there is no data. A report is a bonus; it must never
    break the dashboard.

    Parameters
    ----------
    section_label : platform name given to the model as context.
    ctx           : the section's KPI dict, optionally carrying "_prev"
                    (previous-period values, same keys) and "_notes".
    key           : unique widget key (all views call this function).
    kind          : "ads", "social" or "web" — selects the report structure.
    extra_notes   : extra context lines appended to the payload.
    """
    if not ctx:
        return

    ctx = dict(ctx)
    notes = list(ctx.get(NOTES_KEY) or []) + list(extra_notes or [])
    if notes:
        ctx[NOTES_KEY] = notes

    payload = build_payload(ctx)
    if not payload:
        return

    state_key = f"ai_report_{key}"

    if st.session_state.get(state_key) != payload:
        if not st.button("🧠 Générer le rapport d'analyse", key=f"btn_{state_key}"):
            return
        st.session_state[state_key] = payload

    try:
        with st.spinner("Analyse des données en cours…"):
            report = _generate(section_label, payload, kind)
    except Exception:  # noqa: BLE001 - never let this break the page
        st.caption(
            "⚠️ Le rapport n'a pas pu être généré (limite du service IA ou "
            "indisponibilité). Réessayez dans un instant."
        )
        st.session_state.pop(state_key, None)
        return

    dark = st.session_state.get("theme", "dark") == "dark"
    st.markdown(_card_html(_md_to_html(report), dark), unsafe_allow_html=True)

    period = ctx.get("period", "")
    st.download_button(
        "📥 Télécharger le rapport",
        data=f"# {section_label}\n\n**Période :** {period}\n\n---\n\n{report}\n".encode("utf-8"),
        file_name=f"rapport_{key}_footland.md",
        mime="text/markdown",
        key=f"dl_{state_key}",
    )
