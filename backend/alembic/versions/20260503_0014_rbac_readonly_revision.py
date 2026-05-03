"""rbac catálogo revisado: sistema read-only

Decisão arquitetural (2026-05-03): IAnalisys Saúde é estritamente analítico.
Dados de pacientes/agenda/clinico/financeiro vêm sincronizados das APIs
Clinicorp e Conta Azul — nunca são editados aqui. Logo, permissions de
escrita nesses 4 módulos não fazem sentido.

Mudanças:
- Remove: pacientes.write, agenda.write, clinico.write, financeiro.write
- Adiciona: agenda.export (consistência com pacientes.export e financeiro.export)
- Replica agenda.export pra todas roles que já tinham agenda.read em qualquer tenant

Catálogo final: 19 codes em 8 módulos.

Permissions de escrita continuam existindo nos módulos administrativos:
- usuarios.{invite,edit,deactivate} — gestão de usuários
- empresa.settings.write — editar dados da empresa (logo, etc)
- empresa.permissions.manage — editar matriz role x permission
- sync.run / analytics.rebuild — disparar pipelines
- ia.config — configurar IA

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-03
"""
from alembic import op


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


WRITE_PERMS_TO_REMOVE = [
    "pacientes.write",
    "agenda.write",
    "clinico.write",
    "financeiro.write",
]


def upgrade() -> None:
    # 1) Adiciona agenda.export
    op.execute(
        """
        INSERT INTO permissions (id, code, module, label, description)
        VALUES (UUID(), 'agenda.export', 'agenda', 'Exportar agenda',
                'Baixar lista de consultas em planilha')
        """
    )

    # 2) Toda role que tinha agenda.read em qualquer tenant ganha agenda.export
    op.execute(
        """
        INSERT IGNORE INTO role_permissions (tenant_id, role_id, permission_id)
        SELECT rp.tenant_id, rp.role_id, p_new.id
        FROM role_permissions rp
        JOIN permissions p_old ON p_old.id = rp.permission_id AND p_old.code = 'agenda.read'
        CROSS JOIN permissions p_new
        WHERE p_new.code = 'agenda.export'
        """
    )

    # 3) Remove os 4 codes write — FK CASCADE limpa role_permissions órfãs
    placeholders = ", ".join(f"'{c}'" for c in WRITE_PERMS_TO_REMOVE)
    op.execute(f"DELETE FROM permissions WHERE code IN ({placeholders})")


def downgrade() -> None:
    # Restaura os 4 writes (sem reaplicar matriz — defaults antigas)
    op.execute(
        """
        INSERT INTO permissions (id, code, module, label, description) VALUES
        (UUID(), 'pacientes.write',  'pacientes',  'Criar/editar pacientes',  'Cadastrar e atualizar pacientes'),
        (UUID(), 'agenda.write',     'agenda',     'Editar agenda',           'Criar e alterar agendamentos'),
        (UUID(), 'clinico.write',    'clinico',    'Editar prontuário',       'Registrar e alterar informações clínicas'),
        (UUID(), 'financeiro.write', 'financeiro', 'Editar financeiro',       'Lançar e alterar receitas, despesas e cobranças')
        """
    )

    # Remove agenda.export
    op.execute("DELETE FROM permissions WHERE code = 'agenda.export'")
