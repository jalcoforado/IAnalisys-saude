"""contaazul_tokens: identificação da empresa conectada

Adiciona 5 colunas ao `contaazul_tokens` populadas no callback OAuth via
GET /v1/pessoas/conta-conectada — permitem exibir na UI qual empresa CA
está conectada e amarrar visualmente o token ao tenant correto.

Todas nullable: tokens existentes ficam como NULL; novo OAuth popula.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contaazul_tokens", sa.Column("empresa_documento", sa.String(32), nullable=True))
    op.add_column("contaazul_tokens", sa.Column("empresa_razao_social", sa.String(255), nullable=True))
    op.add_column("contaazul_tokens", sa.Column("empresa_nome_fantasia", sa.String(255), nullable=True))
    op.add_column("contaazul_tokens", sa.Column("empresa_data_fundacao", sa.Date(), nullable=True))
    op.add_column("contaazul_tokens", sa.Column("empresa_email", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("contaazul_tokens", "empresa_email")
    op.drop_column("contaazul_tokens", "empresa_data_fundacao")
    op.drop_column("contaazul_tokens", "empresa_nome_fantasia")
    op.drop_column("contaazul_tokens", "empresa_razao_social")
    op.drop_column("contaazul_tokens", "empresa_documento")
