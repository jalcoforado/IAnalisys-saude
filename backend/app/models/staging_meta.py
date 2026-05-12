"""
Modelos STAGING Meta Graph API — record-level com idempotência por
(tenant_id, external_id [+ data_referencia em snapshots diários]).

Espelha a migration 0033 (sub-PR 21a/staging). São 19 tabelas no total:
- 1 token table (multi-tenant credentials)
- 6 Instagram orgânico
- 4 Facebook orgânico
- 6 Ads (pago)
- 2 Pixel

Padrão (igual Clinicorp/Conta Azul):
- id BIGINT PK + tenant_id CHAR(36) FK
- external_id (Meta ID, VARCHAR 128)
- raw_data JSON (audit trail + insumo IA)
- synced_at + sync_job_id

Tabelas com snapshot diário usam UK composto com `data_referencia`.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.mysql import CHAR, JSON
from app.db.base import Base


def _stg_base():
    """Colunas mínimas de toda tabela staging Meta."""
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(128), nullable=False),
    ]


def _stg_tail():
    """Colunas finais (após colunas custom da tabela)."""
    return [
        Column("external_updated_at", DateTime, nullable=True),
        Column("raw_data", JSON, nullable=False),
        Column("synced_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("sync_job_id", BigInteger, ForeignKey("sync_jobs.id"), nullable=True),
    ]


# ============================================================
# 0. TOKENS — credenciais Meta por tenant (multi-tenant)
# ============================================================
class StgMetaTokens(Base):
    """Token + IDs vinculados (IG/FB/Ad Account/Pixel). 1 linha por tenant."""
    __tablename__ = "stg_meta_tokens"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uk_stg_meta_tokens_tenant"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    # App
    app_id = Column(String(64), nullable=False)
    app_name = Column(String(128), nullable=True)
    # Business
    business_id = Column(String(64), nullable=True)
    business_name = Column(String(255), nullable=True)
    # System User Token
    system_user_id = Column(String(64), nullable=True)
    system_user_name = Column(String(128), nullable=True)
    system_user_token = Column(Text, nullable=False)
    token_scopes = Column(JSON, nullable=True)
    token_validated_at = Column(DateTime, nullable=True)
    token_is_valid = Column(Boolean, nullable=False, default=True)
    # IDs das contas vinculadas
    fb_page_id = Column(String(64), nullable=True)
    fb_page_name = Column(String(255), nullable=True)
    fb_page_token = Column(Text, nullable=True)
    ig_account_id = Column(String(64), nullable=True)
    ig_username = Column(String(128), nullable=True)
    ad_account_id = Column(String(64), nullable=True)
    ad_account_authorized = Column(Boolean, nullable=False, default=False)
    pixel_id = Column(String(64), nullable=True)
    pixel_last_fired_at = Column(DateTime, nullable=True)
    # Operacional
    graph_api_version = Column(String(8), nullable=False, default="v19.0")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# 1. INSTAGRAM ORGÂNICO
# ============================================================
class StgMetaIgPerfil(Base):
    """Snapshot diário do perfil IG (seguidores/posts/seguindo)."""
    __tablename__ = "stg_meta_ig_perfil"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia",
                         name="uk_stg_meta_ig_perfil_external"),
        Index("ix_stg_meta_ig_perfil_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaIgPosts(Base):
    """Posts (mídia) do IG. Header — métricas vão em stg_meta_ig_post_insights."""
    __tablename__ = "stg_meta_ig_posts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ig_posts_external"),
        Index("ix_stg_meta_ig_posts_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    posted_at = Column(DateTime, nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaIgPostInsights(Base):
    """Métricas por post/dia (reach/impressions/saves/etc.)."""
    __tablename__ = "stg_meta_ig_post_insights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia",
                         name="uk_stg_meta_ig_post_insights_external"),
        Index("ix_stg_meta_ig_post_insights_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    post_external_id = Column(String(128), nullable=False)


class StgMetaIgAccountInsights(Base):
    """Métricas da conta IG por dia/métrica (reach, impressions, etc.).
    UK = (tenant_id, data_referencia, metric_name) — NÃO usa external_id."""
    __tablename__ = "stg_meta_ig_account_insights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_referencia", "metric_name",
                         name="uk_stg_meta_ig_acc_ins"),
        Index("ix_stg_meta_ig_account_insights_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    metric_name = Column(String(64), nullable=False)


class StgMetaIgStories(Base):
    """Stories IG (efêmeros — capturados antes de expirar)."""
    __tablename__ = "stg_meta_ig_stories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ig_stories_external"),
        Index("ix_stg_meta_ig_stories_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    posted_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaIgComments(Base):
    """Comentários em posts IG (insumo pra IA classificar leads quentes)."""
    __tablename__ = "stg_meta_ig_comments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ig_comments_external"),
        Index("ix_stg_meta_ig_comments_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    post_external_id = Column(String(128), nullable=False)
    commented_at = Column(DateTime, nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


# ============================================================
# 2. FACEBOOK ORGÂNICO
# ============================================================
class StgMetaFbPage(Base):
    """Snapshot diário da página FB (fans, followers, info)."""
    __tablename__ = "stg_meta_fb_page"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia",
                         name="uk_stg_meta_fb_page_external"),
        Index("ix_stg_meta_fb_page_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaFbPosts(Base):
    """Posts FB (header)."""
    __tablename__ = "stg_meta_fb_posts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_fb_posts_external"),
        Index("ix_stg_meta_fb_posts_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    posted_at = Column(DateTime, nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaFbPostInsights(Base):
    """Insights por post FB / dia."""
    __tablename__ = "stg_meta_fb_post_insights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia",
                         name="uk_stg_meta_fb_post_insights_external"),
        Index("ix_stg_meta_fb_post_insights_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    post_external_id = Column(String(128), nullable=False)


class StgMetaFbPageInsights(Base):
    """Métricas da página FB por dia/métrica.
    UK = (tenant_id, data_referencia, metric_name)."""
    __tablename__ = "stg_meta_fb_page_insights"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_referencia", "metric_name",
                         name="uk_stg_meta_fb_page_ins"),
        Index("ix_stg_meta_fb_page_insights_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    metric_name = Column(String(64), nullable=False)


# ============================================================
# 3. ADS (PAGO)
# ============================================================
class StgMetaAdsCampaigns(Base):
    __tablename__ = "stg_meta_ads_campaigns"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ads_campaigns_external"),
        Index("ix_stg_meta_ads_campaigns_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaAdsAdsets(Base):
    __tablename__ = "stg_meta_ads_adsets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ads_adsets_external"),
        Index("ix_stg_meta_ads_adsets_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    campaign_external_id = Column(String(128), nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaAdsAds(Base):
    __tablename__ = "stg_meta_ads_ads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ads_ads_external"),
        Index("ix_stg_meta_ads_ads_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    adset_external_id = Column(String(128), nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaAdsInsightsDiario(Base):
    """Insights diários — granularidade ad/dia (pode ser adset/campaign via `level`)."""
    __tablename__ = "stg_meta_ads_insights_diario"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia", "level",
                         name="uk_stg_meta_ads_ins_diario"),
        Index("ix_stg_meta_ads_insights_diario_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    ad_external_id = Column(String(128), nullable=True)
    adset_external_id = Column(String(128), nullable=True)
    campaign_external_id = Column(String(128), nullable=True)
    level = Column(String(16), nullable=False, default="ad")


class StgMetaAdsLeadgenForms(Base):
    """Templates de formulários de captura de lead."""
    __tablename__ = "stg_meta_ads_leadgen_forms"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ads_leadgen_forms_external"),
        Index("ix_stg_meta_ads_leadgen_forms_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaAdsLeads(Base):
    """Leads capturados pelos forms — insumo pra cruzar com pacientes Clinicorp."""
    __tablename__ = "stg_meta_ads_leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_stg_meta_ads_leads_external"),
        Index("ix_stg_meta_ads_leads_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    form_external_id = Column(String(128), nullable=True)
    ad_external_id = Column(String(128), nullable=True)
    captured_at = Column(DateTime, nullable=True)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


# ============================================================
# 4. PIXEL
# ============================================================
class StgMetaPixel(Base):
    """Detalhes do pixel — snapshot diário (id, name, last_fired_time)."""
    __tablename__ = "stg_meta_pixel"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", "data_referencia",
                         name="uk_stg_meta_pixel_external"),
        Index("ix_stg_meta_pixel_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()


class StgMetaPixelEventosDiarios(Base):
    """Contagem de eventos do Pixel por dia/event_name (PageView, Lead, etc.).
    UK = (tenant_id, data_referencia, event_name)."""
    __tablename__ = "stg_meta_pixel_eventos_diarios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_referencia", "event_name",
                         name="uk_stg_meta_pixel_ev_diario"),
        Index("ix_stg_meta_pixel_eventos_diarios_synced", "tenant_id", "synced_at"),
    )
    id, tenant_id, external_id = _stg_base()
    data_referencia = Column(Date, nullable=False)
    external_updated_at, raw_data, synced_at, sync_job_id = _stg_tail()
    event_name = Column(String(64), nullable=False)
    event_count = Column(Integer, nullable=False, default=0)
