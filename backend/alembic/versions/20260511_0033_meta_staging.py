"""Meta Graph API — Sub-PR 21a/staging — Redes Sociais Parente Odontologia.

Cria 17 tabelas STAGING para armazenar audit trail JSON cru de:
  - Instagram orgânico: perfil, posts, post_insights, account_insights, stories, comments
  - Facebook orgânico:  page, posts, post_insights, page_insights
  - Meta Ads (pago):    campaigns, adsets, ads, insights_diario, leadgen_forms, leads
  - Pixel:              detalhes + eventos diários
  - Controle:           tokens por tenant

Padrão (igual Clinicorp/Conta Azul):
  - id BIGINT PK
  - tenant_id CHAR(36) FK
  - external_id (Meta ID)
  - data_referencia (DATE) onde aplicável (snapshots diários)
  - raw_data JSON
  - synced_at + sync_job_id
  - UNIQUE (tenant_id, external_id [+ data_referencia em snapshots diários])

Token table (stg_meta_tokens) armazena credenciais por tenant — multi-tenant
ready desde o início. App, Business, Page/IG/Ad/Pixel IDs + system_user_token
(criptografado em prod via secret_key).

Revision ID: 0033
Revises: 0032
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


# ============================================================
# Helpers
# ============================================================
def _staging_columns(extra=None, has_data_referencia=False):
    """Colunas padrão de toda tabela staging Meta."""
    cols = [
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
    ]
    if has_data_referencia:
        cols.append(sa.Column("data_referencia", sa.Date(), nullable=False))
    cols.extend([
        sa.Column("external_updated_at", sa.DateTime(), nullable=True),
        sa.Column("raw_data", mysql.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("sync_job_id", sa.BigInteger(), nullable=True),
    ])
    if extra:
        cols.extend(extra)
    cols.extend([
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    ])
    return cols


def _create_staging(table_name, extra_cols=None, has_data_referencia=False, extra_constraints=None):
    """Cria tabela staging com colunas padrão + UK por (tenant_id, external_id [+ data])."""
    cols = _staging_columns(extra_cols, has_data_referencia)
    uk_cols = ["tenant_id", "external_id"]
    if has_data_referencia:
        uk_cols.append("data_referencia")
    cols.append(sa.UniqueConstraint(*uk_cols, name=f"uk_{table_name}_external"))
    if extra_constraints:
        cols.extend(extra_constraints)
    op.create_table(table_name, *cols)
    op.create_index(f"ix_{table_name}_synced", table_name, ["tenant_id", "synced_at"])


def upgrade() -> None:
    # ============================================================
    # 0. TOKENS (multi-tenant credentials)
    # ============================================================
    op.create_table(
        "stg_meta_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", mysql.CHAR(36), nullable=False),
        # App
        sa.Column("app_id", sa.String(64), nullable=False),
        sa.Column("app_name", sa.String(128), nullable=True),
        # Business
        sa.Column("business_id", sa.String(64), nullable=True),
        sa.Column("business_name", sa.String(255), nullable=True),
        # System User Token (criptografado em prod via SECRET_KEY)
        sa.Column("system_user_id", sa.String(64), nullable=True),
        sa.Column("system_user_name", sa.String(128), nullable=True),
        sa.Column("system_user_token", sa.Text(), nullable=False),
        sa.Column("token_scopes", mysql.JSON(), nullable=True),
        sa.Column("token_validated_at", sa.DateTime(), nullable=True),
        sa.Column("token_is_valid", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        # IDs das contas vinculadas
        sa.Column("fb_page_id", sa.String(64), nullable=True),
        sa.Column("fb_page_name", sa.String(255), nullable=True),
        sa.Column("fb_page_token", sa.Text(), nullable=True),
        sa.Column("ig_account_id", sa.String(64), nullable=True),
        sa.Column("ig_username", sa.String(128), nullable=True),
        sa.Column("ad_account_id", sa.String(64), nullable=True),
        sa.Column("ad_account_authorized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("pixel_id", sa.String(64), nullable=True),
        sa.Column("pixel_last_fired_at", sa.DateTime(), nullable=True),
        # Operacional
        sa.Column("graph_api_version", sa.String(8), nullable=False, server_default=sa.text("'v19.0'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP"),
                  server_onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uk_stg_meta_tokens_tenant"),
    )

    # ============================================================
    # 1. INSTAGRAM ORGÂNICO
    # ============================================================
    # Perfil — snapshot diário
    _create_staging("stg_meta_ig_perfil", has_data_referencia=True)

    # Posts (mídia)
    _create_staging("stg_meta_ig_posts", extra_cols=[
        sa.Column("posted_at", sa.DateTime(), nullable=True),
    ])

    # Post insights — métricas por post (atualizadas com o tempo)
    _create_staging("stg_meta_ig_post_insights", has_data_referencia=True,
        extra_cols=[
            sa.Column("post_external_id", sa.String(128), nullable=False),
        ])

    # Account insights — métricas da conta por dia
    _create_staging("stg_meta_ig_account_insights", has_data_referencia=True,
        extra_cols=[
            sa.Column("metric_name", sa.String(64), nullable=False),
        ],
        extra_constraints=[])
    # Override UK (não usa external_id pra account_insights — usa data+metric)
    op.execute("ALTER TABLE stg_meta_ig_account_insights DROP INDEX uk_stg_meta_ig_account_insights_external")
    op.create_unique_constraint(
        "uk_stg_meta_ig_acc_ins",
        "stg_meta_ig_account_insights",
        ["tenant_id", "data_referencia", "metric_name"]
    )

    # Stories
    _create_staging("stg_meta_ig_stories", extra_cols=[
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    ])

    # Comments
    _create_staging("stg_meta_ig_comments", extra_cols=[
        sa.Column("post_external_id", sa.String(128), nullable=False),
        sa.Column("commented_at", sa.DateTime(), nullable=True),
    ])

    # ============================================================
    # 2. FACEBOOK ORGÂNICO
    # ============================================================
    _create_staging("stg_meta_fb_page", has_data_referencia=True)

    _create_staging("stg_meta_fb_posts", extra_cols=[
        sa.Column("posted_at", sa.DateTime(), nullable=True),
    ])

    _create_staging("stg_meta_fb_post_insights", has_data_referencia=True,
        extra_cols=[
            sa.Column("post_external_id", sa.String(128), nullable=False),
        ])

    _create_staging("stg_meta_fb_page_insights", has_data_referencia=True,
        extra_cols=[
            sa.Column("metric_name", sa.String(64), nullable=False),
        ])
    op.execute("ALTER TABLE stg_meta_fb_page_insights DROP INDEX uk_stg_meta_fb_page_insights_external")
    op.create_unique_constraint(
        "uk_stg_meta_fb_page_ins",
        "stg_meta_fb_page_insights",
        ["tenant_id", "data_referencia", "metric_name"]
    )

    # ============================================================
    # 3. ADS (PAGO)
    # ============================================================
    _create_staging("stg_meta_ads_campaigns")
    _create_staging("stg_meta_ads_adsets", extra_cols=[
        sa.Column("campaign_external_id", sa.String(128), nullable=True),
    ])
    _create_staging("stg_meta_ads_ads", extra_cols=[
        sa.Column("adset_external_id", sa.String(128), nullable=True),
    ])

    # Insights diários — granularidade ad/dia
    _create_staging("stg_meta_ads_insights_diario", has_data_referencia=True,
        extra_cols=[
            sa.Column("ad_external_id", sa.String(128), nullable=True),
            sa.Column("adset_external_id", sa.String(128), nullable=True),
            sa.Column("campaign_external_id", sa.String(128), nullable=True),
            sa.Column("level", sa.String(16), nullable=False, server_default=sa.text("'ad'")),
        ])
    op.execute("ALTER TABLE stg_meta_ads_insights_diario DROP INDEX uk_stg_meta_ads_insights_diario_external")
    op.create_unique_constraint(
        "uk_stg_meta_ads_ins_diario",
        "stg_meta_ads_insights_diario",
        ["tenant_id", "external_id", "data_referencia", "level"]
    )

    # Leadgen forms (templates de captura)
    _create_staging("stg_meta_ads_leadgen_forms")

    # Leads (capturados pelos forms)
    _create_staging("stg_meta_ads_leads", extra_cols=[
        sa.Column("form_external_id", sa.String(128), nullable=True),
        sa.Column("ad_external_id", sa.String(128), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
    ])

    # ============================================================
    # 4. PIXEL
    # ============================================================
    _create_staging("stg_meta_pixel", has_data_referencia=True)

    _create_staging("stg_meta_pixel_eventos_diarios", has_data_referencia=True,
        extra_cols=[
            sa.Column("event_name", sa.String(64), nullable=False),
            sa.Column("event_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        ])
    op.execute("ALTER TABLE stg_meta_pixel_eventos_diarios DROP INDEX uk_stg_meta_pixel_eventos_diarios_external")
    op.create_unique_constraint(
        "uk_stg_meta_pixel_ev_diario",
        "stg_meta_pixel_eventos_diarios",
        ["tenant_id", "data_referencia", "event_name"]
    )


def downgrade() -> None:
    op.drop_table("stg_meta_pixel_eventos_diarios")
    op.drop_table("stg_meta_pixel")
    op.drop_table("stg_meta_ads_leads")
    op.drop_table("stg_meta_ads_leadgen_forms")
    op.drop_table("stg_meta_ads_insights_diario")
    op.drop_table("stg_meta_ads_ads")
    op.drop_table("stg_meta_ads_adsets")
    op.drop_table("stg_meta_ads_campaigns")
    op.drop_table("stg_meta_fb_page_insights")
    op.drop_table("stg_meta_fb_post_insights")
    op.drop_table("stg_meta_fb_posts")
    op.drop_table("stg_meta_fb_page")
    op.drop_table("stg_meta_ig_comments")
    op.drop_table("stg_meta_ig_stories")
    op.drop_table("stg_meta_ig_account_insights")
    op.drop_table("stg_meta_ig_post_insights")
    op.drop_table("stg_meta_ig_posts")
    op.drop_table("stg_meta_ig_perfil")
    op.drop_table("stg_meta_tokens")
