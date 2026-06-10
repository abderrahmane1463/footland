"""
components/chatbot.py — AI Assistant (Groq) for the Footland Analytics dashboard.

Floating chat panel that can answer questions about the data currently
displayed on screen (Facebook, Instagram, Boost, Google Analytics) using
Groq's free Llama models.
"""

import os
import re

import streamlit as st
from dotenv import load_dotenv

try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq may not be installed yet
    Groq = None

load_dotenv()


# ─── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es l'assistant IA intégré au dashboard "Footland Analytics" — un
tableau de bord Streamlit qui suit la performance organique et publicitaire des
réseaux sociaux de Footland (boutique d'articles de sport / football).

## Structure du dashboard

Le dashboard est organisé en plusieurs sections accessibles depuis la barre latérale :

- **🔵 Facebook** — 5 onglets : Audience, Visibility, Engagement, Top Content, Community.
  KPIs principaux : Followers, Nouveaux followers, Désabonnements, Taux d'engagement,
  Spectateurs (reach), Impressions, Content Interactions, Publications,
  Total interactions (réactions + commentaires + partages), Réactions, Commentaires, Partages.

- **📸 Instagram** — 2 onglets : Visibility, Engagement.
  KPIs principaux : Followers, Publications, Taux d'engagement, Couvertures (reach),
  Vues (toutes les publications : posts + reels + stories), Enregistrements (saves),
  Total interactions, Réactions, Commentaires, Partages.

- **🚀 Boost** — Campagnes publicitaires payantes (Meta Marketing API), avec 6 onglets :
  Global, Conversion, Par Objectif, Top #3 Campagnes, Tableau Ads, Démographie & Géo.
  KPIs principaux : Total des campagnes, Clics sur le lien, Comptes touchés (reach),
  Impressions, Coût par clic (CPC), CTR, Montant dépensé, Fréquence.

- **📊 Google Analytics 4** — Comportement des visiteurs sur footland.dz, avec 4 onglets :
  Vue d'ensemble (+ sources de trafic), E-commerce (parcours d'achat + top articles),
  Événements, Audience (géographie + appareils).
  KPIs principaux : Utilisateurs actifs, Nouveaux utilisateurs, Sessions, Sessions engagées.

- **📖 Documentation** — Guide expliquant chaque KPI, ce qu'il mesure et comment il est calculé.

## Sources de données

- Toutes les données Facebook et Instagram proviennent de la **Meta Graph API v19.0**,
  uniquement des données **organiques** (page Footland + compte Instagram lié).
- Les données Boost proviennent de la **Meta Marketing API** (campagnes publicitaires).
- Les données Google Analytics proviennent de l'**API GA4** (propriété footland.dz).
- Les données sont mises en cache dans Supabase (cache permanent, rafraîchi via le
  bouton "🔄 Refresh Data" dans la barre latérale).

## Limitations importantes à connaître

- **Organic-only strict** : un compte publicitaire est bloqué (blocklisté) — aucune donnée
  publicitaire Facebook/Instagram organique ne provient de cette source.
- Sur Instagram, la "Couverture (reach)" via `metric_type=total_value` n'est disponible
  que pour des périodes de 30 jours ou moins ; au-delà, elle affiche "—".
- Le KPI "Vues" Instagram agrège posts + reels + stories en un seul appel API
  (`/{ig-user-id}/insights?metric=views&period=day&metric_type=total_value`).
- Sur Facebook, "Spectateurs" (reach exact via `metric_type=total_value`) n'est
  disponible que pour des fenêtres de 1, 7, 28-31 jours ; sinon affiche "—".
- Le "Taux d'engagement" est calculé comme : interactions totales ÷ portée (reach) × 100,
  uniquement quand la portée exacte est disponible.

## Ton rôle

Réponds aux questions de l'utilisateur sur les statistiques affichées dans le
dashboard, en français, de manière concise et claire. Utilise les données
contextuelles fournies ci-dessous (issues de la session en cours) quand elles sont
disponibles. Si une donnée n'est pas disponible dans le contexte, dis-le clairement
plutôt que d'inventer un chiffre. Tu peux aussi expliquer comment un KPI est calculé
ou d'où il provient (cf. limitations ci-dessus).
"""

GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


# ─── API key resolution ──────────────────────────────────────────────────────
def _get_api_key():
    """Read GROQ_API_KEY from st.secrets first, then environment variables."""
    try:
        key = st.secrets["GROQ_API_KEY"]
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY")


# ─── Live data context ───────────────────────────────────────────────────────
def _build_data_context() -> str:
    """Build a text summary of the data currently shown on screen, from
    st.session_state context dicts (ctx_instagram, ctx_facebook, ctx_boost, ctx_ga4)."""
    sections = []

    fb = st.session_state.get("ctx_facebook")
    if fb:
        period = fb.get("period", "")
        rows = "\n".join(f"- {k}: {v}" for k, v in fb.items() if k != "period")
        sections.append(f"### Facebook (période : {period})\n{rows}")

    ig = st.session_state.get("ctx_instagram")
    if ig:
        period = ig.get("period", "")
        rows = "\n".join(f"- {k}: {v}" for k, v in ig.items() if k != "period")
        sections.append(f"### Instagram (période : {period})\n{rows}")

    boost = st.session_state.get("ctx_boost")
    if boost:
        period = boost.get("period", "")
        rows = "\n".join(f"- {k}: {v}" for k, v in boost.items() if k != "period")
        sections.append(f"### Boost (période : {period})\n{rows}")

    ga4 = st.session_state.get("ctx_ga4")
    if ga4:
        period = ga4.get("period", "")
        rows = "\n".join(f"- {k}: {v}" for k, v in ga4.items() if k != "period")
        sections.append(f"### Google Analytics (période : {period})\n{rows}")

    if not sections:
        return ""

    return (
        "\n\n## Données actuellement affichées dans le dashboard\n\n"
        + "\n\n".join(sections)
    )


# ─── Groq chat completion ────────────────────────────────────────────────────
def _get_groq_response(history):
    """Call Groq's chat completion API, falling back to a second model on rate limits."""
    api_key = _get_api_key()
    if not api_key:
        return "⚠️ Clé API Groq introuvable. Configurez GROQ_API_KEY dans .env ou st.secrets."

    if Groq is None:
        return "⚠️ Le package 'groq' n'est pas installé. Ajoutez 'groq' à requirements.txt."

    client = Groq(api_key=api_key)

    messages = [{"role": "system", "content": SYSTEM_PROMPT + _build_data_context()}]
    for msg in history:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    for model in GROQ_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                continue
            return f"⚠️ Erreur : {err}"

    return "⚠️ Les deux modèles ont atteint leur limite quotidienne. Réessayez dans quelques heures."


# ─── Markdown → HTML helpers ─────────────────────────────────────────────────
def _md_to_html(text: str) -> str:
    """Very small markdown subset → HTML for chat bubbles."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(r"^- (.+)$", r"• \1", text, flags=re.MULTILINE)
    text = text.replace("\n", "<br>")
    return text


def _build_msgs_html(history, dark: bool = True) -> str:
    """Render the chat history as HTML chat bubbles."""
    if not history:
        _empty_c = "rgba(255,255,255,0.35)" if dark else "#9ca3af"
        return (
            f'<div style="text-align:center;color:{_empty_c};font-size:0.85rem;'
            f'padding:2rem 1rem;line-height:1.5;">'
            f'👋 Bonjour ! Je suis l\'assistant IA Footland.<br>'
            f'Posez-moi une question sur les statistiques affichées.</div>'
        )

    bubbles = []
    for msg in history:
        is_user = msg.get("role") == "user"
        content = _md_to_html(msg.get("content", ""))
        if is_user:
            bg, color, align, radius = "#E8420A", "#ffffff", "flex-end", "14px 14px 2px 14px"
        else:
            bg = "rgba(255,255,255,0.08)" if dark else "#f1f5f9"
            color = "#ffffff" if dark else "#111827"
            align, radius = "flex-start", "14px 14px 14px 2px"
        bubbles.append(
            f'<div style="display:flex;justify-content:{align};margin-bottom:0.5rem;">'
            f'<div style="background:{bg};color:{color};padding:0.5rem 0.8rem;'
            f'border-radius:{radius};max-width:85%;font-size:0.85rem;'
            f'line-height:1.45;word-wrap:break-word;">{content}</div>'
            f'</div>'
        )
    return "".join(bubbles)


# ─── Floating chat panel ──────────────────────────────────────────────────────
def render_chatbot():
    """Render the floating AI assistant panel (only call when chat_open is True)."""
    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg       = "#161616" if _dark else "#ffffff"
    _border   = "#262626" if _dark else "#e5e7eb"
    _input_bg = "rgba(255,255,255,0.06)" if _dark else "#f3f4f6"
    _text_c   = "#ffffff" if _dark else "#111827"

    st.markdown(
        f"""
<style>
.st-key-fl_chatbot_container {{
    position: fixed !important;
    bottom: 96px !important;
    right: 16px !important;
    top: auto !important;
    left: auto !important;
    width: 360px !important;
    max-width: calc(100vw - 24px) !important;
    height: 520px !important;
    max-height: 520px !important;
    min-height: 0 !important;
    z-index: 9999 !important;
    background: {_bg} !important;
    border: 1px solid {_border} !important;
    border-radius: 16px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45) !important;
    overflow: hidden !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 0 !important;
}}

/* Header row (title + close button) — only the row containing .fl-chat-title */
.st-key-fl_chatbot_container [data-testid="stHorizontalBlock"]:has(.fl-chat-title) {{
    flex: 0 0 auto !important;
    background: linear-gradient(90deg, #E8420A, #C1320A);
    align-items: center;
    padding: 0.55rem 0.8rem;
}}
.st-key-fl_chatbot_container [data-testid="stHorizontalBlock"]:has(.fl-chat-title) [data-testid="stMarkdownContainer"] p {{
    color: #ffffff !important;
    font-weight: 700;
    font-size: 0.95rem;
    margin: 0;
}}
.st-key-fl_chat_close button {{
    background: transparent !important;
    border: none !important;
    color: #ffffff !important;
    font-size: 1.1rem !important;
    line-height: 1 !important;
    padding: 0.2rem 0.5rem !important;
    min-height: unset !important;
    box-shadow: none !important;
    float: right;
}}
.st-key-fl_chat_close button:hover {{
    background: rgba(255,255,255,0.18) !important;
}}

/* Scrollable messages area — middle, takes remaining space */
.st-key-fl_chatbot_container [data-testid="stElementContainer"]:has(.fl-chat-messages) {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    max-height: 100% !important;
    height: 0 !important;
    overflow: hidden !important;
}}
.st-key-fl_chatbot_container [data-testid="stElementContainer"]:has(.fl-chat-messages) [data-testid="stMarkdownContainer"] {{
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
}}
.fl-chat-messages {{
    display: block !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow-y: auto !important;
    padding: 0.7rem;
    scrollbar-width: thin;
    scrollbar-color: #E8420A transparent;
}}
.fl-chat-messages::-webkit-scrollbar {{
    width: 6px;
}}
.fl-chat-messages::-webkit-scrollbar-track {{
    background: transparent;
}}
.fl-chat-messages::-webkit-scrollbar-thumb {{
    background-color: #E8420A;
    border-radius: 3px;
}}
.fl-chat-messages::-webkit-scrollbar-thumb:hover {{
    background-color: #FF6B35;
}}

/* Input row (form) — pinned at the bottom of the panel */
.st-key-fl_chatbot_container [data-testid="stForm"] {{
    flex: 0 0 auto !important;
    border: none;
    border-top: 1px solid {_border};
    padding: 0.5rem 0.6rem;
    background: transparent;
    margin: 0 !important;
}}
.st-key-fl_chatbot_container [data-testid="stForm"] [data-testid="stTextInput"] input {{
    background: {_input_bg} !important;
    color: {_text_c} !important;
    border-radius: 20px !important;
    border: 1px solid {_border} !important;
}}
.st-key-fl_chatbot_container [data-testid="stForm"] [data-testid="baseButton-secondaryFormSubmit"],
.st-key-fl_chatbot_container [data-testid="stForm"] button[kind="secondaryFormSubmit"] {{
    border-radius: 50% !important;
    width: 2.4rem !important;
    height: 2.4rem !important;
    padding: 0 !important;
}}
.st-key-fl_chatbot_container [data-testid="InputInstructions"] {{
    display: none !important;
}}

@media (max-width: 480px) {{
    .st-key-fl_chatbot_container {{
        width: calc(100vw - 16px);
        right: 8px;
        bottom: 84px;
        height: 70vh;
    }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    with st.container(key="fl_chatbot_container"):
        hcol1, hcol2 = st.columns([6, 1])
        with hcol1:
            st.markdown('<span class="fl-chat-title">🤖 <b>Assistant IA Footland</b></span>', unsafe_allow_html=True)
        with hcol2:
            if st.button("✕", key="fl_chat_close"):
                st.session_state.chat_open = False
                st.rerun()

        msgs_html = _build_msgs_html(st.session_state.get("chat_history", []), _dark)
        st.markdown(f'<div class="fl-chat-messages" id="fl-chat-messages">{msgs_html}</div>', unsafe_allow_html=True)

        with st.form("fl_chat_form", clear_on_submit=True, border=False):
            fcol1, fcol2 = st.columns([6, 1])
            with fcol1:
                user_msg = st.text_input(
                    "message", placeholder="Posez votre question...",
                    label_visibility="collapsed", key="fl_chat_text",
                )
            with fcol2:
                sent = st.form_submit_button("➤")

    # Auto-scroll the messages area to the bottom after each render
    st.components.v1.html(
        """
        <script>
        const doc = window.parent.document;
        const el = doc.getElementById("fl-chat-messages");
        if (el) { el.scrollTop = el.scrollHeight; }
        </script>
        """,
        height=0,
    )

    if sent and user_msg and user_msg.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_msg.strip()})
        with st.spinner("L'assistant réfléchit..."):
            reply = _get_groq_response(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()
