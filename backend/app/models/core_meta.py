"""
Modelos CORE Meta — camada relacional limpa, derivada do staging.

12 tabelas (espelha migration 0034):
- core_meta_canais        (lookup IG/FB/Ads/Pixel/Lead — seeded)
- core_meta_perfis        (snapshot consolidado tenant/canal/data)
- core_meta_pixel         (config + last_fired)
- core_meta_posts         (unificado IG+FB, header)
- core_meta_post_metricas_diarias  (1 linha por post/dia)
- core_meta_comentarios   (com 11 colunas de classificação IA)
- core_meta_campanhas
- core_meta_adsets
- core_meta_ads
- core_meta_ad_metricas_diarias    (1 linha por ad/dia)
- core_meta_leads         (cruza com core_patients via fone/email)

Decisões:
- canal_id discrimina IG/FB nas tabelas unificadas (posts, perfis).
- core_meta_comentarios concentra TODAS as flags IA — `fato_meta_comentario`
  apenas snapshota o estado para consultas analíticas.
- core_meta_leads.patient_id cruza com core_patients (Clinicorp) por fone E.164
  ou email — `match_metodo` registra qual chave fechou o match.
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.mysql import CHAR, JSON
from app.db.base import Base


def _core_cols():
    """Colunas padrão de toda tabela core (id, tenant_id, soft-delete, timestamps)."""
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("is_deleted", Boolean, nullable=False, default=False),
        Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("updated_at", DateTime, nullable=False,
               server_default=func.current_timestamp(), onupdate=func.current_timestamp()),
    ]


# ============================================================
# 1. CANAIS (lookup)
# ============================================================
class CoreMetaCanais(Base):
    """Catálogo IG/FB/ADS/PXL/LEAD — seed na migration."""
    __tablename__ = "core_meta_canais"
    __table_args__ = (
        UniqueConstraint("codigo", name="uk_core_meta_canais_codigo"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(16), nullable=False)
    nome = Column(String(64), nullable=False)
    descricao = Column(String(255), nullable=True)
    is_ativo = Column(Boolean, nullable=False, default=True)


# ============================================================
# 2. PERFIS (snapshot diário consolidado IG/FB)
# ============================================================
class CoreMetaPerfis(Base):
    __tablename__ = "core_meta_perfis"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canal_id", "data_referencia",
                         name="uk_core_meta_perfis_dia"),
        Index("ix_core_meta_perfis_data", "tenant_id", "data_referencia"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    canal_id = Column(Integer, ForeignKey("core_meta_canais.id"), nullable=False)
    external_id = Column(String(128), nullable=False)
    data_referencia = Column(Date, nullable=False)
    username = Column(String(128), nullable=True)
    display_name = Column(String(255), nullable=True)
    biografia = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    profile_picture_url = Column(String(1000), nullable=True)
    seguidores = Column(Integer, nullable=True)
    seguindo = Column(Integer, nullable=True)
    total_posts = Column(Integer, nullable=True)
    fan_count = Column(Integer, nullable=True)  # FB: page likes
    category = Column(String(128), nullable=True)
    phone = Column(String(64), nullable=True)
    location_str = Column(String(255), nullable=True)
    verification_status = Column(String(32), nullable=True)


# ============================================================
# 3. PIXEL
# ============================================================
class CoreMetaPixel(Base):
    __tablename__ = "core_meta_pixel"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_pixel_external"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(64), nullable=False)
    nome = Column(String(255), nullable=True)
    data_criacao = Column(DateTime, nullable=True)
    last_fired_at = Column(DateTime, nullable=True)
    is_unavailable = Column(Boolean, nullable=False, default=False)
    dias_sem_disparar = Column(Integer, nullable=True)
    owner_business_id = Column(String(64), nullable=True)


# ============================================================
# 4. POSTS (unificado IG + FB)
# ============================================================
class CoreMetaPosts(Base):
    __tablename__ = "core_meta_posts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canal_id", "external_id",
                         name="uk_core_meta_posts_external"),
        Index("ix_core_meta_posts_posted", "tenant_id", "posted_at"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    canal_id = Column(Integer, ForeignKey("core_meta_canais.id"), nullable=False)
    external_id = Column(String(128), nullable=False)
    media_type = Column(String(32), nullable=True)
    caption = Column(Text, nullable=True)
    permalink = Column(String(1000), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    media_url = Column(String(1000), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    is_comment_enabled = Column(Boolean, nullable=True)
    hashtags = Column(JSON, nullable=True)
    mentions = Column(JSON, nullable=True)


# ============================================================
# 5. POST MÉTRICAS DIÁRIAS
# ============================================================
class CoreMetaPostMetricasDiarias(Base):
    __tablename__ = "core_meta_post_metricas_diarias"
    __table_args__ = (
        UniqueConstraint("tenant_id", "post_id", "data_referencia",
                         name="uk_core_meta_post_met_dia"),
        Index("ix_core_meta_post_met_data", "tenant_id", "data_referencia"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    post_id = Column(BigInteger, ForeignKey("core_meta_posts.id"), nullable=False)
    data_referencia = Column(Date, nullable=False)
    reach = Column(Integer, nullable=True)
    impressions = Column(Integer, nullable=True)
    engagement = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    comments_count = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    saves = Column(Integer, nullable=True)
    video_views = Column(Integer, nullable=True)
    video_avg_watch_time_sec = Column(Numeric(8, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# 6. COMENTÁRIOS — 11 colunas de classificação IA
# ============================================================
class CoreMetaComentarios(Base):
    """Comentários IG/FB com classificação IA.

    Flags IA aprovadas (11 colunas):
      sentimento, lead_quente_flag, depoimento_flag, duvida_clinica_flag,
      objecao_flag, reclamacao_flag, procedimento_mencionado,
      urgencia_atendimento, requer_resposta_humana, respondido_flag,
      horas_para_resposta.
    """
    __tablename__ = "core_meta_comentarios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_coments_external"),
        Index("ix_core_meta_coments_commented", "tenant_id", "commented_at"),
        Index("ix_core_meta_coments_lead_quente", "tenant_id", "lead_quente_flag"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(128), nullable=False)
    post_id = Column(BigInteger, ForeignKey("core_meta_posts.id"), nullable=True)
    post_external_id = Column(String(128), nullable=True)
    autor_username = Column(String(128), nullable=True)
    texto = Column(Text, nullable=False)
    commented_at = Column(DateTime, nullable=True)
    parent_external_id = Column(String(128), nullable=True)
    # Classificação IA
    sentimento = Column(Enum("positivo", "neutro", "negativo", name="sentimento_comentario"), nullable=True)
    lead_quente_flag = Column(Boolean, nullable=False, default=False)
    depoimento_flag = Column(Boolean, nullable=False, default=False)
    duvida_clinica_flag = Column(Boolean, nullable=False, default=False)
    objecao_flag = Column(Boolean, nullable=False, default=False)
    reclamacao_flag = Column(Boolean, nullable=False, default=False)
    procedimento_mencionado = Column(String(64), nullable=True)
    urgencia_atendimento = Column(Enum("alta", "media", "baixa", name="urgencia_comentario"), nullable=True)
    requer_resposta_humana = Column(Boolean, nullable=False, default=False)
    respondido_flag = Column(Boolean, nullable=False, default=False)
    horas_para_resposta = Column(Integer, nullable=True)
    classificacao_ia_modelo = Column(String(64), nullable=True)
    classificacao_ia_at = Column(DateTime, nullable=True)


# ============================================================
# 7. CAMPANHAS (Ads)
# ============================================================
class CoreMetaCampanhas(Base):
    __tablename__ = "core_meta_campanhas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_camp_external"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(128), nullable=False)
    name = Column(String(500), nullable=True)
    status = Column(String(32), nullable=True)
    effective_status = Column(String(32), nullable=True)
    objective = Column(String(64), nullable=True)
    daily_budget = Column(Numeric(15, 2), nullable=True)
    lifetime_budget = Column(Numeric(15, 2), nullable=True)
    start_time = Column(DateTime, nullable=True)
    stop_time = Column(DateTime, nullable=True)
    procedimento_inferido = Column(String(64), nullable=True)  # IA detecta pelo nome


# ============================================================
# 8. ADSETS
# ============================================================
class CoreMetaAdsets(Base):
    __tablename__ = "core_meta_adsets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_adsets_external"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(128), nullable=False)
    campaign_id = Column(BigInteger, ForeignKey("core_meta_campanhas.id"), nullable=True)
    name = Column(String(500), nullable=True)
    status = Column(String(32), nullable=True)
    daily_budget = Column(Numeric(15, 2), nullable=True)
    optimization_goal = Column(String(64), nullable=True)
    targeting = Column(JSON, nullable=True)


# ============================================================
# 9. ADS
# ============================================================
class CoreMetaAds(Base):
    __tablename__ = "core_meta_ads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_ads_external"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(128), nullable=False)
    adset_id = Column(BigInteger, ForeignKey("core_meta_adsets.id"), nullable=True)
    name = Column(String(500), nullable=True)
    status = Column(String(32), nullable=True)
    effective_status = Column(String(32), nullable=True)
    creative_id = Column(String(128), nullable=True)
    creative_thumbnail_url = Column(String(1000), nullable=True)


# ============================================================
# 10. AD MÉTRICAS DIÁRIAS
# ============================================================
class CoreMetaAdMetricasDiarias(Base):
    __tablename__ = "core_meta_ad_metricas_diarias"
    __table_args__ = (
        UniqueConstraint("tenant_id", "ad_id", "adset_id", "campaign_id",
                         "data_referencia", "level", name="uk_core_meta_ad_met_dia"),
        Index("ix_core_meta_ad_met_data", "tenant_id", "data_referencia"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    data_referencia = Column(Date, nullable=False)
    ad_id = Column(BigInteger, ForeignKey("core_meta_ads.id"), nullable=True)
    adset_id = Column(BigInteger, ForeignKey("core_meta_adsets.id"), nullable=True)
    campaign_id = Column(BigInteger, ForeignKey("core_meta_campanhas.id"), nullable=True)
    level = Column(String(16), nullable=False, default="ad")
    impressions = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    ctr = Column(Numeric(7, 4), nullable=True)
    spend = Column(Numeric(15, 2), nullable=True)
    cpc = Column(Numeric(15, 4), nullable=True)
    cpm = Column(Numeric(15, 4), nullable=True)
    reach = Column(Integer, nullable=True)
    frequency = Column(Numeric(8, 4), nullable=True)
    leads = Column(Integer, nullable=True)
    conversas_whatsapp = Column(Integer, nullable=True)
    link_clicks = Column(Integer, nullable=True)
    video_views = Column(Integer, nullable=True)
    actions_raw = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# 11. LEADS — cruza com core_patients (Clinicorp)
# ============================================================
class CoreMetaLeads(Base):
    """Leads capturados via form. patient_id resolve cruzamento com Clinicorp."""
    __tablename__ = "core_meta_leads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_leads_external"),
        Index("ix_core_meta_leads_telefone", "tenant_id", "telefone_e164"),
        Index("ix_core_meta_leads_email", "tenant_id", "email"),
        Index("ix_core_meta_leads_captured", "tenant_id", "captured_at"),
        Index("ix_core_meta_leads_patient", "tenant_id", "patient_id"),
    )
    id, tenant_id, is_deleted, created_at, updated_at = _core_cols()
    external_id = Column(String(128), nullable=False)
    form_external_id = Column(String(128), nullable=True)
    ad_external_id = Column(String(128), nullable=True)
    campaign_id = Column(BigInteger, ForeignKey("core_meta_campanhas.id"), nullable=True)
    captured_at = Column(DateTime, nullable=True)
    # Dados do form
    nome = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    telefone = Column(String(32), nullable=True)
    telefone_e164 = Column(String(32), nullable=True)  # normalizado pra match
    cidade = Column(String(128), nullable=True)
    uf = Column(String(2), nullable=True)
    interesse_procedimento = Column(String(128), nullable=True)
    field_data_raw = Column(JSON, nullable=True)
    # Match com pacientes
    patient_id = Column(BigInteger, nullable=True)  # FK lógica core_patients.id
    match_metodo = Column(String(32), nullable=True)  # 'telefone'/'email'/'nome'
    match_score = Column(Numeric(5, 2), nullable=True)
    matched_at = Column(DateTime, nullable=True)
    # Operacional
    contato_iniciado_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=True)  # 'novo'/'em_contato'/'agendado'/'consultado'/'perdido'
