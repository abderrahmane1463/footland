"""
views/documentation.py — Guide du dashboard Footland.
"""

import streamlit as st


def _doc_css(dark: bool = True) -> str:
    """Theme-aware CSS for the documentation tab, matching the rest of the dashboard."""
    if dark:
        hero_bg     = "linear-gradient(135deg, #161616 0%, #1a0f0a 100%)"
        border      = "#262626"
        muted       = "#a1a1aa"
        label       = "#71717a"
        text        = "#e4e4e7"
        row_border  = "#1a1a1a"
        row_hover   = "#1a1a1a"
        endpoint_bg = "#1e1e1e"
    else:
        hero_bg     = "linear-gradient(135deg, #ffffff 0%, #fff5f0 100%)"
        border      = "#e5e7eb"
        muted       = "#6b7280"
        label       = "#6b7280"
        text        = "#111827"
        row_border  = "#f1f5f9"
        row_hover   = "#f9fafb"
        endpoint_bg = "#f3f4f6"

    return f"""
<style>
.doc-hero {{
    background: {hero_bg};
    border: 1px solid {border};
    border-radius: 20px;
    padding: 40px 48px;
    margin-bottom: 32px;
}}
.doc-hero h1 {{
    font-size: 32px;
    font-weight: 800;
    background: linear-gradient(90deg, #E8420A, #FF6B35);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}}
.doc-hero p {{ color: {muted} !important; font-size: 15px; }}
.doc-section-title {{
    font-size: 20px;
    font-weight: 700;
    color: #E8420A !important;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid {border};
}}
.kpi-table {{ width: 100%; border-collapse: collapse; }}
.kpi-table th {{
    text-align: left;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 600;
    color: {label} !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid {border};
}}
.kpi-table td {{
    padding: 10px 14px;
    font-size: 14px;
    color: {text} !important;
    border-bottom: 1px solid {row_border};
    vertical-align: top;
}}
.kpi-table tr:last-child td {{ border-bottom: none; }}
.kpi-table tr:hover td {{ background: {row_hover}; }}
.kpi-name {{ font-weight: 600; white-space: nowrap; }}
.kpi-desc {{ color: {muted} !important; }}
.endpoint {{
    font-family: monospace;
    font-size: 12px;
    background: {endpoint_bg};
    color: #E8420A !important;
    padding: 2px 6px;
    border-radius: 4px;
    white-space: nowrap;
}}
</style>
"""


def render_documentation():
    _is_admin = st.session_state.get("user", {}).get("role") == "admin"
    _dark = st.session_state.get("theme", "dark") == "dark"

    # Hide Endpoint column for viewers via CSS
    if not _is_admin:
        st.markdown("""
<style>
.kpi-table th:nth-child(3),
.kpi-table td:nth-child(3) { display: none !important; }
</style>
""", unsafe_allow_html=True)

    st.markdown(_doc_css(_dark), unsafe_allow_html=True)

    st.markdown("""
<div class="doc-hero">
  <h1>📖 Guide du Dashboard</h1>
  <p>Ce guide explique chaque indicateur (KPI) affiché dans le dashboard Footland — ce qu'il mesure et comment il est calculé.</p>
</div>
""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🔵 **Facebook** — Audience, Engagement, Visibilité, Publications, Communauté")
    with col2:
        st.info("📸 **Instagram** — Visibilité, Engagement, Publications")
    with col3:
        st.info("🚀 **Boost** — Campagnes payantes, Conversions, Par Objectif, Top #3, Rapport (Rapport Hebdomadaire Sales · Rapport Hebdomadaire Notoriété & Engagement), Drill-down Adset/Ad, Démographie, Géographie")

    col4, col5 = st.columns(2)
    with col4:
        st.info("📊 **Google Analytics** — Vue d'ensemble + Sources de trafic, E-commerce (Parcours d'achat + Top articles), Événements, Audience (Géographie + Appareils)")
    with col5:
        st.info("🤖 **Intelligence Artificielle** — Chatbot flottant propulsé par DeepSeek, répondant aux questions sur les données affichées")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Facebook ──────────────────────────────────────────────────────────────
    st.markdown('<div class="doc-section-title">🔵 Facebook</div>', unsafe_allow_html=True)

    t1, t2, t3, t4, t5, t6 = st.tabs(["Vue d'ensemble", "👥 Audience", "📡 Visibilité", "💬 Engagement", "🏆 Top Contenu", "🤝 Communauté"])

    with t1:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">👥 Followers</td><td class="kpi-desc">Nombre total d'abonnés à la fin de la période.</td><td><span class="endpoint">/{page_id}?fields=fan_count</span></td></tr>
  <tr><td class="kpi-name">➕ Nouveaux followers</td><td class="kpi-desc">Nouveaux abonnements pendant la période.</td><td><span class="endpoint">/{page_id}/insights?metric=page_daily_follows</span></td></tr>
  <tr><td class="kpi-name">➖ Désabonnements</td><td class="kpi-desc">Personnes ayant arrêté de suivre la page.</td><td><span class="endpoint">/{page_id}/insights?metric=page_daily_unfollows</span></td></tr>
  <tr><td class="kpi-name">📊 Taux d'engagement</td><td class="kpi-desc">Interactions totales ÷ portée × 100.</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">👁️ Spectateurs (Reach)</td><td class="kpi-desc">Comptes uniques ayant vu un contenu de la page.</td><td><span class="endpoint">/{page_id}/insights?metric=page_impressions_unique</span></td></tr>
  <tr><td class="kpi-name">📢 Impressions</td><td class="kpi-desc">Nombre total d'affichages (doublons inclus).</td><td><span class="endpoint">/{page_id}/insights?metric=page_impressions</span></td></tr>
  <tr><td class="kpi-name">🤝 Content Interactions</td><td class="kpi-desc">Réactions, commentaires, partages, clics sur les publications.</td><td><span class="endpoint">/{page_id}/insights?metric=page_post_engagements</span></td></tr>
  <tr><td class="kpi-name">📝 Publications</td><td class="kpi-desc">Nombre de posts publiés sur la période.</td><td><span class="endpoint">/{page_id}/posts?fields=id,…</span></td></tr>
  <tr><td class="kpi-name">🔥 Total interactions (posts)</td><td class="kpi-desc">Somme réactions + commentaires + partages de tous les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=reactions,comments,shares</span></td></tr>
  <tr><td class="kpi-name">❤️ Réactions</td><td class="kpi-desc">Total des réactions sur les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=reactions.summary(true)</span></td></tr>
  <tr><td class="kpi-name">💬 Commentaires</td><td class="kpi-desc">Total des commentaires sur les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=comments.summary(true)</span></td></tr>
  <tr><td class="kpi-name">🔁 Partages</td><td class="kpi-desc">Total des partages sur les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=shares</span></td></tr>
</table>""", unsafe_allow_html=True)

    with t2:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">➡️ Net follows</td><td class="kpi-desc">Nouveaux abonnements moins désabonnements.</td><td><span class="endpoint">/{page_id}/insights?metric=page_fan_adds,page_fan_removes</span></td></tr>
  <tr><td class="kpi-name">↗️ Unfollows</td><td class="kpi-desc">Total des désabonnements sur la période.</td><td><span class="endpoint">/{page_id}/insights?metric=page_daily_unfollows</span></td></tr>
  <tr><td class="kpi-name">👤 Followers (Lifetime)</td><td class="kpi-desc">Évolution du total abonnés jour par jour.</td><td><span class="endpoint">/{page_id}/insights/page_fans?period=lifetime</span></td></tr>
</table>""", unsafe_allow_html=True)

    with t3:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">🔥 Total interactions</td><td class="kpi-desc">Somme des interactions de tous les posts sur la période (réactions + commentaires + partages).</td><td><span class="endpoint">/{page_id}/posts?fields=reactions,comments,shares</span></td></tr>
  <tr><td class="kpi-name">❤️ Réactions</td><td class="kpi-desc">Total des réactions sur tous les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=reactions.summary(true)</span></td></tr>
  <tr><td class="kpi-name">💬 Commentaires</td><td class="kpi-desc">Total des commentaires sur tous les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=comments.summary(true)</span></td></tr>
  <tr><td class="kpi-name">🔁 Partages</td><td class="kpi-desc">Total des partages sur tous les posts.</td><td><span class="endpoint">/{page_id}/posts?fields=shares</span></td></tr>
</table>""", unsafe_allow_html=True)

    with t4:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">📏 Avg Daily Reach</td><td class="kpi-desc">Moyenne de comptes uniques touchés par jour.</td><td><span class="endpoint">/{page_id}/insights?metric=page_impressions_unique&period=day</span></td></tr>
  <tr><td class="kpi-name">🏔️ Peak Reach Day</td><td class="kpi-desc">Meilleure journée en portée sur la période.</td><td><span class="endpoint">Calculé depuis la série journalière</span></td></tr>
  <tr><td class="kpi-name">📊 Total Impressions</td><td class="kpi-desc">Nombre total d'affichages sur la période.</td><td><span class="endpoint">/{page_id}/insights?metric=page_impressions&period=day</span></td></tr>
  <tr><td class="kpi-name">🎯 Pic Impressions</td><td class="kpi-desc">Meilleure journée en impressions.</td><td><span class="endpoint">Calculé depuis la série journalière</span></td></tr>
  <tr><td class="kpi-name">📈 Moy. journalière</td><td class="kpi-desc">Moyenne d'impressions par jour.</td><td><span class="endpoint">Calculé depuis la série journalière</span></td></tr>
</table>""", unsafe_allow_html=True)

    with t5:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Podium Top #3 par portée et Top #3 par engagement. Chaque carte affiche :</p><br>
<table class="kpi-table">
  <tr><th>Métrique carte</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">👁️ Reach</td><td class="kpi-desc">Comptes uniques ayant vu ce post (seule métrique d'impression disponible pour New Page Experience).</td><td><span class="endpoint">/{post_id}/insights?metric=post_impressions_unique</span></td></tr>
  <tr><td class="kpi-name">❤️ Réactions</td><td class="kpi-desc">Total des réactions sur le post.</td><td><span class="endpoint">/{post_id}?fields=reactions.summary(true)</span></td></tr>
  <tr><td class="kpi-name">💬 Commentaires</td><td class="kpi-desc">Total des commentaires.</td><td><span class="endpoint">/{post_id}?fields=comments.summary(true)</span></td></tr>
  <tr><td class="kpi-name">🔁 Partages</td><td class="kpi-desc">Total des partages (inclut reposts via post_activity_by_action_type).</td><td><span class="endpoint">/{post_id}/insights?metric=post_activity_by_action_type</span></td></tr>
  <tr><td class="kpi-name">🖱️ Clics</td><td class="kpi-desc">Total des clics sur le post (liens, photo, nom de page).</td><td><span class="endpoint">/{post_id}/insights?metric=post_clicks</span></td></tr>
  <tr><td class="kpi-name">⚡ Total interactions</td><td class="kpi-desc">Réactions + Commentaires + Partages.</td><td><span class="endpoint">Calculé</span></td></tr>
</table>""", unsafe_allow_html=True)

    with t6:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">🆕 Nouveaux contacts</td><td class="kpi-desc">Nouvelles conversations initiées en DM.</td><td><span class="endpoint">/{page_id}/insights?metric=page_messages_new_conversations_unique</span></td></tr>
</table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Instagram ─────────────────────────────────────────────────────────────
    st.markdown('<div class="doc-section-title">📸 Instagram</div>', unsafe_allow_html=True)

    i1, i2, i3 = st.tabs(["Vue d'ensemble", "📡 Visibilité", "💬 Engagement"])

    with i1:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">👥 Followers</td><td class="kpi-desc">Total abonnés au compte Instagram.</td><td><span class="endpoint">/{ig_user_id}?fields=followers_count</span></td></tr>
  <tr><td class="kpi-name">📝 Publications</td><td class="kpi-desc">Nombre de posts publiés sur la période.</td><td><span class="endpoint">/{ig_user_id}/media?fields=id,timestamp,…</span></td></tr>
  <tr><td class="kpi-name">📊 Taux d'engagement</td><td class="kpi-desc">Total interactions ÷ couverture × 100.</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">👁️ Couvertures (Reach)</td><td class="kpi-desc">Comptes uniques ayant vu au moins un contenu. Indisponible si période > 30 jours.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=reach&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">👁️ Vues</td><td class="kpi-desc">Total affichages de tous les contenus (posts + reels + stories). Un seul appel API agrégé.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=views&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">🔖 Enregistrements</td><td class="kpi-desc">Total des sauvegardes sur tous les posts de la période.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=saves&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">🔥 Total interactions</td><td class="kpi-desc">Likes + commentaires + partages + enregistrements. Valeur directe de l'API Meta (non filtrée).</td><td><span class="endpoint">/{ig_user_id}/insights?metric=total_interactions&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">❤️ Réactions</td><td class="kpi-desc">Total des likes sur tous les posts de la période.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=likes&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">💬 Commentaires</td><td class="kpi-desc">Total des commentaires sur tous les posts.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=comments&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">↗️ Partages</td><td class="kpi-desc">Total des partages (Stories, DMs, etc.).</td><td><span class="endpoint">/{ig_user_id}/insights?metric=shares&period=day&metric_type=total_value</span></td></tr>
</table>""", unsafe_allow_html=True)

    with i2:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">👁️ Total Reach</td><td class="kpi-desc">Comptes uniques touchés sur la période (dédupliqué).</td><td><span class="endpoint">/{ig_user_id}/insights?metric=reach&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">🎯 Pic</td><td class="kpi-desc">Meilleure journée en portée sur la période.</td><td><span class="endpoint">Calculé depuis la série journalière</span></td></tr>
  <tr><td class="kpi-name">📏 Moy. journalière</td><td class="kpi-desc">Moyenne de portée par jour sur la période.</td><td><span class="endpoint">Calculé depuis la série journalière</span></td></tr>
</table>""", unsafe_allow_html=True)

    with i3:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">🔥 Total interactions</td><td class="kpi-desc">Likes + commentaires + partages + enregistrements sur la période.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=total_interactions&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">❤️ Réactions</td><td class="kpi-desc">Total des likes sur tous les posts.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=likes&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">💬 Commentaires</td><td class="kpi-desc">Total des commentaires sur tous les posts.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=comments&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">🔖 Enregistrements</td><td class="kpi-desc">Total des sauvegardes sur tous les posts.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=saves&period=day&metric_type=total_value</span></td></tr>
  <tr><td class="kpi-name">↗️ Partages</td><td class="kpi-desc">Total des partages sur tous les posts.</td><td><span class="endpoint">/{ig_user_id}/insights?metric=shares&period=day&metric_type=total_value</span></td></tr>
</table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Boost ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="doc-section-title">🚀 Boost (Campagnes Payantes)</div>', unsafe_allow_html=True)

    b1, b2, b3, b4, b5, b6 = st.tabs(["📊 Global", "🎯 Conversion", "🗂️ Par Objectif", "🏆 Top #3 Campagnes", "📋 Rapport", "👥 Démographie & Géo"])

    with b1:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">📁 Total campagnes</td><td class="kpi-desc">Nombre de campagnes actives sur la période.</td><td><span class="endpoint">/{ad_account}/campaigns?fields=id,name</span></td></tr>
  <tr><td class="kpi-name">🖱️ Clics sur le lien</td><td class="kpi-desc">Total de tous les clics sur la publicité (lien, réaction, commentaire, profil, etc.).</td><td><span class="endpoint">/{ad_account}/insights?fields=clicks&level=campaign</span></td></tr>
  <tr><td class="kpi-name">👁️ Comptes touchés</td><td class="kpi-desc">Personnes uniques ayant vu au moins une pub.</td><td><span class="endpoint">/{ad_account}/insights?fields=reach&level=account</span></td></tr>
  <tr><td class="kpi-name">📢 Impressions</td><td class="kpi-desc">Total d'affichages des publicités.</td><td><span class="endpoint">/{ad_account}/insights?fields=impressions&level=campaign</span></td></tr>
  <tr><td class="kpi-name">💸 Coût par clic (CPC)</td><td class="kpi-desc">Budget ÷ nombre de clics.</td><td><span class="endpoint">/{ad_account}/insights?fields=cpc&level=campaign</span></td></tr>
  <tr><td class="kpi-name">📈 CTR</td><td class="kpi-desc">Clics ÷ impressions × 100.</td><td><span class="endpoint">/{ad_account}/insights?fields=ctr&level=campaign</span></td></tr>
  <tr><td class="kpi-name">💰 Montant dépensé</td><td class="kpi-desc">Budget total consommé sur la période.</td><td><span class="endpoint">/{ad_account}/insights?fields=spend&level=campaign</span></td></tr>
  <tr><td class="kpi-name">🔁 Répétition</td><td class="kpi-desc">Impressions ÷ Reach. Fréquence moyenne d'exposition.</td><td><span class="endpoint">/{ad_account}/insights?fields=frequency&level=campaign</span></td></tr>
</table>""", unsafe_allow_html=True)

    with b2:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Filtre uniquement les campagnes avec un objectif <strong>CONVERSIONS</strong> ou <strong>OUTCOME_SALES</strong>.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">📁 Campagnes</td><td class="kpi-desc">Nombre de campagnes conversion actives sur la période.</td><td><span class="endpoint">Filtré depuis /{ad_account}/campaigns</span></td></tr>
  <tr><td class="kpi-name">🖱️ Clics sur le lien</td><td class="kpi-desc">Clics vers l'URL de destination uniquement (inline_link_clicks), sans réactions ni commentaires.</td><td><span class="endpoint">/{ad_account}/insights?fields=inline_link_clicks&level=campaign</span></td></tr>
  <tr><td class="kpi-name">👁️ Comptes touchés</td><td class="kpi-desc">Reach dédupliqué pour les campagnes conversion uniquement (1 appel API combiné).</td><td><span class="endpoint">/{ad_account}/insights?fields=reach&level=account&filtering=campaign.id IN [...]</span></td></tr>
  <tr><td class="kpi-name">📢 Impressions</td><td class="kpi-desc">Total d'affichages des campagnes conversion.</td><td><span class="endpoint">/{ad_account}/insights?fields=impressions&level=campaign</span></td></tr>
  <tr><td class="kpi-name">💸 Coût par clic (CPC)</td><td class="kpi-desc">Budget conversion ÷ clics sur le lien (pondéré par volume).</td><td><span class="endpoint">Calculé : spend ÷ inline_link_clicks</span></td></tr>
  <tr><td class="kpi-name">📈 CTR</td><td class="kpi-desc">Clics sur le lien ÷ impressions × 100 (pondéré par impressions).</td><td><span class="endpoint">Calculé : inline_link_clicks ÷ impressions × 100</span></td></tr>
  <tr><td class="kpi-name">💰 Montant dépensé</td><td class="kpi-desc">Budget total consommé par les campagnes conversion.</td><td><span class="endpoint">/{ad_account}/insights?fields=spend&level=campaign</span></td></tr>
  <tr><td class="kpi-name">🔁 Répétition</td><td class="kpi-desc">Impressions ÷ Reach dédupliqué des campagnes conversion.</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">🎁 Coût par vente</td><td class="kpi-desc">Budget ÷ nombre de conversions (purchase).</td><td><span class="endpoint">/{ad_account}/insights?fields=cost_per_action_type&level=campaign</span></td></tr>
  <tr><td class="kpi-name">✅ Commandes</td><td class="kpi-desc">Total des conversions de type "purchase" attribuées aux publicités.</td><td><span class="endpoint">/{ad_account}/insights?fields=actions[action_type=purchase]&level=campaign</span></td></tr>
</table>""", unsafe_allow_html=True)

    with b3:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Agrège les KPIs de toutes les campagnes selon les objectifs sélectionnés via un filtre multiselect. Le reach est récupéré en un seul appel API dédupliqué pour les campagnes sélectionnées.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">Filtre objectif</td><td class="kpi-desc">Multiselect listant tous les objectifs présents (Ventes, Trafic, Notoriété, Engagement, Leads…). Sélectionner un ou plusieurs pour filtrer les KPIs.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">📁 Campagnes</td><td class="kpi-desc">Nombre de campagnes actives pour les objectifs sélectionnés.</td><td><span class="endpoint">Filtré depuis campaigns list</span></td></tr>
  <tr><td class="kpi-name">🖱️ Clics sur le lien</td><td class="kpi-desc">inline_link_clicks (clics URL destination uniquement) pour les objectifs sélectionnés.</td><td><span class="endpoint">/{ad_account}/insights?fields=inline_link_clicks&level=campaign</span></td></tr>
  <tr><td class="kpi-name">👁️ Comptes touchés</td><td class="kpi-desc">Reach dédupliqué exact — un seul appel API avec tous les IDs de campagnes sélectionnées combinés.</td><td><span class="endpoint">/{ad_account}/insights?fields=reach&level=account&filtering=campaign.id IN [ids]</span></td></tr>
  <tr><td class="kpi-name">📢 Impressions</td><td class="kpi-desc">Total impressions pour les objectifs sélectionnés.</td><td><span class="endpoint">/{ad_account}/insights?fields=impressions&level=campaign</span></td></tr>
  <tr><td class="kpi-name">💸 CPC, 📈 CTR, 💰 Dépensé</td><td class="kpi-desc">Métriques pondérées par volume (pas une simple moyenne).</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">🎁 Coût par vente / ✅ Commandes</td><td class="kpi-desc">Conversions purchase pour les objectifs sélectionnés.</td><td><span class="endpoint">/{ad_account}/insights?fields=actions,cost_per_action_type&level=campaign</span></td></tr>
</table>""", unsafe_allow_html=True)

    with b4:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Top 3 campagnes triées par nombre de commandes (conversions). Si aucune conversion, classement par budget dépensé.</p><br>
<table class="kpi-table">
  <tr><th>Métrique carte</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">🥇🥈🥉 Classement</td><td class="kpi-desc">Podium des 3 meilleures campagnes par ventes (ou par spend si 0 commandes).</td><td><span class="endpoint">Trié depuis campaigns list</span></td></tr>
  <tr><td class="kpi-name">✅ Commandes</td><td class="kpi-desc">Nombre de conversions purchase attribuées à la campagne.</td><td><span class="endpoint">/{ad_account}/insights?fields=actions&level=campaign</span></td></tr>
  <tr><td class="kpi-name">💰 Dépensé</td><td class="kpi-desc">Budget consommé par la campagne.</td><td><span class="endpoint">/{ad_account}/insights?fields=spend&level=campaign</span></td></tr>
  <tr><td class="kpi-name">🎁 CPA</td><td class="kpi-desc">Coût par acquisition (spend ÷ conversions).</td><td><span class="endpoint">/{ad_account}/insights?fields=cost_per_action_type&level=campaign</span></td></tr>
  <tr><td class="kpi-name">🖱️ Clics</td><td class="kpi-desc">Clics sur le lien (inline_link_clicks) pour la campagne.</td><td><span class="endpoint">/{ad_account}/insights?fields=inline_link_clicks&level=campaign</span></td></tr>
</table>""", unsafe_allow_html=True)

    with b5:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">
L'onglet <strong>📋 Rapport</strong> contient deux tableaux indépendants, chacun avec son propre filtre par objectif et son bouton d'export Excel.
</p><br>

<p style="color:#E8420A;font-size:15px;font-weight:700;">📋 Rapport Hebdomadaire Sales</p>
<p style="color:#a1a1aa;font-size:13px;">
Tableau au niveau <strong>ad</strong> (une ligne par publicité), format identique à l'export CSV de Meta Ads Manager — 43 colonnes dans l'ordre exact du CSV.
Trié par date de création de campagne (plus récente en premier).
</p><br>
<table class="kpi-table">
  <tr><th>Fonctionnalité / Colonne</th><th>Description</th><th>Source</th></tr>
  <tr><td class="kpi-name">🔽 Filtre objectif (indépendant)</td><td class="kpi-desc">Multiselect propre à ce tableau — filtre uniquement les lignes de la table Sales.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">📥 Export Excel</td><td class="kpi-desc">Télécharge les 43 colonnes au format .xlsx (openpyxl).</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">☑️ Sélection multi-lignes</td><td class="kpi-desc">Shift+clic pour une plage, Ctrl/Cmd+clic pour une sélection multiple.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">Ad name → Campaign name → Delivery status → Delivery level → Ad set name</td><td class="kpi-desc">Identifiants de la publicité, campagne, adset et statut de diffusion.</td><td><span class="endpoint">level=ad → ad_name, campaign_name, adset_name, effective_status</span></td></tr>
  <tr><td class="kpi-name">Objective</td><td class="kpi-desc">Objectif Meta de la campagne (OUTCOME_SALES, OUTCOME_AWARENESS, etc.).</td><td><span class="endpoint">/{ad_account}/campaigns?fields=objective</span></td></tr>
  <tr><td class="kpi-name">Result type / Results / Cost per result</td><td class="kpi-desc">Type de résultat principal, nombre de résultats et coût par résultat selon l'objectif de la campagne.</td><td><span class="endpoint">level=ad → actions, cost_per_action_type</span></td></tr>
  <tr><td class="kpi-name">Amount spent (EUR)</td><td class="kpi-desc">Budget consommé par l'ad sur la période.</td><td><span class="endpoint">level=ad → spend</span></td></tr>
  <tr><td class="kpi-name">Campaign Budget / Type · Ad Set Budget / Type</td><td class="kpi-desc">Budgets et types (Daily / Lifetime) au niveau campagne et adset. "Using campaign budget" si aucun budget adset défini.</td><td><span class="endpoint">/{ad_account}/campaigns + adsets → daily_budget, lifetime_budget</span></td></tr>
  <tr><td class="kpi-name">Reach / Impressions / Frequency / CPM / Cost per 1,000 reached</td><td class="kpi-desc">Portée unique, affichages totaux, fréquence, coût pour 1000 impressions, coût pour 1000 comptes touchés.</td><td><span class="endpoint">level=ad → reach, impressions, frequency</span></td></tr>
  <tr><td class="kpi-name">Clicks / CPC / CTR · Link clicks / CPC link / CTR link</td><td class="kpi-desc">Clics totaux et variantes "link click" uniquement.</td><td><span class="endpoint">level=ad → clicks, cpc, ctr, inline_link_clicks</span></td></tr>
  <tr><td class="kpi-name">Outbound clicks / Cost · Landing page views / Cost</td><td class="kpi-desc">Clics sortants et vues de page de destination avec leurs coûts unitaires.</td><td><span class="endpoint">level=ad → outbound_clicks, actions[landing_page_view]</span></td></tr>
  <tr><td class="kpi-name">Adds to cart / Website / Cost · Checkouts / Website / Cost · Purchases / Website / Cost per purchase</td><td class="kpi-desc">Conversions e-commerce (panier, paiement, achat) pixel Meta, avec et sans préfixe "Website".</td><td><span class="endpoint">level=ad → actions[offsite_conversion.fb_pixel_*]</span></td></tr>
  <tr><td class="kpi-name">Engagement / Quality / Conversion rate ranking</td><td class="kpi-desc">Classements Meta de la qualité, du taux d'engagement et de conversion par rapport aux ads similaires.</td><td><span class="endpoint">level=ad → quality_ranking, engagement_rate_ranking, conversion_rate_ranking</span></td></tr>
  <tr><td class="kpi-name">Reporting starts / ends</td><td class="kpi-desc">Dates de début et fin de la période sélectionnée dans le dashboard.</td><td><span class="endpoint">—</span></td></tr>
</table>

<br>
<p style="color:#E8420A;font-size:15px;font-weight:700;">📊 Rapport Hebdomadaire Notoriété & Engagement</p>
<p style="color:#a1a1aa;font-size:13px;">
Tableau au niveau <strong>campagne</strong> (une ligne par campagne), 19 colonnes dans l'ordre exact du CSV Ads Manager <em>Rapport-avec-kpi.csv</em>.
Affiché immédiatement après le tableau Sales, avec son propre filtre et son propre export Excel.
</p><br>
<table class="kpi-table">
  <tr><th>Colonne</th><th>Description</th><th>Source</th></tr>
  <tr><td class="kpi-name">🔽 Filtre objectif (indépendant)</td><td class="kpi-desc">Multiselect propre à ce tableau — OUTCOME_ENGAGEMENT affiché en premier, puis OUTCOME_AWARENESS. N'affecte pas le tableau Sales.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">📥 Export Excel</td><td class="kpi-desc">Télécharge les 19 colonnes au format .xlsx.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">☑️ Sélection multi-lignes</td><td class="kpi-desc">Shift+clic pour une plage, Ctrl/Cmd+clic pour une sélection multiple.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">Campaign name</td><td class="kpi-desc">Nom de la campagne.</td><td><span class="endpoint">/{ad_account}/campaigns?fields=name</span></td></tr>
  <tr><td class="kpi-name">Objective</td><td class="kpi-desc">Objectif Meta (OUTCOME_AWARENESS, OUTCOME_ENGAGEMENT, etc.).</td><td><span class="endpoint">/{ad_account}/campaigns?fields=objective</span></td></tr>
  <tr><td class="kpi-name">Reach / Impressions / Frequency</td><td class="kpi-desc">Portée unique, affichages totaux, fréquence moyenne de la campagne.</td><td><span class="endpoint">level=campaign → reach, impressions, frequency</span></td></tr>
  <tr><td class="kpi-name">Result type / Results</td><td class="kpi-desc">Type de résultat principal et nombre de résultats obtenus.</td><td><span class="endpoint">level=campaign → actions, cost_per_action_type</span></td></tr>
  <tr><td class="kpi-name">Amount spent (EUR)</td><td class="kpi-desc">Budget total consommé par la campagne sur la période.</td><td><span class="endpoint">level=campaign → spend</span></td></tr>
  <tr><td class="kpi-name">Starts / Ends</td><td class="kpi-desc">Dates de début et de fin de la campagne (déduites des ads).</td><td><span class="endpoint">level=ad → campaign start/end déduit</span></td></tr>
  <tr><td class="kpi-name">Cost per result</td><td class="kpi-desc">Budget ÷ nombre de résultats. Calculé ou retourné par l'API.</td><td><span class="endpoint">level=campaign → cost_per_action_type</span></td></tr>
  <tr><td class="kpi-name">Delivery status</td><td class="kpi-desc">Statut de diffusion : active, recently_completed, archived, etc.</td><td><span class="endpoint">/{ad_account}/campaigns?fields=effective_status</span></td></tr>
  <tr><td class="kpi-name">Delivery level</td><td class="kpi-desc">Toujours "campaign" pour ce tableau.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">Link clicks / CPC (cost per link click)</td><td class="kpi-desc">Clics sur le lien et coût par clic sur le lien au niveau campagne.</td><td><span class="endpoint">level=campaign → inline_link_clicks, cost_per_inline_link_click</span></td></tr>
  <tr><td class="kpi-name">CPM (cost per 1,000 impressions)</td><td class="kpi-desc">Coût pour 1000 impressions.</td><td><span class="endpoint">Calculé : spend ÷ impressions × 1000</span></td></tr>
  <tr><td class="kpi-name">CTR (all)</td><td class="kpi-desc">Taux de clic global (tous clics ÷ impressions × 100).</td><td><span class="endpoint">level=campaign → ctr</span></td></tr>
  <tr><td class="kpi-name">Reporting starts / Reporting ends</td><td class="kpi-desc">Dates de début et fin de la période sélectionnée dans le dashboard.</td><td><span class="endpoint">—</span></td></tr>
</table>
<br>
<p style="color:#a1a1aa;font-size:13px;"><strong>Drill-down par campagne</strong> — En dessous des deux tableaux, chaque campagne est affichée sous forme d'expander cliquable. À l'intérieur :</p>
<ul style="color:#a1a1aa;font-size:13px;margin-top:4px;">
  <li>Mini KPIs de la campagne (spend, clics, portée, CTR, CPC, impressions, répétition, commandes, CPA, objectif)</li>
  <li>Tableau <strong>adset</strong> avec les mêmes colonnes que le tableau Sales</li>
  <li>Sous-expanders par adset contenant le tableau <strong>ads</strong> avec les mêmes colonnes</li>
</ul>""", unsafe_allow_html=True)

    with b6:
        st.markdown("""
<table class="kpi-table">
  <tr><th>Section</th><th>Description</th><th>Endpoint</th></tr>
  <tr><td class="kpi-name">👥 Démographie</td><td class="kpi-desc">Répartition Hommes/Femmes par tranche d'âge.</td><td><span class="endpoint">/{ad_account}/insights?breakdowns=age,gender&fields=reach&level=campaign</span></td></tr>
  <tr><td class="kpi-name">🌍 Géographie</td><td class="kpi-desc">Top villes/régions par portée.</td><td><span class="endpoint">/{ad_account}/insights?breakdowns=region&fields=reach&level=campaign</span></td></tr>
</table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Google Analytics ──────────────────────────────────────────────────────
    st.markdown('<div class="doc-section-title">📊 Google Analytics 4</div>', unsafe_allow_html=True)

    g1, g2, g3, g4 = st.tabs(["📊 Vue d'ensemble", "🛒 E-commerce", "⚡ Événements", "🌍 Audience"])

    with g1:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">KPIs globaux du site footland.dz + sources de trafic. Source : Google Analytics 4 Data API (v1beta).</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Métrique GA4</th></tr>
  <tr><td class="kpi-name">👥 Utilisateurs actifs</td><td class="kpi-desc">Utilisateurs ayant déclenché au moins un événement sur la période.</td><td><span class="endpoint">activeUsers</span></td></tr>
  <tr><td class="kpi-name">🆕 Nouveaux utilisateurs</td><td class="kpi-desc">Utilisateurs visitant le site pour la première fois.</td><td><span class="endpoint">newUsers</span></td></tr>
  <tr><td class="kpi-name">🔄 Sessions</td><td class="kpi-desc">Nombre total de sessions (visites) sur la période.</td><td><span class="endpoint">sessions</span></td></tr>
  <tr><td class="kpi-name">✅ Sessions engagées</td><td class="kpi-desc">Sessions durant plus de 10 secondes, ayant une conversion ou au moins 2 pages vues.</td><td><span class="endpoint">engagedSessions</span></td></tr>
  <tr><td class="kpi-name">💡 Taux d'engagement</td><td class="kpi-desc">Sessions engagées ÷ Sessions totales × 100.</td><td><span class="endpoint">engagementRate</span></td></tr>
  <tr><td class="kpi-name">↩️ Taux de rebond</td><td class="kpi-desc">Sessions non engagées ÷ Sessions totales × 100.</td><td><span class="endpoint">bounceRate</span></td></tr>
  <tr><td class="kpi-name">⏱️ Durée moyenne</td><td class="kpi-desc">Durée moyenne d'une session en minutes et secondes.</td><td><span class="endpoint">averageSessionDuration</span></td></tr>
  <tr><td class="kpi-name">📄 Pages vues</td><td class="kpi-desc">Nombre total de pages affichées (rechargements inclus).</td><td><span class="endpoint">screenPageViews</span></td></tr>
  <tr><td class="kpi-name">📑 Pages / Session</td><td class="kpi-desc">Nombre moyen de pages consultées par session.</td><td><span class="endpoint">screenPageViewsPerSession</span></td></tr>
</table>
<br>
<p style="color:#a1a1aa;font-size:14px;font-weight:600;">🚦 Sources de trafic — Top 10 canaux classés par sessions.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Métrique / Dimension GA4</th></tr>
  <tr><td class="kpi-name">Canal</td><td class="kpi-desc">Groupe de canaux par défaut (Organic Search, Direct, Paid Social, Organic Social, Email, Referral…).</td><td><span class="endpoint">sessionDefaultChannelGroup</span></td></tr>
  <tr><td class="kpi-name">Sessions</td><td class="kpi-desc">Nombre de sessions provenant de ce canal.</td><td><span class="endpoint">sessions</span></td></tr>
  <tr><td class="kpi-name">Utilisateurs</td><td class="kpi-desc">Utilisateurs actifs provenant de ce canal.</td><td><span class="endpoint">activeUsers</span></td></tr>
  <tr><td class="kpi-name">Taux d'engagement</td><td class="kpi-desc">Sessions engagées ÷ Sessions × 100 pour ce canal.</td><td><span class="endpoint">engagementRate</span></td></tr>
  <tr><td class="kpi-name">Taux de rebond</td><td class="kpi-desc">Sessions non engagées ÷ Sessions × 100 pour ce canal.</td><td><span class="endpoint">bounceRate</span></td></tr>
  <tr><td class="kpi-name">% du total</td><td class="kpi-desc">Part de sessions de ce canal sur le total des sessions.</td><td><span class="endpoint">Calculé</span></td></tr>
</table>""", unsafe_allow_html=True)

    with g2:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Parcours d'achat des visiteurs + détail par article.</p><br>
<p style="color:#a1a1aa;font-size:13px;font-weight:600;">🛒 Parcours d'achat — Funnel session → achat par étape et par appareil.</p><br>
<table class="kpi-table">
  <tr><th>Étape</th><th>Description</th><th>Événement GA4</th></tr>
  <tr><td class="kpi-name">1. Ouverture de session</td><td class="kpi-desc">Utilisateurs ayant démarré une session.</td><td><span class="endpoint">session_start</span></td></tr>
  <tr><td class="kpi-name">2. Affichage du produit</td><td class="kpi-desc">Utilisateurs ayant consulté une fiche produit.</td><td><span class="endpoint">view_item</span></td></tr>
  <tr><td class="kpi-name">3. Ajout au panier</td><td class="kpi-desc">Utilisateurs ayant ajouté un article au panier.</td><td><span class="endpoint">add_to_cart</span></td></tr>
  <tr><td class="kpi-name">4. Paiement initié</td><td class="kpi-desc">Utilisateurs ayant commencé le processus de paiement.</td><td><span class="endpoint">begin_checkout</span></td></tr>
  <tr><td class="kpi-name">5. Achat finalisé</td><td class="kpi-desc">Utilisateurs ayant complété un achat.</td><td><span class="endpoint">purchase</span></td></tr>
  <tr><td class="kpi-name">▼ % abandon</td><td class="kpi-desc">Pourcentage d'utilisateurs perdus entre deux étapes consécutives.</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">Tableau par appareil</td><td class="kpi-desc">Même funnel ventilé par mobile, desktop, tablet, smart tv.</td><td><span class="endpoint">deviceCategory</span></td></tr>
</table>
<br>
<p style="color:#a1a1aa;font-size:13px;font-weight:600;">🛍️ Achats d'e-commerce — Top articles consultés, ajoutés au panier, achetés et revenu généré.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Métrique GA4</th></tr>
  <tr><td class="kpi-name">Article</td><td class="kpi-desc">Nom du produit tel que défini dans les événements e-commerce WooCommerce.</td><td><span class="endpoint">itemName</span></td></tr>
  <tr><td class="kpi-name">Consultés</td><td class="kpi-desc">Nombre de fois que la fiche produit a été vue.</td><td><span class="endpoint">itemsViewed</span></td></tr>
  <tr><td class="kpi-name">Ajoutés au panier</td><td class="kpi-desc">Nombre d'ajouts au panier pour cet article.</td><td><span class="endpoint">itemsAddedToCart</span></td></tr>
  <tr><td class="kpi-name">Achetés</td><td class="kpi-desc">Nombre d'articles achetés (quantité totale vendue).</td><td><span class="endpoint">itemsPurchased</span></td></tr>
  <tr><td class="kpi-name">Revenu (DZD)</td><td class="kpi-desc">Revenu total généré par cet article.</td><td><span class="endpoint">itemRevenue</span></td></tr>
</table>""", unsafe_allow_html=True)

    with g3:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Tous les événements GA4 déclenchés sur la période, triés par nombre d'occurrences.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Métrique GA4</th></tr>
  <tr><td class="kpi-name">Événement</td><td class="kpi-desc">Nom de l'événement GA4 (view_item, session_start, add_to_cart, begin_checkout, purchase…).</td><td><span class="endpoint">eventName</span></td></tr>
  <tr><td class="kpi-name">Nombre d'événements</td><td class="kpi-desc">Total de fois que cet événement a été déclenché sur la période.</td><td><span class="endpoint">eventCount</span></td></tr>
  <tr><td class="kpi-name">% du total</td><td class="kpi-desc">Part de cet événement sur le total de tous les événements.</td><td><span class="endpoint">Calculé</span></td></tr>
  <tr><td class="kpi-name">Utilisateurs</td><td class="kpi-desc">Nombre total d'utilisateurs ayant déclenché cet événement.</td><td><span class="endpoint">totalUsers</span></td></tr>
  <tr><td class="kpi-name">Événements / utilisateur</td><td class="kpi-desc">Nombre moyen de fois qu'un utilisateur actif a déclenché cet événement.</td><td><span class="endpoint">eventCountPerUser</span></td></tr>
  <tr><td class="kpi-name">Revenu (DZD)</td><td class="kpi-desc">Revenu associé à cet événement (non nul uniquement pour purchase).</td><td><span class="endpoint">totalRevenue</span></td></tr>
</table>""", unsafe_allow_html=True)

    with g4:
        st.markdown("""
<p style="color:#a1a1aa;font-size:14px;">Répartition géographique et par appareil des visiteurs du site.</p><br>
<p style="color:#a1a1aa;font-size:13px;font-weight:600;">🌍 Géographie — Top 10 pays et Top 15 villes.</p><br>
<table class="kpi-table">
  <tr><th>Section</th><th>Description</th><th>Dimension GA4</th></tr>
  <tr><td class="kpi-name">🌍 Top Pays</td><td class="kpi-desc">Top 10 pays par utilisateurs actifs, avec nombre de sessions et % du total.</td><td><span class="endpoint">country</span></td></tr>
  <tr><td class="kpi-name">🏙️ Top Villes</td><td class="kpi-desc">Top 15 villes par utilisateurs actifs (valeurs "(not set)" exclues), avec nombre de sessions et % du total.</td><td><span class="endpoint">city</span></td></tr>
</table>
<br>
<p style="color:#a1a1aa;font-size:13px;font-weight:600;">📱 Appareils — Répartition des sessions par type d'appareil.</p><br>
<table class="kpi-table">
  <tr><th>Indicateur</th><th>Description</th><th>Dimension / Métrique GA4</th></tr>
  <tr><td class="kpi-name">Appareil</td><td class="kpi-desc">Catégorie d'appareil : mobile, desktop, tablet.</td><td><span class="endpoint">deviceCategory</span></td></tr>
  <tr><td class="kpi-name">Utilisateurs</td><td class="kpi-desc">Utilisateurs actifs sur cet appareil.</td><td><span class="endpoint">activeUsers</span></td></tr>
  <tr><td class="kpi-name">Sessions</td><td class="kpi-desc">Nombre de sessions sur cet appareil.</td><td><span class="endpoint">sessions</span></td></tr>
  <tr><td class="kpi-name">Taux d'engagement</td><td class="kpi-desc">Sessions engagées ÷ Sessions × 100 pour cet appareil.</td><td><span class="endpoint">engagementRate</span></td></tr>
  <tr><td class="kpi-name">Taux de rebond</td><td class="kpi-desc">Taux de rebond pour cet appareil.</td><td><span class="endpoint">bounceRate</span></td></tr>
  <tr><td class="kpi-name">% du total</td><td class="kpi-desc">Part de cet appareil sur le total des utilisateurs.</td><td><span class="endpoint">Calculé</span></td></tr>
</table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Alertes (admin) ───────────────────────────────────────────────────────
    # Alerts and the AI report are agency tools, hidden from the client account,
    # so their documentation is hidden too — describing a feature the reader
    # cannot see only causes confusion.
    if _is_admin:
        st.markdown('<div class="doc-section-title">🚨 Alertes automatiques</div>', unsafe_allow_html=True)

        st.markdown("""
<p style="color:#a1a1aa;font-size:13px;">
Des alertes s'affichent en haut de chaque onglet et sous-onglet lorsqu'un seuil est franchi. Une alerte détectée sur une plateforme reste visible depuis les autres pendant la session.
La détection est faite par des règles fixes, <strong>pas par l'IA</strong> : un seuil se
déclenche ou non, de façon identique à chaque exécution. Les seuils sont calibrés sur
les données réelles de Footland (CPC ~0,005 EUR, coût par commande 1,35–2,00 EUR),
et non sur des références européennes inadaptées au marché algérien.
</p>
<p style="color:#a1a1aa;font-size:13px;">
<strong>Phase actuelle : observation.</strong> Les alertes s'affichent et sont écrites dans
les logs, mais aucune notification n'est envoyée. L'objectif est de mesurer leur
fréquence de déclenchement avant d'alerter qui que ce soit — une règle qui se déclenche
plus de deux fois par semaine est mal calibrée, pas informative.
</p><br>
<table class="kpi-table">
  <tr><th>Règle</th><th>Seuil</th><th>Pourquoi</th></tr>
  <tr><td class="kpi-name">💸 Coût par commande</td><td class="kpi-desc">Alerte à <strong>3 EUR</strong>, critique à <strong>5 EUR</strong>. Campagne dépensant plus de 50 EUR sans aucune commande : critique.</td><td><span class="endpoint">Référence observée : 1,35 à 2,01 EUR. Uniquement sur les campagnes Ventes — une campagne notoriété ne génère pas de commandes par nature.</span></td></tr>
  <tr><td class="kpi-name">🔁 Saturation d'audience</td><td class="kpi-desc">Répétition &gt; <strong>3 par semaine</strong> (critique à 4), ou répétition en hausse de +15 % pendant que le CTR recule de 15 %.</td><td><span class="endpoint">Le seuil est ramené à la semaine : la répétition s'accumule avec la durée de la période, donc 5,63 sur 30 jours (1,31/semaine) est sain alors que le même chiffre sur 7 jours ne l'est pas.</span></td></tr>
  <tr><td class="kpi-name">📊 Données ads manquantes</td><td class="kpi-desc">Des campagnes ont diffusé mais aucune publicité n'est récupérée.</td><td><span class="endpoint">Détecte l'échec silencieux qui avait vidé les tableaux Rapport pendant plusieurs jours.</span></td></tr>
  <tr><td class="kpi-name">🌐 Suivi GA4 défaillant</td><td class="kpi-desc">Moins de 0,5 page vue par session.</td><td><span class="endpoint">Détecte un tag page_view cassé — 12 pages vues déclarées pour 628 962 sessions passaient inaperçues.</span></td></tr>
</table>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ── Intelligence Artificielle ─────────────────────────────────────────────
    st.markdown('<div class="doc-section-title">🤖 Intelligence Artificielle</div>', unsafe_allow_html=True)

    st.markdown("""
<p style="color:#E8420A;font-size:15px;font-weight:700;">🧠 Rapport d'analyse <span style="font-size:12px;font-weight:500;color:#a1a1aa;">— réservé à l'agence</span></p>
<p style="color:#a1a1aa;font-size:13px;">
Un bouton discret <strong>« 🧠 Générer le rapport d'analyse »</strong> se trouve tout en bas
de chaque plateforme. Il produit un rapport qui <strong>interprète</strong> les chiffres : ce qui
a monté, ce qui a baissé, les causes probables, et des recommandations concrètes — puis se télécharge.
</p><br>
<table class="kpi-table">
  <tr><th>Fonctionnalité</th><th>Description</th><th>Détail technique</th></tr>
  <tr><td class="kpi-name">📍 Emplacement</td><td class="kpi-desc">Tout en bas de chaque plateforme, sous les onglets — un bouton discret, visible quel que soit l'onglet ouvert.</td><td><span class="endpoint">components/ai_insights.py</span></td></tr>
  <tr><td class="kpi-name">📈 Comparaison de périodes</td><td class="kpi-desc">Chaque indicateur est accompagné de sa valeur sur la période précédente et de sa variation — c'est ce qui permet au rapport d'expliquer les hausses et les baisses plutôt que de répéter les chiffres.</td><td><span class="endpoint">ctx_*["_prev"]</span></td></tr>
  <tr><td class="kpi-name">📉 Forme de la courbe</td><td class="kpi-desc">Les courbes journalières sont transmises au rapport sous forme de repères calculés : pic, creux, et moyennes début / milieu / fin de période. C'est ce qui lui permet d'écrire « un pic au 1er août suivi d'un essoufflement en fin de période » au lieu d'un simple total.</td><td><span class="endpoint">ctx_*["_series"]</span></td></tr>
  <tr><td class="kpi-name">📝 Contexte du mois</td><td class="kpi-desc">Champ libre à remplir avant de générer : opération commerciale, changement de budget, saisonnalité (Ramadan, soldes). L'IA ne peut pas deviner ces éléments — c'est le levier qui fait passer le texte d'un résumé à une véritable analyse. Modifier ce champ régénère le rapport.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">🏆 Campagnes nommées</td><td class="kpi-desc">Sur le Boost, le rapport reçoit le top 3 des campagnes par dépense, les CTR les plus faibles (dépense ≥ 10 EUR uniquement, pour écarter le bruit) et la répartition par objectif.</td><td><span class="endpoint">ctx_boost["_notes"]</span></td></tr>
  <tr><td class="kpi-name">📱 Organique vs payant</td><td class="kpi-desc">La portée et les vues d'une page incluent le trafic publicitaire. Si l'onglet Boost a été chargé, l'évolution du budget est transmise au rapport, qui doit alors distinguer ce qui relève réellement de l'organique.</td><td><span class="endpoint">paid_spend_note()</span></td></tr>
  <tr><td class="kpi-name">🔒 Fiabilité des chiffres</td><td class="kpi-desc">Toutes les valeurs et variations sont calculées en Python. Le modèle a interdiction formelle de calculer quoi que ce soit : il ne fait qu'interpréter. Il lui est aussi interdit de comparer le CTR entre objectifs différents (une campagne notoriété n'optimise pas le clic).</td><td><span class="endpoint">SYSTEM_PROMPT</span></td></tr>
  <tr><td class="kpi-name">🔄 Changement de période</td><td class="kpi-desc">Si la période change, le rapport affiché disparaît et le bouton réapparaît — cela évite de laisser une analyse obsolète sous de nouveaux chiffres.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">⚡ Coût & rapidité</td><td class="kpi-desc">Rien n'est généré tant que le bouton n'est pas cliqué. Le résultat est mis en cache sur les données : redemander la même période est instantané et gratuit.</td><td><span class="endpoint">st.cache_data(ttl=3600)</span></td></tr>
  <tr><td class="kpi-name">📥 Téléchargement</td><td class="kpi-desc">Le rapport peut être télécharger au format Markdown pour être intégré à un livrable client.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">🧠 Modèle utilisé</td><td class="kpi-desc">DeepSeek (v4-flash) en priorité — il produit l'analyse la plus fine. Bascule automatiquement sur Groq (GPT-OSS 120B) si DeepSeek est indisponible ou si le crédit prépayé est épuisé.</td><td><span class="endpoint">DEEPSEEK_API_KEY → GROQ_API_KEY</span></td></tr>
  <tr><td class="kpi-name">🛡️ Tolérance aux pannes</td><td class="kpi-desc">Double fournisseur : si le premier échoue, le second prend le relais. Si les deux échouent, un message discret s'affiche et le bouton reste utilisable — le dashboard n'est jamais bloqué.</td><td><span class="endpoint">—</span></td></tr>
</table>
<br>
<p style="color:#E8420A;font-size:15px;font-weight:700;">💬 Assistant conversationnel</p>
<p style="color:#a1a1aa;font-size:14px;">Un assistant flottant, propulsé par <strong>DeepSeek</strong> (avec Groq en secours), capable de répondre aux questions sur les statistiques affichées dans le dashboard.</p><br>
<table class="kpi-table">
  <tr><th>Fonctionnalité</th><th>Description</th><th>Détail technique</th></tr>
  <tr><td class="kpi-name">💬 Ouverture / fermeture</td><td class="kpi-desc">Bouton "💬 Assistant IA" en bas de la barre latérale. Le bouton devient "✕ Fermer l'assistant" quand le panneau est ouvert.</td><td><span class="endpoint">st.session_state.chat_open</span></td></tr>
  <tr><td class="kpi-name">🧠 Modèle IA</td><td class="kpi-desc">DeepSeek (v4-flash) en priorité — réponse en 3 secondes environ. Bascule automatiquement sur Groq (GPT-OSS) si DeepSeek est indisponible ou si le crédit prépayé est épuisé.</td><td><span class="endpoint">components/llm.py</span></td></tr>
  <tr><td class="kpi-name">📊 Contexte des données</td><td class="kpi-desc">L'assistant connaît les KPIs de la période et de l'onglet actuellement affichés (Facebook, Instagram, Boost, Google Analytics) — uniquement les sections déjà visitées dans la session en cours.</td><td><span class="endpoint">ctx_facebook / ctx_instagram / ctx_boost / ctx_ga4</span></td></tr>
  <tr><td class="kpi-name">🌐 Langue</td><td class="kpi-desc">Répond en français, en s'appuyant sur les données réelles du dashboard ; indique clairement si une donnée n'est pas disponible plutôt que d'inventer un chiffre.</td><td><span class="endpoint">—</span></td></tr>
  <tr><td class="kpi-name">🗑️ Effacer la conversation</td><td class="kpi-desc">Bouton visible quand le panneau est ouvert et qu'il y a des messages — réinitialise l'historique de discussion.</td><td><span class="endpoint">st.session_state.chat_history</span></td></tr>
</table>
<br>
<p style="color:#a1a1aa;font-size:13px;font-weight:600;">⚠️ Limitations de l'assistant</p><br>
<table class="kpi-table">
  <tr><th>Situation</th><th>Comportement</th></tr>
  <tr><td class="kpi-name">Aucune donnée chargée</td><td class="kpi-desc">Si aucun onglet n'a encore été visité dans la session, l'assistant répond sans contexte chiffré et le signale.</td></tr>
  <tr><td class="kpi-name">Limite quotidienne atteinte</td><td class="kpi-desc">Si DeepSeek et Groq sont tous deux indisponibles (crédit épuisé ou quota gratuit atteint), un message invite à réessayer plus tard.</td></tr>
  <tr><td class="kpi-name">Clé API manquante</td><td class="kpi-desc">Si <code style="background:rgba(232,66,10,0.1);padding:1px 5px;border-radius:4px;">GROQ_API_KEY</code> n'est pas configurée (st.secrets ou .env), l'assistant affiche un message d'erreur explicite.</td></tr>
  <tr><td class="kpi-name">Hors-sujet</td><td class="kpi-desc">L'assistant est conçu pour répondre uniquement sur le contenu du dashboard Footland (KPIs, sources de données, méthodes de calcul).</td></tr>
</table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Limitations ───────────────────────────────────────────────────────────
    with st.expander("⚠️ Limitations & Données Indisponibles", expanded=False):
        st.markdown("""
<div style="margin-bottom:0.8rem;font-size:0.9rem;color:#a1a1aa;">
Certains indicateurs affichent <strong style="color:#E8420A;">—</strong> ou peuvent différer de Meta Business Suite.
Ce n'est pas une erreur du dashboard — ce sont des contraintes imposées par l'API Meta.
</div>
""", unsafe_allow_html=True)

        st.markdown("#### 📊 KPIs avec restrictions de période")
        st.markdown("""
| KPI | Comportement | Raison API |
|---|---|---|
| 👁️ **Couvertures** (Instagram) | Affiche **—** si période > 30 jours | `metric_type=total_value` non supporté au-delà de 30 jours |
| 👁️ **Spectateurs** (Facebook) | Affiche **—** sur certaines périodes | Disponible uniquement pour exactement 1j, 7j ou 28–31j |
| 📊 **Taux d'engagement** | Affiche **—** quand la portée est indisponible | Formule = Interactions ÷ Portée — impossible sans portée |
""")

        st.markdown("#### 👁️ Vues & Enregistrements")
        st.markdown("""
| KPI | Limitation | Détail |
|---|---|---|
| 👁️ **Vues** (Instagram) | Inclut les données publicitaires | Le metric `views` de l'API Meta agrège posts organiques + reels + stories + contenus sponsorisés. Pas de filtre organique disponible. |
| 🔖 **Enregistrements** | Peut différer de Meta Business Suite | Business Suite peut inclure des enregistrements de contenus supprimés ou archivés |
| 📢 **Impressions** (Facebook) | Basé sur `post_impressions_unique` | Pour les pages New Page Experience, Meta n'expose que la portée unique par post, pas les impressions brutes |
""")

        st.markdown("#### 🚀 Boost — Données Indisponibles / Comportements Attendus")
        st.markdown("""
| Situation | Explication |
|---|---|
| **Delivery status = "—"** | Campagne archivée ou supprimée — l'API ne retourne pas les campagnes inactives par défaut |
| **End = "—"** | L'adset n'a pas de date de fin planifiée — il tourne jusqu'à être mis en pause manuellement |
| **Cost per add to cart / checkout = 0** | Meta ne retourne pas toujours ces coûts au niveau ad — le dashboard calcule automatiquement spend ÷ count en fallback |
| **Objective = "—" sur anciennes dates** | Les campagnes archivées ne figurent pas dans la liste par défaut de l'API |
| **Budget = 0** | L'adset utilise le budget de la campagne parente (pas de budget propre défini) |
""")

        st.markdown("#### 💾 Cache & Actualisation")
        st.markdown("""
| Situation | Explication |
|---|---|
| Une publication récente n'apparaît pas | Les données sont mises en cache — cliquez **🔄 Refresh Data** pour forcer le rechargement |
| Les chiffres diffèrent de Business Suite | Business Suite peut utiliser un fuseau horaire ou une fenêtre glissante différente |
| Les données d'hier semblent incomplètes | Meta finalise certaines métriques avec un délai de 24–48h |
""")

        st.info("💡 En cas de doute sur un chiffre, consultez directement **Meta Business Suite** pour le comparer — le dashboard suit la même source de données (Meta Graph API).")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Glossaire & Fréquence ─────────────────────────────────────────────────
    with st.expander("📚 Glossaire — Termes clés"):
        st.markdown("""
| Terme | Définition |
|---|---|
| **Reach (Portée)** | Comptes **uniques** ayant vu un contenu. Chaque personne comptée une seule fois. |
| **Impressions** | Nombre total d'**affichages**. Une même personne peut générer plusieurs impressions. |
| **Engagement** | Toute interaction active : like, commentaire, partage, clic, enregistrement. |
| **Taux d'engagement** | Engagement ÷ Reach × 100. |
| **CTR** | Click-Through Rate. Clics ÷ Impressions × 100. |
| **CPC** | Coût Par Clic. Budget ÷ Clics. |
| **CPA** | Coût Par Acquisition. Budget ÷ Conversions. |
| **Répétition** | Impressions ÷ Reach. Fois moyenne qu'une personne voit une pub. |
| **Conversion** | Action réalisée après avoir vu une pub (achat, inscription, etc.). |
| **Organique** | Contenu diffusé sans budget, via l'algorithme. |
| **Payant (Boost)** | Contenu promu via un budget Meta Ads. |
| **CPM** | Coût Pour Mille. Budget ÷ Impressions × 1000. |
| **Add to Cart** | Ajout au panier déclenché par le pixel Meta sur le site. |
| **Initiate Checkout** | Début du processus de paiement déclenché par le pixel Meta. |
| **Landing Page View** | Vue de page de destination après un clic sur la pub. |
| **Outbound Click** | Clic sortant vers un site externe (hors Meta). |
| **Delivery status** | Statut de diffusion d'une campagne/adset/ad : active, inactive, archived, deleted, with_issues. |
| **Adset** | Groupe de publicités dans une campagne — définit le ciblage, le budget et le calendrier. |
""")

    if _is_admin:
        with st.expander("🔄 Fréquence de mise à jour"):
            st.markdown("""
| Source | Fréquence |
|---|---|
| **Toutes les périodes** | Chargées au premier accès, puis sauvegardées en base indéfiniment |
| **Bouton Refresh Data** | Rechargement immédiat depuis Meta API — écrase les données en cache |
| **Nouvelle session** | Données servies depuis la base (Supabase) — aucun appel API si déjà en cache |

> Facebook et Instagram : **Meta Graph API v19.0** — Boost : **Meta Marketing API**
""")
