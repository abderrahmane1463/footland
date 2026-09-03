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

import streamlit as st

from components.chatbot import _md_to_html
from components.llm import complete

# Token budgets are per provider and deliberately different.
# DeepSeek needs headroom: v4-flash spent 3 153 completion tokens on a Boost
# report, so a 3 000 ceiling truncated it mid-sentence.
# Groq rejects that same ceiling outright (HTTP 413 Payload Too Large), and
# gpt-oss only used 1 247 tokens for a full report anyway — so it keeps 3 000.
DEEPSEEK_MAX_TOKENS = 8000
GROQ_MAX_TOKENS = 3000


# Keys carrying structure rather than a KPI value.
PREV_KEY = "_prev"
NOTES_KEY = "_notes"
SERIES_KEY = "_series"
_INTERNAL_KEYS = {PREV_KEY, NOTES_KEY, SERIES_KEY}


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
- Quand une section « ÉVOLUTION DANS LE TEMPS » est fournie, décris la FORME de la
  courbe (pics, creux, début / milieu / fin de période) — pas seulement le total.
  Exemple de ton attendu : « Le mois présente une évolution fluctuante avec
  plusieurs pics, mais une baisse globale de -3,1 %. »
- Quand une section « CONTEXTE MÉTIER » est fournie, sers-t'en en priorité pour
  expliquer les variations : elle contient ce que les chiffres ne disent pas
  (opérations commerciales, changements de budget, saisonnalité).
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


def _describe_series(label: str, series: list) -> str | None:
    """Reduce a daily series to the shape descriptors a written report needs.

    A total says reach rose 67 %; it cannot say the month peaked on 1 August
    and collapsed afterwards. The monthly PDF reports lean on exactly that
    ("plusieurs pics", "creux en milieu de période"), so the peak, the trough
    and the start/middle/end averages are computed here — in Python, because
    the model is not allowed to calculate anything.
    """
    points = [(p.get("date"), p.get("value") or 0)
              for p in (series or []) if p.get("date")]
    if len(points) < 3:
        return None

    points.sort(key=lambda x: str(x[0]))
    n = len(points)
    third = max(1, n // 3)
    segments = {
        "début":  points[:third],
        "milieu": points[third:2 * third],
        "fin":    points[2 * third:],
    }

    def _where(date) -> str:
        for name, seg in segments.items():
            if any(d == date for d, _ in seg):
                return name
        return "—"

    peak   = max(points, key=lambda x: x[1])
    trough = min(points, key=lambda x: x[1])
    averages = {name: sum(v for _, v in seg) / len(seg)
                for name, seg in segments.items() if seg}

    lines = [
        f"- {label} — évolution journalière sur {n} jours :",
        f"    · moyenne journalière : {_fmt(round(sum(v for _, v in points) / n))}",
        f"    · pic : {peak[0]} ({_fmt(peak[1])}) — en {_where(peak[0])} de période",
        f"    · creux : {trough[0]} ({_fmt(trough[1])}) — en {_where(trough[0])} de période",
        "    · moyennes par tiers : " + ", ".join(
            f"{name} {_fmt(round(v))}" for name, v in averages.items()),
    ]
    return "\n".join(lines)


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

    # Daily curves — what lets the report describe the shape of the month
    # ("pic en fin de période") rather than only its total.
    shapes = [s for label, series in (ctx.get(SERIES_KEY) or {}).items()
              if (s := _describe_series(label, series))]
    if shapes:
        payload += "\n\nÉVOLUTION DANS LE TEMPS :\n" + "\n".join(shapes)

    if notes:
        payload += "\n\nCONTEXTE MÉTIER :\n" + "\n".join(f"- {n}" for n in notes)
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


@st.cache_data(ttl=3600, show_spinner=False)
def _generate(section_label: str, payload: str, kind: str) -> str:
    """Generate one report, DeepSeek first then Groq (see components/llm.py).

    Cached on (section, payload, kind) — the payload holds every value and
    variation, so the key changes exactly when the data does.
    """
    system = f"{_COMMON_RULES}\n\n{_STRUCTURES.get(kind, _STRUCTURES['social'])}"
    user = f"PLATEFORME / SECTION : {section_label}\n\nINDICATEURS :\n{payload}"

    content = complete(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}],
        deepseek_max_tokens=DEEPSEEK_MAX_TOKENS,
        groq_max_tokens=GROQ_MAX_TOKENS,
        temperature=0.4,
    )
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

    Admin only. The report is a drafting tool: the agency writes the context,
    reviews the output and decides what reaches the client. It also spends
    DeepSeek credit, which should not be triggerable from a client account.
    """
    if st.session_state.get("user", {}).get("role") != "admin":
        return
    if not ctx:
        return

    ctx = dict(ctx)
    notes = list(ctx.get(NOTES_KEY) or []) + list(extra_notes or [])

    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

    # The single biggest quality lever. Seasonality, promotions and budget
    # decisions are invisible in the API — the monthly PDF's best line
    # ("un effet Ramadan qui avait boosté mars") could never be derived from
    # the numbers. Typing it here is what turns a summary into commentary.
    with st.expander("📝 Contexte du mois (optionnel) — améliore nettement l'analyse"):
        st.caption(
            "Ce que les chiffres ne disent pas : opération commerciale, changement "
            "de budget, saisonnalité (Ramadan, soldes), refonte des créas…"
        )
        user_note = st.text_area(
            "Contexte",
            key=f"note_{key}",
            label_visibility="collapsed",
            placeholder="Ex : Soldes été lancées en semaine 30 · budget Ads doublé · "
                        "mars était porté par le Ramadan",
            height=80,
        )
    if user_note and user_note.strip():
        notes.append(f"Éléments fournis par l'agence : {user_note.strip()}")

    if notes:
        ctx[NOTES_KEY] = notes

    payload = build_payload(ctx)
    if not payload:
        return

    state_key = f"ai_report_{key}"

    # The context text is part of the payload, so editing it invalidates the
    # stored report and offers the button again — the analysis can never sit
    # under context it wasn't written from.
    if st.session_state.get(state_key) != payload:
        if not st.button("🧠 Générer le rapport d'analyse",
                         key=f"btn_{state_key}", type="tertiary"):
            return
        st.session_state[state_key] = payload

    try:
        # The wait is genuinely ~30 s (the model reasons before writing), so the
        # duration is stated: an unexplained spinner that long reads as a freeze.
        with st.spinner("🧠 Analyse des données en cours — environ 30 secondes…"):
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
