"""
components/ai_insights.py — Auto-generated AI commentary for dashboard sections.

Renders a short, client-facing analysis of the KPIs currently on screen.
Reuses the Groq client, API key resolution and markdown renderer from
components/chatbot.py so both features stay on the same model configuration.

The generation is cached on the data payload itself, so a given set of numbers
costs exactly one API call no matter how many times Streamlit reruns the script.
"""

import streamlit as st

from components.chatbot import GROQ_MODELS, _get_api_key, _md_to_html

try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq may not be installed yet
    Groq = None


SYSTEM_PROMPT = """Tu es analyste social media & publicité digitale pour Footland,
un détaillant d'articles de sport en Algérie. Tu rédiges de courtes analyses
destinées au client, à afficher directement dans son dashboard.

Règles impératives :
- Réponds en français, ton professionnel, direct, sans jargon inutile.
- Appuie-toi UNIQUEMENT sur les chiffres fournis. N'invente jamais une donnée.
- NE CALCULE AUCUNE nouvelle métrique (pas de ratio, division, pourcentage ou
  moyenne que tu aurais toi-même calculé). Reprends exclusivement les valeurs
  telles qu'elles te sont données, avec leur nom et leur unité.
- Ne commente pas une métrique absente ou nulle : ignore-la simplement.
- Cite les chiffres qui justifient chaque affirmation.
- N'invente aucune comparaison avec une période précédente si elle n'est pas fournie.

Format de réponse EXACT (rien avant, rien après) :
**Ce qu'il faut retenir**
- (2 à 3 puces factuelles, chiffres à l'appui)

**Recommandations**
- (1 à 2 actions concrètes et applicables)

Maximum 130 mots au total. Pas d'introduction, pas de conclusion, pas de titre."""


# Human-readable labels (with units) for every ctx_* key across the four views.
# The model is forbidden from computing anything, so it can only reproduce the
# units it is handed — without this map it writes "CTR est de 1.48" instead of
# "CTR de 1,48 %", and "284.5" instead of "284,5 €".
_KPI_LABELS = {
    # shared
    "period":               "Période analysée",
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
    # Google Analytics
    "active_users":         "Utilisateurs actifs",
    "new_users":            "Nouveaux utilisateurs",
    "sessions":             "Sessions",
    "engaged_sessions":     "Sessions engagées",
}


def _format_payload(ctx: dict) -> str:
    """Turn a ctx_* dict into labelled 'Label : value' lines carrying units."""
    lines = []
    for key, value in ctx.items():
        if value in (None, ""):
            continue
        lines.append(f"- {_KPI_LABELS.get(key, key)} : {value}")
    return "\n".join(lines)


class _InsightError(RuntimeError):
    """Raised when no model could produce an analysis.

    Raising (instead of returning an empty string) keeps failures out of the
    Streamlit cache, so a transient API problem retries on the next rerun
    instead of being frozen in for the whole TTL.
    """


@st.cache_data(ttl=3600, show_spinner=False)
def _generate(section_label: str, payload: str) -> str:
    """Generate the analysis for one section.

    Cached on (section_label, payload) — the payload holds the period and every
    KPI value, so the cache key changes exactly when the numbers do.
    """
    api_key = _get_api_key()
    if not api_key or Groq is None:
        raise _InsightError("Groq unavailable")

    client = Groq(api_key=api_key)
    user_msg = (
        f"Section du dashboard : {section_label}\n\n"
        f"Données de la période :\n{payload}"
    )

    for model in GROQ_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            content = (response.choices[0].message.content or "").strip()
            # Reasoning models can spend the whole budget thinking and return
            # an empty message — fall through to the next model in that case.
            if content:
                return content
        except Exception as exc:  # noqa: BLE001 - any failure ⇒ try next model
            print(f"DEBUG ai_insights: {model} failed: {exc}")
            continue

    raise _InsightError("no model returned an analysis")


def _card_html(body_html: str, dark: bool) -> str:
    """Wrap the analysis in a branded, theme-aware card."""
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
        f'padding:1.1rem 1.3rem;margin:0.4rem 0 1.4rem;">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.7rem;">'
        f'<div style="width:26px;height:26px;border-radius:50%;'
        f'background:linear-gradient(135deg,#E8420A,#C1320A);display:flex;'
        f'align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">🧠</div>'
        f'<span style="font-size:0.95rem;font-weight:700;color:#E8420A;'
        f'letter-spacing:0.02em;">Analyse automatique</span></div>'
        f'<div style="font-size:0.88rem;line-height:1.75;color:{text_c};">{body_html}</div>'
        f'<div style="font-size:0.72rem;color:{muted_c};margin-top:0.8rem;'
        f'font-style:italic;">Généré par IA à partir des données de la période '
        f'affichée — à recouper avec votre analyse métier.</div>'
        f'</div>'
    )


def render_ai_insights(section_label: str, ctx: dict | None):
    """Render an auto-generated analysis block for a dashboard section.

    Silently renders nothing when there is no data or the model is unavailable —
    an analysis block is a bonus, it must never break the dashboard.

    Parameters
    ----------
    section_label : human-readable section name, passed to the model as context
                    (e.g. "Boost — campagnes payantes Meta").
    ctx           : the section's KPI dict (the same ctx_* payload the chatbot
                    uses). Falsy ⇒ nothing is rendered.
    """
    if not ctx:
        return

    payload = _format_payload(ctx)
    if not payload:
        return

    try:
        with st.spinner("Analyse des données en cours…"):
            analysis = _generate(section_label, payload)
    except Exception:  # noqa: BLE001 - never let this break the page
        return

    dark = st.session_state.get("theme", "dark") == "dark"
    st.markdown(_card_html(_md_to_html(analysis), dark), unsafe_allow_html=True)
