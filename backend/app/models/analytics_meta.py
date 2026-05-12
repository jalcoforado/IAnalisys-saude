"""
Modelos ANALYTICS Meta — star schema para dashboards de Redes Sociais.

9 tabelas (espelha migration 0035):

DIMENSÕES:
  - dim_canal_meta        (IG/FB/Ads/Pixel/Lead — seed)
  - dim_campanha_meta     (1 linha por campanha histórica)
  - dim_post_meta         (1 linha por post histórico)
  - dim_lead_meta         (1 linha por lead capturado)
  -- dim_tempo (reusa universal — já existe)

FATOS:
  - fato_meta_organico_diario   (alcance/engajamento orgânico, canal/dia)
  - fato_meta_pago_diario       (performance paga, campanha/dia)
  - fato_meta_funil_diario      (impressão → clique → lead → WhatsApp → consulta)
  - fato_meta_comentario        (cada comentário com flags IA — snapshot p/ analytics)
  - fato_meta_lead_jornada      (lead → conversa → consulta — cruza com fato_agenda)
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index,
    Integer, Numeric, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.mysql import CHAR, JSON
from app.db.base import Base


# ============================================================
# DIM CANAL — seed na migration
# ============================================================
class DimCanalMeta(Base):
    __tablename__ = "dim_canal_meta"
    __table_args__ = (
        UniqueConstraint("codigo", name="uk_dim_canal_meta_codigo"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(16), nullable=False)
    nome = Column(String(64), nullable=False)


# ============================================================
# DIM CAMPANHA
# ============================================================
class DimCampanhaMeta(Base):
    __tablename__ = "dim_campanha_meta"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_camp_meta_external"),
        Index("ix_dim_camp_meta_procedimento", "tenant_id", "procedimento_inferido"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(128), nullable=False)
    name = Column(String(500), nullable=True)
    objective = Column(String(64), nullable=True)
    status_atual = Column(String(32), nullable=True)
    procedimento_inferido = Column(String(64), nullable=True)
    data_inicio = Column(Date, nullable=True)
    data_fim = Column(Date, nullable=True)
    daily_budget = Column(Numeric(15, 2), nullable=True)
    lifetime_budget = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# DIM POST
# ============================================================
class DimPostMeta(Base):
    __tablename__ = "dim_post_meta"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canal_id", "external_id", name="uk_dim_post_meta_external"),
        Index("ix_dim_post_meta_posted", "tenant_id", "posted_date_key"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    canal_id = Column(Integer, ForeignKey("dim_canal_meta.id"), nullable=False)
    external_id = Column(String(128), nullable=False)
    media_type = Column(String(32), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    posted_date_key = Column(Integer, nullable=True)  # FK lógica dim_tempo
    caption_snippet = Column(String(300), nullable=True)
    permalink = Column(String(1000), nullable=True)
    thumbnail_url = Column(String(1000), nullable=True)
    topico_inferido = Column(String(64), nullable=True)  # IA
    hashtags = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# DIM LEAD
# ============================================================
class DimLeadMeta(Base):
    __tablename__ = "dim_lead_meta"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_lead_meta_external"),
        Index("ix_dim_lead_meta_captured", "tenant_id", "captured_date_key"),
        Index("ix_dim_lead_meta_virou", "tenant_id", "virou_paciente_flag"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(128), nullable=False)
    captured_at = Column(DateTime, nullable=True)
    captured_date_key = Column(Integer, nullable=True)
    campanha_id = Column(BigInteger, ForeignKey("dim_campanha_meta.id"), nullable=True)
    post_id = Column(BigInteger, ForeignKey("dim_post_meta.id"), nullable=True)
    nome_completo = Column(String(255), nullable=True)
    telefone_e164 = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)
    cidade = Column(String(128), nullable=True)
    uf = Column(String(2), nullable=True)
    interesse_procedimento = Column(String(128), nullable=True)
    patient_id = Column(BigInteger, nullable=True)  # FK lógica dim_paciente
    virou_paciente_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# FATO 1 — ORGÂNICO DIÁRIO (alcance/engajamento)
# ============================================================
class FatoMetaOrganicoDiario(Base):
    __tablename__ = "fato_meta_organico_diario"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canal_id", "data_referencia", name="uk_fato_meta_org_dia"),
        Index("ix_fato_meta_org_data", "tenant_id", "data_key"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    canal_id = Column(Integer, ForeignKey("dim_canal_meta.id"), nullable=False)
    data_key = Column(Integer, nullable=False)
    data_referencia = Column(Date, nullable=False)
    # Métricas orgânicas
    seguidores = Column(Integer, nullable=True)
    novos_seguidores = Column(Integer, nullable=True)
    unfollows = Column(Integer, nullable=True)
    alcance = Column(Integer, nullable=True)
    impressoes = Column(Integer, nullable=True)
    profile_views = Column(Integer, nullable=True)
    website_clicks = Column(Integer, nullable=True)
    posts_publicados = Column(Integer, nullable=True)
    total_likes = Column(Integer, nullable=True)
    total_comments = Column(Integer, nullable=True)
    total_shares = Column(Integer, nullable=True)
    total_saves = Column(Integer, nullable=True)
    engajamento_pct = Column(Numeric(7, 4), nullable=True)
    top_post_id = Column(BigInteger, ForeignKey("dim_post_meta.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# FATO 2 — PAGO DIÁRIO (performance campanha)
# ============================================================
class FatoMetaPagoDiario(Base):
    __tablename__ = "fato_meta_pago_diario"
    __table_args__ = (
        UniqueConstraint("tenant_id", "campanha_id", "data_referencia", name="uk_fato_meta_pago_dia"),
        Index("ix_fato_meta_pago_data", "tenant_id", "data_key"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    campanha_id = Column(BigInteger, ForeignKey("dim_campanha_meta.id"), nullable=True)
    data_key = Column(Integer, nullable=False)
    data_referencia = Column(Date, nullable=False)
    # Investimento
    spend = Column(Numeric(15, 2), nullable=True)
    impressoes = Column(Integer, nullable=True)
    cliques = Column(Integer, nullable=True)
    link_clicks = Column(Integer, nullable=True)
    reach = Column(Integer, nullable=True)
    frequency = Column(Numeric(8, 4), nullable=True)
    ctr = Column(Numeric(7, 4), nullable=True)
    cpc = Column(Numeric(15, 4), nullable=True)
    cpm = Column(Numeric(15, 4), nullable=True)
    # Conversões
    leads = Column(Integer, nullable=True)
    conversas_whatsapp = Column(Integer, nullable=True)
    video_views = Column(Integer, nullable=True)
    cpl = Column(Numeric(15, 4), nullable=True)
    # ROI
    roas_estimado = Column(Numeric(8, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# FATO 3 — FUNIL DIÁRIO (impressão → clique → lead → wpp → agenda → consulta)
# ============================================================
class FatoMetaFunilDiario(Base):
    """Funil consolidado da clínica — 6 etapas + 5 taxas + CPA."""
    __tablename__ = "fato_meta_funil_diario"
    __table_args__ = (
        UniqueConstraint("tenant_id", "data_referencia", name="uk_fato_meta_funil_dia"),
        Index("ix_fato_meta_funil_data", "tenant_id", "data_key"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    data_key = Column(Integer, nullable=False)
    data_referencia = Column(Date, nullable=False)
    # 6 etapas
    etapa1_impressoes = Column(Integer, nullable=True)
    etapa2_cliques = Column(Integer, nullable=True)
    etapa3_leads = Column(Integer, nullable=True)
    etapa4_conversas_whatsapp = Column(Integer, nullable=True)
    etapa5_consultas_agendadas = Column(Integer, nullable=True)
    etapa6_consultas_realizadas = Column(Integer, nullable=True)
    # 5 taxas
    taxa_clique_pct = Column(Numeric(7, 4), nullable=True)
    taxa_lead_pct = Column(Numeric(7, 4), nullable=True)
    taxa_wpp_pct = Column(Numeric(7, 4), nullable=True)
    taxa_agenda_pct = Column(Numeric(7, 4), nullable=True)
    taxa_consulta_pct = Column(Numeric(7, 4), nullable=True)
    # Investimento e ROI
    investimento = Column(Numeric(15, 2), nullable=True)
    cpa_consulta = Column(Numeric(15, 4), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# FATO 4 — COMENTÁRIO (snapshot p/ analytics — 11 flags)
# ============================================================
class FatoMetaComentario(Base):
    __tablename__ = "fato_meta_comentario"
    __table_args__ = (
        UniqueConstraint("tenant_id", "comentario_external_id", name="uk_fato_meta_coment_external"),
        Index("ix_fato_meta_coment_data", "tenant_id", "data_key"),
        Index("ix_fato_meta_coment_lead_quente", "tenant_id", "lead_quente_flag", "respondido_flag"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    comentario_external_id = Column(String(128), nullable=False)
    post_id = Column(BigInteger, ForeignKey("dim_post_meta.id"), nullable=True)
    data_key = Column(Integer, nullable=False)
    commented_at = Column(DateTime, nullable=True)
    autor_username = Column(String(128), nullable=True)
    # Classificação IA (11 colunas)
    sentimento = Column(String(16), nullable=True)
    lead_quente_flag = Column(Boolean, nullable=False, default=False)
    depoimento_flag = Column(Boolean, nullable=False, default=False)
    duvida_clinica_flag = Column(Boolean, nullable=False, default=False)
    objecao_flag = Column(Boolean, nullable=False, default=False)
    reclamacao_flag = Column(Boolean, nullable=False, default=False)
    procedimento_mencionado = Column(String(64), nullable=True)
    urgencia_atendimento = Column(String(16), nullable=True)
    requer_resposta_humana = Column(Boolean, nullable=False, default=False)
    respondido_flag = Column(Boolean, nullable=False, default=False)
    horas_para_resposta = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())


# ============================================================
# FATO 5 — LEAD JORNADA (cruza com fato_agenda Clinicorp)
# ============================================================
class FatoMetaLeadJornada(Base):
    """Jornada do lead: capturado → conversa → agendada → realizada.
    Cruzamento com Clinicorp via patient_id."""
    __tablename__ = "fato_meta_lead_jornada"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lead_id", name="uk_fato_meta_lead_jorn"),
        Index("ix_fato_meta_lead_jorn_data", "tenant_id", "data_key"),
        Index("ix_fato_meta_lead_jorn_virou", "tenant_id", "virou_paciente_flag"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    lead_id = Column(BigInteger, ForeignKey("dim_lead_meta.id"), nullable=False)
    data_key = Column(Integer, nullable=False)
    lead_date = Column(Date, nullable=False)
    primeira_conversa_at = Column(DateTime, nullable=True)
    primeira_consulta_agendada_at = Column(DateTime, nullable=True)
    primeira_consulta_realizada_at = Column(DateTime, nullable=True)
    # Tempos
    horas_ate_primeira_conversa = Column(Integer, nullable=True)
    dias_ate_primeira_consulta = Column(Integer, nullable=True)
    # Flags
    virou_paciente_flag = Column(Boolean, nullable=False, default=False)
    realizou_consulta_flag = Column(Boolean, nullable=False, default=False)
    realizou_procedimento_flag = Column(Boolean, nullable=False, default=False)
    # Cruzamento
    patient_id = Column(BigInteger, nullable=True)
    campanha_id = Column(BigInteger, ForeignKey("dim_campanha_meta.id"), nullable=True)
    # ROI
    receita_gerada = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False,
                        server_default=func.current_timestamp(),
                        onupdate=func.current_timestamp())
