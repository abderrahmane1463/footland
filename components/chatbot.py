"""
components/chatbot.py — AI Assistant (Groq) for the Footland Analytics dashboard.

Floating chat panel that can answer questions about the data currently
displayed on screen (Facebook, Instagram, Boost, Google Analytics) using
Groq's free hosted models.
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

# Primary model, then a smaller/faster fallback used on rate limits.
# The previous llama-3.x models were decommissioned by Groq (404 model_not_found).
GROQ_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]


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
            content = (response.choices[0].message.content or "").strip()
            # Reasoning models spend part of the budget thinking; if the whole
            # budget went to reasoning, content comes back empty — fall through
            # to the next model rather than showing an empty bubble.
            if content:
                return content
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err.lower():
                continue
            return f"⚠️ Erreur : {err}"

    return ("⚠️ Aucune réponse n'a pu être générée (limite quotidienne atteinte "
            "ou réponse vide). Réessayez dans quelques instants.")


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
            f'<div style="display:flex;gap:9px;align-items:flex-start;">'
            f'<div style="width:30px;height:30px;border-radius:50%;'
            f'background:linear-gradient(135deg,#E8420A,#C1320A);'
            f'display:flex;align-items:center;justify-content:center;'
            f'flex-shrink:0;font-size:15px;">🤖</div>'
            f'<div style="background:{"rgba(255,255,255,0.08)" if dark else "#f1f5f9"};'
            f'color:{_empty_c};padding:0.6rem 0.8rem;border-radius:4px 16px 16px 16px;'
            f'font-size:0.85rem;line-height:1.6;max-width:86%;">'
            f'👋 <strong>Bonjour !</strong> Je suis l\'assistant IA Footland.<br>'
            f'Posez-moi une question sur les statistiques affichées.</div>'
            f'</div>'
        )

    bot_bg = "rgba(255,255,255,0.08)" if dark else "#f1f5f9"
    bot_tc = "#ffffff" if dark else "#111827"

    bubbles = []
    for msg in history:
        is_user = msg.get("role") == "user"
        content = _md_to_html(msg.get("content", ""))
        if is_user:
            bubbles.append(
                f'<div style="display:flex;gap:9px;align-items:flex-start;'
                f'justify-content:flex-end;margin-bottom:0.6rem;">'
                f'<div style="background:linear-gradient(135deg,#E8420A,#C1320A);color:#fff;'
                f'padding:0.6rem 0.8rem;border-radius:16px 4px 16px 16px;'
                f'font-size:0.85rem;line-height:1.6;max-width:86%;word-wrap:break-word;">{content}</div>'
                f'<div style="width:30px;height:30px;border-radius:50%;background:#444;flex-shrink:0;'
                f'display:flex;align-items:center;justify-content:center;font-size:15px;">👤</div>'
                f'</div>'
            )
        else:
            bubbles.append(
                f'<div style="display:flex;gap:9px;align-items:flex-start;margin-bottom:0.6rem;">'
                f'<div style="width:30px;height:30px;border-radius:50%;'
                f'background:linear-gradient(135deg,#E8420A,#C1320A);'
                f'display:flex;align-items:center;justify-content:center;'
                f'flex-shrink:0;font-size:15px;">🤖</div>'
                f'<div style="background:{bot_bg};color:{bot_tc};padding:0.6rem 0.8rem;'
                f'border-radius:4px 16px 16px 16px;font-size:0.85rem;line-height:1.6;'
                f'max-width:86%;word-wrap:break-word;">{content}</div>'
                f'</div>'
            )
    return "".join(bubbles)


# ─── Floating chat panel ──────────────────────────────────────────────────────
def render_chatbot():
    """Render the floating AI assistant panel (only call when chat_open is True)."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    _dark = st.session_state.get("theme", "dark") == "dark"
    _bg       = "#161616" if _dark else "#ffffff"
    _border   = "#262626" if _dark else "#e5e7eb"
    _input_bg = "rgba(255,255,255,0.06)" if _dark else "#f3f4f6"
    _text_c   = "#ffffff" if _dark else "#111827"
    _ph_c     = "rgba(255,255,255,0.35)" if _dark else "#9ca3af"

    msgs_html = _build_msgs_html(st.session_state.chat_history, _dark)

    st.markdown(
        f"""
<style>
#fl-chat-panel {{
    position: fixed;
    bottom: 76px;
    right: 16px;
    width: 360px;
    max-width: calc(100vw - 24px);
    height: 480px;
    max-height: 70vh;
    background: {_bg};
    border: 1px solid {_border};
    border-bottom: none;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -4px 32px rgba(0,0,0,0.35);
    z-index: 9000;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: flChatIn .25s cubic-bezier(.34,1.56,.64,1) both;
}}
@keyframes flChatIn {{
    from {{ opacity: 0; transform: translateY(18px) scale(.96); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
}}
#fl-chat-hdr {{
    background: linear-gradient(90deg, #E8420A, #C1320A);
    padding: 0.6rem 0.8rem;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}}
#fl-chat-hdr span.fl-chat-title {{
    color: #ffffff;
    font-weight: 700;
    font-size: 0.95rem;
}}

/* Scrollable messages area */
#fl-chat-messages {{
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    padding: 0.7rem;
    scrollbar-width: thin;
    scrollbar-color: #E8420A transparent;
}}
#fl-chat-messages::-webkit-scrollbar {{
    width: 6px;
}}
#fl-chat-messages::-webkit-scrollbar-track {{
    background: transparent;
}}
#fl-chat-messages::-webkit-scrollbar-thumb {{
    background-color: #E8420A;
    border-radius: 3px;
}}
#fl-chat-messages::-webkit-scrollbar-thumb:hover {{
    background-color: #FF6B35;
}}

/* Close button overlay, pinned to the panel header */
.st-key-fl_chat_close_wrap {{
    position: fixed !important;
    bottom: calc(76px + 480px - 42px) !important;
    right: 22px !important;
    z-index: 9002 !important;
    width: 28px !important;
    height: 28px !important;
}}
.st-key-fl_chat_close_wrap button {{
    background: rgba(255,255,255,0.18) !important;
    border: none !important;
    border-radius: 50% !important;
    color: #ffffff !important;
    width: 28px !important;
    height: 28px !important;
    padding: 0 !important;
    min-height: unset !important;
    font-size: 0.85rem !important;
    line-height: 1 !important;
    box-shadow: none !important;
}}
.st-key-fl_chat_close_wrap button:hover {{
    background: rgba(255,255,255,0.32) !important;
}}

/* Make the global bottom bar transparent / click-through except the input itself */
[data-testid="stBottom"] {{
    background: transparent !important;
    pointer-events: none !important;
}}
[data-testid="stBottom"] * {{
    pointer-events: auto !important;
}}
[data-testid="stBottomBlockContainer"] {{
    background: transparent !important;
}}

/* Chat input pinned directly under the floating panel */
[data-testid="stChatInput"] {{
    position: fixed !important;
    bottom: 0 !important;
    right: 16px !important;
    left: auto !important;
    width: 360px !important;
    max-width: calc(100vw - 24px) !important;
    z-index: 9001 !important;
    background: {_bg} !important;
    border: 1px solid {_border} !important;
    border-radius: 0 0 16px 16px !important;
    padding: 0.5rem 0.6rem !important;
    margin: 0 !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.45) !important;
}}
[data-testid="stChatInput"] textarea {{
    background: {_input_bg} !important;
    color: {_text_c} !important;
    border-radius: 12px !important;
    border: 1px solid {_border} !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{
    color: {_ph_c} !important;
}}
[data-testid="stChatInput"] button {{
    background: linear-gradient(135deg, #E8420A, #C1320A) !important;
    border-radius: 10px !important;
    border: none !important;
}}

@media (max-width: 480px) {{
    #fl-chat-panel,
    [data-testid="stChatInput"] {{
        width: calc(100vw - 16px) !important;
        right: 8px !important;
    }}
    #fl-chat-panel {{
        bottom: 124px;
        height: 60vh;
        max-height: 60vh;
    }}
    .st-key-fl_chat_close_wrap {{
        bottom: calc(124px + 60vh - 42px) !important;
        right: 14px !important;
    }}
}}
</style>

<div id="fl-chat-panel">
  <div id="fl-chat-hdr">
    <span style="font-size:1.1rem;">🤖</span>
    <span class="fl-chat-title">Assistant IA Footland</span>
  </div>
  <div id="fl-chat-messages">{msgs_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.container(key="fl_chat_close_wrap"):
        if st.button("✕", key="fl_chat_close"):
            st.session_state.chat_open = False
            st.rerun()

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

    prompt = st.chat_input("Posez votre question...", key="fl_chat_input")
    if prompt and prompt.strip():
        st.session_state.chat_history.append({"role": "user", "content": prompt.strip()})
        with st.spinner("L'assistant réfléchit..."):
            reply = _get_groq_response(st.session_state.chat_history)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()
