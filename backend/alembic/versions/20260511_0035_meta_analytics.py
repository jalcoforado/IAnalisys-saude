"""Meta — Sub-PR 21a/analytics — Star schema para dashboards de Redes Sociais.

Cria 4 dimensões + 5 fatos:

DIMENSÕES:
  - dim_canal_meta        (lookup IG/FB/Ads/Pixel)
  - dim_campanha_meta     (uma linha por campanha histórica + procedimento inferido)
  - dim_post_meta         (uma linha por post histórico)
  - dim_lead_meta         (uma linha por lead capturado)
  -- dim_tempo já existe (universal)

FATOS:
  - fato_meta_organico_diario   (alcance/engajamento orgânico)
  - fato_meta_pago_diario       (performance paga por campanha/dia)
  - fato_meta_funil_diario      (funil consolidado impressão → clique → lead → conversa → consulta)
  - fato_meta_comentario        (cada comentário com flags)
  - fato_meta_lead_jornada      (lead → conversa → consulta — cruza com fato_agenda Clinicorp)

Revision ID: 0035
Revises: 0034
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================================
    # DIM CANAL
    # ============================================================
    op.create_table(
        "dim_canal_meta",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(16), nullable=False),
        sa.Column("nome", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uk_dim_canal_meta_codigo"),
    )
    op.execute("""
        INSERT INTO dim_canal_meta (codigo, nome) VALUES
            ('IG',  'Instagram'),
            ('FB',  'Facebook'),
            ('ADS', 'Meta Ads'),
            ('PXL', 'Pixel'),
            ('LEAD','Lead Forms')
    """)

    # ============================================================
    # DIM CAMPANHA
    # ============================================================
    op.create_table(
        "dim_campanha_meta",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("objective", sa.String(64), nullable=True),
        sa.Column("status_atual", sa.String(32), nullable=True),
        sa.Column("procedimento_inferido", sa.String(64), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_fim", sa.Date(), nullable=True),
        sa.Column("daily_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("lifetime_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_dim_camp_meta_external"),
    )
    op.create_index("ix_dim_camp_meta_procedimento", "dim_campanha_meta", ["tenant_id", "procedimento_inferido"])

    # ============================================================
    # DIM POST
    # ============================================================
    op.create_table(
        "dim_post_meta",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("canal_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("posted_date_key", sa.Integer(), nullable=True),  # FK dim_tempo
        sa.Column("caption_snippet", sa.String(300), nullable=True),
        sa.Column("permalink", sa.String(1000), nullable=True),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("topico_inferido", sa.String(64), nullable=True),  # IA
        sa.Column("hashtags", mysql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["canal_id"], ["dim_canal_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "canal_id", "external_id", name="uk_dim_post_meta_external"),
    )
    op.create_index("ix_dim_post_meta_posted", "dim_post_meta", ["tenant_id", "posted_date_key"])

    # ============================================================
    # DIM LEAD
    # ============================================================
    op.create_table(
        "dim_lead_meta",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("captured_date_key", sa.Integer(), nullable=True),
        sa.Column("campanha_id", sa.BigInteger(), nullable=True),
        sa.Column("post_id", sa.BigInteger(), nullable=True),  # caso lead orgânico (DM/comentário)
        sa.Column("nome_completo", sa.String(255), nullable=True),
        sa.Column("telefone_e164", sa.String(32), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("cidade", sa.String(128), nullable=True),
        sa.Column("uf", sa.String(2), nullable=True),
        sa.Column("interesse_procedimento", sa.String(128), nullable=True),
        sa.Column("patient_id", sa.BigInteger(), nullable=True),  # FK dim_paciente quando virou paciente
        sa.Column("virou_paciente_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campanha_id"], ["dim_campanha_meta.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["dim_post_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_dim_lead_meta_external"),
    )
    op.create_index("ix_dim_lead_meta_captured", "dim_lead_meta", ["tenant_id", "captured_date_key"])
    op.create_index("ix_dim_lead_meta_virou", "dim_lead_meta", ["tenant_id", "virou_paciente_flag"])

    # ============================================================
    # FATO 1 — ORGÂNICO DIÁRIO (alcance/engajamento)
    # ============================================================
    op.create_table(
        "fato_meta_organico_diario",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("canal_id", sa.Integer(), nullable=False),
        sa.Column("data_key", sa.Integer(), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        # Métricas orgânicas
        sa.Column("seguidores", sa.Integer(), nullable=True),
        sa.Column("novos_seguidores", sa.Integer(), nullable=True),
        sa.Column("unfollows", sa.Integer(), nullable=True),
        sa.Column("alcance", sa.Integer(), nullable=True),
        sa.Column("impressoes", sa.Integer(), nullable=True),
        sa.Column("profile_views", sa.Integer(), nullable=True),
        sa.Column("website_clicks", sa.Integer(), nullable=True),
        sa.Column("posts_publicados", sa.Integer(), nullable=True),
        sa.Column("total_likes", sa.Integer(), nullable=True),
        sa.Column("total_comments", sa.Integer(), nullable=True),
        sa.Column("total_shares", sa.Integer(), nullable=True),
        sa.Column("total_saves", sa.Integer(), nullable=True),
        sa.Column("engajamento_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("top_post_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["canal_id"], ["dim_canal_meta.id"]),
        sa.ForeignKeyConstraint(["top_post_id"], ["dim_post_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "canal_id", "data_referencia", name="uk_fato_meta_org_dia"),
    )
    op.create_index("ix_fato_meta_org_data", "fato_meta_organico_diario", ["tenant_id", "data_key"])

    # ============================================================
    # FATO 2 — PAGO DIÁRIO (performance campanha)
    # ============================================================
    op.create_table(
        "fato_meta_pago_diario",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("campanha_id", sa.BigInteger(), nullable=True),
        sa.Column("data_key", sa.Integer(), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        # Investimento
        sa.Column("spend", sa.Numeric(15, 2), nullable=True),
        sa.Column("impressoes", sa.Integer(), nullable=True),
        sa.Column("cliques", sa.Integer(), nullable=True),
        sa.Column("link_clicks", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Numeric(8, 4), nullable=True),
        sa.Column("ctr", sa.Numeric(7, 4), nullable=True),
        sa.Column("cpc", sa.Numeric(15, 4), nullable=True),
        sa.Column("cpm", sa.Numeric(15, 4), nullable=True),
        # Conversões
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("conversas_whatsapp", sa.Integer(), nullable=True),
        sa.Column("video_views", sa.Integer(), nullable=True),
        sa.Column("cpl", sa.Numeric(15, 4), nullable=True),
        # ROI projetado (caso seja sub-PR futuro)
        sa.Column("roas_estimado", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campanha_id"], ["dim_campanha_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "campanha_id", "data_referencia", name="uk_fato_meta_pago_dia"),
    )
    op.create_index("ix_fato_meta_pago_data", "fato_meta_pago_diario", ["tenant_id", "data_key"])

    # ============================================================
    # FATO 3 — FUNIL DIÁRIO (consolidado: impressão → clique → lead → WhatsApp → consulta)
    # ============================================================
    op.create_table(
        "fato_meta_funil_diario",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("data_key", sa.Integer(), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        # 5 etapas do funil
        sa.Column("etapa1_impressoes", sa.Integer(), nullable=True),
        sa.Column("etapa2_cliques", sa.Integer(), nullable=True),
        sa.Column("etapa3_leads", sa.Integer(), nullable=True),
        sa.Column("etapa4_conversas_whatsapp", sa.Integer(), nullable=True),
        sa.Column("etapa5_consultas_agendadas", sa.Integer(), nullable=True),
        sa.Column("etapa6_consultas_realizadas", sa.Integer(), nullable=True),
        # Taxas
        sa.Column("taxa_clique_pct", sa.Numeric(7, 4), nullable=True),  # cliques/impressões
        sa.Column("taxa_lead_pct", sa.Numeric(7, 4), nullable=True),    # leads/cliques
        sa.Column("taxa_wpp_pct", sa.Numeric(7, 4), nullable=True),     # whatsapp/leads
        sa.Column("taxa_agenda_pct", sa.Numeric(7, 4), nullable=True),  # agenda/whatsapp
        sa.Column("taxa_consulta_pct", sa.Numeric(7, 4), nullable=True),# consulta/agenda
        # Investimento e ROI
        sa.Column("investimento", sa.Numeric(15, 2), nullable=True),
        sa.Column("cpa_consulta", sa.Numeric(15, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "data_referencia", name="uk_fato_meta_funil_dia"),
    )
    op.create_index("ix_fato_meta_funil_data", "fato_meta_funil_diario", ["tenant_id", "data_key"])

    # ============================================================
    # FATO 4 — COMENTÁRIO (cada um com flags)
    # ============================================================
    op.create_table(
        "fato_meta_comentario",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("comentario_external_id", sa.String(128), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=True),
        sa.Column("data_key", sa.Integer(), nullable=False),
        sa.Column("commented_at", sa.DateTime(), nullable=True),
        sa.Column("autor_username", sa.String(128), nullable=True),
        # Classificação IA (11 colunas finais)
        sa.Column("sentimento", sa.String(16), nullable=True),
        sa.Column("lead_quente_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("depoimento_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("duvida_clinica_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("objecao_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reclamacao_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("procedimento_mencionado", sa.String(64), nullable=True),
        sa.Column("urgencia_atendimento", sa.String(16), nullable=True),
        sa.Column("requer_resposta_humana", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("respondido_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("horas_para_resposta", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["dim_post_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "comentario_external_id", name="uk_fato_meta_coment_external"),
    )
    op.create_index("ix_fato_meta_coment_data", "fato_meta_comentario", ["tenant_id", "data_key"])
    op.create_index("ix_fato_meta_coment_lead_quente", "fato_meta_comentario", ["tenant_id", "lead_quente_flag", "respondido_flag"])

    # ============================================================
    # FATO 5 — LEAD JORNADA (lead → conversa → consulta → consultou)
    # cruza com fato_agenda (Clinicorp) via patient_id
    # ============================================================
    op.create_table(
        "fato_meta_lead_jornada",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("data_key", sa.Integer(), nullable=False),
        sa.Column("lead_date", sa.Date(), nullable=False),
        sa.Column("primeira_conversa_at", sa.DateTime(), nullable=True),
        sa.Column("primeira_consulta_agendada_at", sa.DateTime(), nullable=True),
        sa.Column("primeira_consulta_realizada_at", sa.DateTime(), nullable=True),
        # Tempos de jornada (em horas/dias)
        sa.Column("horas_ate_primeira_conversa", sa.Integer(), nullable=True),
        sa.Column("dias_ate_primeira_consulta", sa.Integer(), nullable=True),
        # Flags
        sa.Column("virou_paciente_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("realizou_consulta_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("realizou_procedimento_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        # Cruzamento Clinicorp
        sa.Column("patient_id", sa.BigInteger(), nullable=True),
        sa.Column("campanha_id", sa.BigInteger(), nullable=True),
        # ROI
        sa.Column("receita_gerada", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["dim_lead_meta.id"]),
        sa.ForeignKeyConstraint(["campanha_id"], ["dim_campanha_meta.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "lead_id", name="uk_fato_meta_lead_jorn"),
    )
    op.create_index("ix_fato_meta_lead_jorn_data", "fato_meta_lead_jornada", ["tenant_id", "data_key"])
    op.create_index("ix_fato_meta_lead_jorn_virou", "fato_meta_lead_jornada", ["tenant_id", "virou_paciente_flag"])


def downgrade() -> None:
    op.drop_table("fato_meta_lead_jornada")
    op.drop_table("fato_meta_comentario")
    op.drop_table("fato_meta_funil_diario")
    op.drop_table("fato_meta_pago_diario")
    op.drop_table("fato_meta_organico_diario")
    op.drop_table("dim_lead_meta")
    op.drop_table("dim_post_meta")
    op.drop_table("dim_campanha_meta")
    op.drop_table("dim_canal_meta")
