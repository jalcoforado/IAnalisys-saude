"""rbac permissions and role_permissions matrix

Cria catálogo de permissions granulares e matriz role x permission por
tenant (cada tenant pode ter sua própria matriz).

Tambêm adiciona coluna `purpose` em `password_reset_tokens` para
reaproveitar a tabela no fluxo de convite de usuários (purpose='invite'
muda só o template de email, consumo do token usa o mesmo endpoint).

Seed:
- 22 permissions em 8 módulos (dashboard, pacientes, agenda, clinico,
  financeiro, sync, usuarios, empresa, ia)
- Matriz default das 6 roles pro tenant existente (Parente Odontologia,
  id=00000000-0000-0000-0000-000000000001)

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Catálogo inicial — 22 permissions em 8 módulos
# (code, module, label, description)
# ---------------------------------------------------------------------------
PERMISSIONS = [
    # dashboard
    ("dashboard.read",           "dashboard",  "Ver dashboards",                 "Acesso ao dashboard executivo e visões agregadas"),
    # pacientes
    ("pacientes.read",           "pacientes",  "Ver pacientes",                  "Listar e consultar dados de pacientes"),
    ("pacientes.write",          "pacientes",  "Criar/editar pacientes",         "Cadastrar e atualizar pacientes"),
    ("pacientes.export",         "pacientes",  "Exportar pacientes",             "Baixar lista de pacientes em planilha"),
    # agenda
    ("agenda.read",              "agenda",     "Ver agenda",                     "Consultar agendamentos"),
    ("agenda.write",             "agenda",     "Editar agenda",                  "Criar e alterar agendamentos"),
    # clinico
    ("clinico.read",             "clinico",    "Ver prontuário",                 "Consultar histórico clínico do paciente"),
    ("clinico.write",            "clinico",    "Editar prontuário",              "Registrar e alterar informações clínicas"),
    # financeiro
    ("financeiro.read",          "financeiro", "Ver financeiro",                 "Consultar receitas, despesas e indicadores financeiros"),
    ("financeiro.write",         "financeiro", "Editar financeiro",              "Lançar e alterar receitas, despesas e cobranças"),
    ("financeiro.export",        "financeiro", "Exportar financeiro",            "Baixar relatórios financeiros"),
    # sync / analytics
    ("sync.run",                 "sync",       "Rodar sincronização",            "Disparar sync com Clinicorp/Conta Azul"),
    ("analytics.rebuild",        "sync",       "Reconstruir analytics",          "Reconstruir camadas CORE e ANALYTICS"),
    # usuarios
    ("usuarios.read",            "usuarios",   "Ver usuários",                   "Listar usuários do tenant"),
    ("usuarios.invite",          "usuarios",   "Convidar usuários",              "Criar novo usuário e enviar convite por email"),
    ("usuarios.edit",            "usuarios",   "Editar usuários",                "Alterar nome, role ou status de usuários"),
    ("usuarios.deactivate",      "usuarios",   "Desativar usuários",             "Inativar acesso de um usuário"),
    # empresa
    ("empresa.settings.read",    "empresa",    "Ver configurações da empresa",   "Consultar identidade visual e dados da empresa"),
    ("empresa.settings.write",   "empresa",    "Editar configurações da empresa","Editar identidade visual e dados da empresa"),
    ("empresa.permissions.manage","empresa",   "Gerenciar permissões",           "Editar matriz de roles x permissões"),
    # ia
    ("ia.use",                   "ia",         "Usar assistente IA",             "Fazer perguntas ao assistente IA"),
    ("ia.config",                "ia",         "Configurar IA",                  "Editar prompts, limites e controle de tokens"),
]


# ---------------------------------------------------------------------------
# Matriz default — código → conjunto de codes que a role recebe
# saas_admin: bypass total no código, mas seedamos todas pra consistência
# tenant_admin: todas
# manager: tudo, exceto operações administrativas e técnicas
# financial: dashboard + financeiro + pacientes (read/export) + IA básica
# commercial: dashboard + pacientes/agenda + IA básica
# operations: pacientes + agenda + clinico (back-office sem visão de receita)
# ---------------------------------------------------------------------------
ALL_CODES = [c for c, _, _, _ in PERMISSIONS]

DEFAULT_MATRIX = {
    "saas_admin":   set(ALL_CODES),
    "tenant_admin": set(ALL_CODES),
    "manager": {
        "dashboard.read",
        "pacientes.read", "pacientes.write", "pacientes.export",
        "agenda.read", "agenda.write",
        "clinico.read",
        "financeiro.read", "financeiro.export",
        "usuarios.read",
        "empresa.settings.read",
        "ia.use",
    },
    "financial": {
        "dashboard.read",
        "pacientes.read", "pacientes.export",
        "financeiro.read", "financeiro.write", "financeiro.export",
        "empresa.settings.read",
        "ia.use",
    },
    "commercial": {
        "dashboard.read",
        "pacientes.read", "pacientes.write", "pacientes.export",
        "agenda.read", "agenda.write",
        "empresa.settings.read",
        "ia.use",
    },
    "operations": {
        "pacientes.read", "pacientes.write",
        "agenda.read", "agenda.write",
        "clinico.read", "clinico.write",
    },
}


# Tenant existente (Parente Odontologia) — seed inicial da matriz
PARENTE_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # 1) Catálogo de permissions
    op.create_table(
        "permissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("module", sa.String(40), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])

    # 2) Matriz role x permission (por tenant — cada tenant tem sua matriz)
    op.create_table(
        "role_permissions",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "role_id", "permission_id", name="pk_role_permissions"),
    )
    op.create_index("ix_role_permissions_role", "role_permissions", ["tenant_id", "role_id"])

    # 3) Coluna purpose em password_reset_tokens (reaproveita p/ convite)
    op.add_column(
        "password_reset_tokens",
        sa.Column("purpose", sa.String(20), nullable=False, server_default="reset"),
    )

    # 4) Seed — catálogo de permissions
    op.execute(
        "INSERT INTO permissions (id, code, module, label, description) VALUES\n"
        + ",\n".join(
            f"(UUID(), '{code}', '{module}', '{label}', '{description}')"
            for code, module, label, description in PERMISSIONS
        )
    )

    # 5) Seed — matriz default pro tenant Parente
    for role_name, codes in DEFAULT_MATRIX.items():
        if not codes:
            continue
        codes_sql = ", ".join(f"'{c}'" for c in codes)
        op.execute(
            f"""
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT '{PARENTE_TENANT_ID}', r.id, p.id
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.name = '{role_name}'
              AND p.code IN ({codes_sql})
            """
        )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "purpose")
    op.drop_index("ix_role_permissions_role", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_table("permissions")
