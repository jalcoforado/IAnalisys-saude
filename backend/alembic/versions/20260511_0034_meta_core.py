"""Meta — Sub-PR 21a/core — Camada CORE limpa, relacional.

Cria 11 tabelas core a partir do staging:
  - core_meta_canais        (lookup IG/FB/Ads/Pixel/Email)
  - core_meta_perfis        (snapshot consolidado tenant/canal/data)
  - core_meta_pixel         (config + last_fired)
  - core_meta_posts         (unificado IG+FB, header)
  - core_meta_post_metricas_diarias  (métricas por post/dia)
  - core_meta_comentarios   (com flags de classificação IA)
  - core_meta_campanhas
  - core_meta_adsets
  - core_meta_ads
  - core_meta_ad_metricas_diarias    (performance por ad/dia)
  - core_meta_leads         (capturados via form; cruza com core_patients via fone/email)

Revision ID: 0034
Revises: 0033
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def _core_columns():
    """Colunas padrão de toda tabela core."""
    return [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    # ============================================================
    # 1. CANAIS (lookup)
    # ============================================================
    op.create_table(
        "core_meta_canais",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(16), nullable=False),
        sa.Column("nome", sa.String(64), nullable=False),
        sa.Column("descricao", sa.String(255), nullable=True),
        sa.Column("is_ativo", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo", name="uk_core_meta_canais_codigo"),
    )
    # Seed dos canais conhecidos
    op.execute("""
        INSERT INTO core_meta_canais (codigo, nome, descricao) VALUES
            ('IG',   'Instagram',     'Perfil Business Instagram'),
            ('FB',   'Facebook',      'Página oficial Facebook'),
            ('ADS',  'Meta Ads',      'Anúncios pagos via Business Manager'),
            ('PXL',  'Pixel',         'Rastreio de conversão no site'),
            ('LEAD', 'Lead Forms',    'Formulários de captura via ads')
    """)

    # ============================================================
    # 2. PERFIS (snapshot diário consolidado)
    # ============================================================
    op.create_table(
        "core_meta_perfis",
        *_core_columns(),
        sa.Column("canal_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("biografia", sa.Text(), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("profile_picture_url", sa.String(1000), nullable=True),
        sa.Column("seguidores", sa.Integer(), nullable=True),
        sa.Column("seguindo", sa.Integer(), nullable=True),
        sa.Column("total_posts", sa.Integer(), nullable=True),
        sa.Column("fan_count", sa.Integer(), nullable=True),  # FB: page likes
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("location_str", sa.String(255), nullable=True),
        sa.Column("verification_status", sa.String(32), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["canal_id"], ["core_meta_canais.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "canal_id", "data_referencia", name="uk_core_meta_perfis_dia"),
    )
    op.create_index("ix_core_meta_perfis_data", "core_meta_perfis", ["tenant_id", "data_referencia"])

    # ============================================================
    # 3. PIXEL
    # ============================================================
    op.create_table(
        "core_meta_pixel",
        *_core_columns(),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("data_criacao", sa.DateTime(), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(), nullable=True),
        sa.Column("is_unavailable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("dias_sem_disparar", sa.Integer(), nullable=True),
        sa.Column("owner_business_id", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_pixel_external"),
    )

    # ============================================================
    # 4. POSTS (unificado IG + FB)
    # ============================================================
    op.create_table(
        "core_meta_posts",
        *_core_columns(),
        sa.Column("canal_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("permalink", sa.String(1000), nullable=True),
        sa.Column("thumbnail_url", sa.String(1000), nullable=True),
        sa.Column("media_url", sa.String(1000), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("is_comment_enabled", sa.Boolean(), nullable=True),
        sa.Column("hashtags", mysql.JSON(), nullable=True),
        sa.Column("mentions", mysql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["canal_id"], ["core_meta_canais.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "canal_id", "external_id", name="uk_core_meta_posts_external"),
    )
    op.create_index("ix_core_meta_posts_posted", "core_meta_posts", ["tenant_id", "posted_at"])

    # ============================================================
    # 5. POST MÉTRICAS DIÁRIAS
    # ============================================================
    op.create_table(
        "core_meta_post_metricas_diarias",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("engagement", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=True),
        sa.Column("saves", sa.Integer(), nullable=True),
        sa.Column("video_views", sa.Integer(), nullable=True),
        sa.Column("video_avg_watch_time_sec", sa.Numeric(8, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["core_meta_posts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "post_id", "data_referencia", name="uk_core_meta_post_met_dia"),
    )
    op.create_index("ix_core_meta_post_met_data", "core_meta_post_metricas_diarias", ["tenant_id", "data_referencia"])

    # ============================================================
    # 6. COMENTÁRIOS (com flags IA — Pedro pediu 11 colunas)
    # ============================================================
    op.create_table(
        "core_meta_comentarios",
        *_core_columns(),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=True),
        sa.Column("post_external_id", sa.String(128), nullable=True),
        sa.Column("autor_username", sa.String(128), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("commented_at", sa.DateTime(), nullable=True),
        sa.Column("parent_external_id", sa.String(128), nullable=True),
        # Classificação IA (11 colunas finais aprovadas)
        sa.Column("sentimento", sa.Enum("positivo", "neutro", "negativo", name="sentimento_comentario"), nullable=True),
        sa.Column("lead_quente_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("depoimento_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("duvida_clinica_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("objecao_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reclamacao_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("procedimento_mencionado", sa.String(64), nullable=True),
        sa.Column("urgencia_atendimento", sa.Enum("alta", "media", "baixa", name="urgencia_comentario"), nullable=True),
        sa.Column("requer_resposta_humana", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("respondido_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("horas_para_resposta", sa.Integer(), nullable=True),
        sa.Column("classificacao_ia_modelo", sa.String(64), nullable=True),
        sa.Column("classificacao_ia_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["core_meta_posts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_coments_external"),
    )
    op.create_index("ix_core_meta_coments_commented", "core_meta_comentarios", ["tenant_id", "commented_at"])
    op.create_index("ix_core_meta_coments_lead_quente", "core_meta_comentarios", ["tenant_id", "lead_quente_flag"])

    # ============================================================
    # 7. CAMPANHAS (Ads)
    # ============================================================
    op.create_table(
        "core_meta_campanhas",
        *_core_columns(),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("effective_status", sa.String(32), nullable=True),
        sa.Column("objective", sa.String(64), nullable=True),
        sa.Column("daily_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("lifetime_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("stop_time", sa.DateTime(), nullable=True),
        sa.Column("procedimento_inferido", sa.String(64), nullable=True),  # IA detecta pelo nome
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_camp_external"),
    )

    # ============================================================
    # 8. ADSETS
    # ============================================================
    op.create_table(
        "core_meta_adsets",
        *_core_columns(),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("daily_budget", sa.Numeric(15, 2), nullable=True),
        sa.Column("optimization_goal", sa.String(64), nullable=True),
        sa.Column("targeting", mysql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["core_meta_campanhas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_adsets_external"),
    )

    # ============================================================
    # 9. ADS
    # ============================================================
    op.create_table(
        "core_meta_ads",
        *_core_columns(),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("adset_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("effective_status", sa.String(32), nullable=True),
        sa.Column("creative_id", sa.String(128), nullable=True),
        sa.Column("creative_thumbnail_url", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["adset_id"], ["core_meta_adsets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_ads_external"),
    )

    # ============================================================
    # 10. AD MÉTRICAS DIÁRIAS
    # ============================================================
    op.create_table(
        "core_meta_ad_metricas_diarias",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("ad_id", sa.BigInteger(), nullable=True),
        sa.Column("adset_id", sa.BigInteger(), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("level", sa.String(16), nullable=False, server_default=sa.text("'ad'")),  # ad/adset/campaign
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("ctr", sa.Numeric(7, 4), nullable=True),
        sa.Column("spend", sa.Numeric(15, 2), nullable=True),
        sa.Column("cpc", sa.Numeric(15, 4), nullable=True),
        sa.Column("cpm", sa.Numeric(15, 4), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Numeric(8, 4), nullable=True),
        # Actions (leads, conversas, etc.) — extraídos do `actions` array
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("conversas_whatsapp", sa.Integer(), nullable=True),
        sa.Column("link_clicks", sa.Integer(), nullable=True),
        sa.Column("video_views", sa.Integer(), nullable=True),
        sa.Column("actions_raw", mysql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["ad_id"], ["core_meta_ads.id"]),
        sa.ForeignKeyConstraint(["adset_id"], ["core_meta_adsets.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["core_meta_campanhas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "ad_id", "adset_id", "campaign_id", "data_referencia", "level",
                            name="uk_core_meta_ad_met_dia"),
    )
    op.create_index("ix_core_meta_ad_met_data", "core_meta_ad_metricas_diarias", ["tenant_id", "data_referencia"])

    # ============================================================
    # 11. LEADS (formulário Meta → cruza com pacientes)
    # ============================================================
    op.create_table(
        "core_meta_leads",
        *_core_columns(),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("form_external_id", sa.String(128), nullable=True),
        sa.Column("ad_external_id", sa.String(128), nullable=True),
        sa.Column("campaign_id", sa.BigInteger(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        # Dados extraídos do form
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telefone", sa.String(32), nullable=True),
        sa.Column("telefone_e164", sa.String(32), nullable=True),  # normalizado pra match
        sa.Column("cidade", sa.String(128), nullable=True),
        sa.Column("uf", sa.String(2), nullable=True),
        sa.Column("interesse_procedimento", sa.String(128), nullable=True),
        sa.Column("field_data_raw", mysql.JSON(), nullable=True),
        # Match com pacientes (cruzamento Clinicorp)
        sa.Column("patient_id", sa.BigInteger(), nullable=True),
        sa.Column("match_metodo", sa.String(32), nullable=True),  # 'telefone', 'email', 'nome'
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("matched_at", sa.DateTime(), nullable=True),
        # Operacional
        sa.Column("contato_iniciado_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),  # 'novo','em_contato','agendado','consultado','perdido'
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["campaign_id"], ["core_meta_campanhas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uk_core_meta_leads_external"),
    )
    op.create_index("ix_core_meta_leads_telefone", "core_meta_leads", ["tenant_id", "telefone_e164"])
    op.create_index("ix_core_meta_leads_email", "core_meta_leads", ["tenant_id", "email"])
    op.create_index("ix_core_meta_leads_captured", "core_meta_leads", ["tenant_id", "captured_at"])
    op.create_index("ix_core_meta_leads_patient", "core_meta_leads", ["tenant_id", "patient_id"])


def downgrade() -> None:
    op.drop_table("core_meta_leads")
    op.drop_table("core_meta_ad_metricas_diarias")
    op.drop_table("core_meta_ads")
    op.drop_table("core_meta_adsets")
    op.drop_table("core_meta_campanhas")
    op.drop_table("core_meta_comentarios")
    op.drop_table("core_meta_post_metricas_diarias")
    op.drop_table("core_meta_posts")
    op.drop_table("core_meta_pixel")
    op.drop_table("core_meta_perfis")
    op.drop_table("core_meta_canais")
