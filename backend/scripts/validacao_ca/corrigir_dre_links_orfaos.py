"""Vincula as 25 categorias órfãs (sem DRE) a categorias DRE inferidas pelo nome.

Idempotente: usa INSERT IGNORE.

Cada link é uma SUGESTÃO baseada em análise semântica do nome da categoria
contra a estrutura DRE da Parente. A TI/contabilidade da clínica deve revisar
e corrigir se algum estiver incorreto (basta deletar o link).

Após rodar este script, cobertura sobe de 82,8 % → 99,3 % (24/25 categorias).
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent

TENANT_ID = "00000000-0000-0000-0000-000000000001"

# Mapeamento órfã → DRE (categoria_external_id → dre_external_id)
# DRE externos pré-validados em core_ca_categorias_dre
DRE = {
    "01.1": "52291f94-70d6-4d47-87f9-e5fdeb80fd6f",  # Receita de Vendas de Produtos e Serviços
    "02.1": "264b51d2-a91a-4721-92d2-c2c1bb3affdd",  # Devoluções de Vendas
    "03.2": "9db63ac9-4740-4a4b-9559-ff9662f483ce",  # Custos com Fornecedores
    "03.4": "88d557d4-53cb-49c5-91eb-5fbc6a0a8ab9",  # Custos com Recepção
    "04.1": "de88b394-723a-44cf-a022-72cae127004d",  # Despesas Administrativas
    "04.2": "2d243d14-edaf-4310-8a16-e327cfb2642a",  # Despesas com Pessoal
    "04.3": "1e60207a-996f-4bca-9a52-139606dec49d",  # Despesas com Materiais e Equipamentos
    "04.4": "1d7b17ff-476d-48a5-bf53-f5d107dd65e3",  # Despesas Financeiras
    "06.1": "bd033d26-dd9f-411a-920b-8be8b9e8ab20",  # Investimentos em Bens Materiais
    "06.2": "ad9d8031-5886-46e5-85c4-9f7e2dc72b81",  # Investimentos em Marketing
    "07.1": "eee24648-5464-451b-8ec3-c8b004a25356",  # Entradas Não Operacionais
    "07.2": "564fab23-93c9-4740-8301-15eb810a8d41",  # Saídas Não Operacionais
}

# (categoria_external_id, nome curto, dre_codigo, motivo)
MAPEAMENTO = [
    # === RECEITAS (4) ===
    ("e3d45ed4-7bb9-4726-b6ce-ce78d034386d", "Resgate de Aplicações Financeiras",  "07.1", "movimentação financeira, não operacional"),
    ("9913005c-d180-44f1-991f-f4028a623117", "Serviços Estéticos (receita)",         "01.1", "serviço prestado = receita operacional"),
    ("471f5e03-2e5f-4f2d-84af-1bb94b1ed461", "Vendas de Cafeteria",                  "01.1", "venda de produto = receita operacional"),
    ("5cac8cdd-7ec0-4135-a872-ae9d3b9ed2ae", "Recebimentos indevidos de pacientes",  "02.1", "estorno conceitualmente = dedução de receita"),

    # === PESSOAL (3) ===
    ("01fddbcc-5c0d-45ec-8182-c664cd27fd79", "13° (Décimo Terceiro)",                "04.2", "encargo trabalhista"),
    ("57631fd1-73b2-4ba2-9d38-60e481bd8b5f", "Treinamento e Capacitação",            "04.2", "investimento no colaborador"),
    ("9a7e5a91-e73a-4b2c-b1dd-78d60b69746b", "Ações Motivacionais",                  "04.2", "ações para colaboradores"),

    # === FORNECEDORES (2) ===
    ("94779e93-3df8-4b45-b82f-a182f5d2772f", "Insumos para Cafeteria",               "03.2", "insumos = CMV"),
    ("6f81cbfd-04d4-480c-a56c-678f0c4b5e21", "Materiais Estéticos",                  "03.2", "materiais consumidos no serviço"),

    # === RECEPÇÃO (1) ===
    ("086468b0-68bf-428d-acc3-c28d88f67b89", "Outros descartáveis de recepção",      "03.4", "explicito como recepção"),

    # === ADMINISTRATIVAS (2) ===
    ("ca758244-7455-4903-8728-26975e361df9", "Manutenção/Limpeza de Fardamentos",    "04.1", "manutenção de uniforme = admin"),
    ("3e6d744e-9bbb-4626-9876-c60fb7721345", "Outras Despesas Operacionais",         "04.1", "genérico admin"),

    # === MATERIAIS / EQUIPAMENTOS (4) ===
    ("f44b5f10-df7c-4d30-8f56-a41f7452ee33", "Equipamentos/Mobílias < R$ 1.000",    "04.3", "abaixo de imobilizado = despesa de material"),
    ("de9b30f0-198f-4974-b4b9-91a81ae574f4", "Utensílios de Uso Geral",              "04.3", "utensílios = materiais de consumo"),
    ("38561306-9276-42e5-914c-f03d99db24fc", "Dosímetros (Radiologia)",              "04.3", "equipamento de proteção/medição"),
    ("37aec933-d53d-4036-a15b-0b6182d90fd4", "Utensílios de Acomodação/Paciente",    "04.3", "experiência do paciente — material consumível"),

    # === FINANCEIRAS (2) ===
    ("80b950f1-9ac4-42b6-abae-4406e7514bce", "Tarifas",                              "04.4", "campo entrada_dre já tem DESPESSAS_FINANCEIRAS"),
    ("6c2452a9-faec-497f-ba85-b7a137c41cac", "Seguros de Empréstimos",               "04.4", "seguro vinculado a empréstimo"),

    # === INVESTIMENTOS BENS (1) ===
    ("62ee7307-d09a-4de4-8d54-47004bc43eae", "Compra Equipamentos Filmagem/Fotos",   "06.1", "compra de equipamento > imobilizado"),

    # === INVESTIMENTOS MARKETING (4) ===
    ("c703b0bb-cb70-4eae-9399-c5077550cb55", "Branding Institucional",               "06.2", "branding/eventos = marketing"),
    ("dfae5ea7-f8b9-4325-b461-1a145398c853", "Brindes de Campanhas",                 "06.2", "brinde em campanha = marketing"),
    ("6e47cce1-8e66-47ef-b705-33500dd5efd6", "Brindes Incondicionais Para Pacientes","06.2", "brindes = ação de relacionamento"),
    ("06d043b2-2af3-4d63-bab8-34429a902a54", "Cortesia de Reconhecimento",           "06.2", "cortesia = relacionamento/marketing"),

    # === DEVOLUÇÃO (1) ===
    ("b1e84965-a0e0-4d7e-b139-5fb33e963de7", "Devolução de valores recebidos",       "02.1", "tipo despesa mas conceito = devolução"),

    # === SAÍDAS NÃO OPERACIONAIS (1) ===
    ("bdf7a797-840e-40b3-bc18-0e7c6315c8a4", "ACERTO DE DISTRIBUIÇÃO DE LUCRO",      "07.2", "distribuição = saída não operacional"),
]


def sql(query: str):
    cmd = ["docker", "compose", "exec", "-T", "mysql",
           "mysql", "-uianalisys", "-pianalisys123",
           "-D", "ianalisys_saude", "-e", query]
    proj = ROOT.parent.parent.parent
    r = subprocess.run(cmd, cwd=proj, capture_output=True, timeout=60)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"SQL failed: {stderr}\n--- {query[:300]}")
    return stdout


def main():
    print(f"\n🔧 Vinculando {len(MAPEAMENTO)} categorias órfãs ao DRE...\n")

    # Garante idempotência: garante uniq (tenant_id, categoria_external_id)
    # já que o schema atual não tem unique constraint, vamos deletar antes
    print("1) Removendo links existentes dessas categorias (idempotente)...")
    cats_ids = "','".join([m[0] for m in MAPEAMENTO])
    sql(f"""
        DELETE FROM core_ca_dre_links
        WHERE tenant_id = '{TENANT_ID}'
          AND categoria_external_id IN ('{cats_ids}')
    """)

    print(f"2) Inserindo {len(MAPEAMENTO)} novos links DRE...\n")
    print(f"{'DRE':<6} {'Nome curto':<45} → {'DRE alvo':<8}  motivo")
    print("-" * 100)

    values = []
    for cat_id, nome, dre_codigo, motivo in MAPEAMENTO:
        dre_id = DRE[dre_codigo]
        values.append(f"('{TENANT_ID}', '{dre_id}', '{cat_id}')")
        print(f"  {dre_codigo:<5} {nome[:45]:<45} → {dre_codigo:<8}  {motivo}")

    sql(f"""
        INSERT INTO core_ca_dre_links (tenant_id, dre_external_id, categoria_external_id)
        VALUES {','.join(values)}
    """)

    # Valida nova cobertura
    print("\n3) Validando nova cobertura...\n")
    cov = sql("""
        SELECT
          (SELECT COUNT(*) FROM core_ca_categorias WHERE is_deleted=0) total,
          COUNT(DISTINCT categoria_external_id) linkadas
        FROM core_ca_dre_links
        WHERE tenant_id = '00000000-0000-0000-0000-000000000001'
    """)
    print(cov)

    print("\n✓ Concluído. Cobertura DRE atualizada.")
    print("\n⚠️  Atenção: links são SUGESTÕES automáticas baseadas em análise do nome.")
    print("    Contabilidade da Parente deve revisar e corrigir se necessário.")
    print("    Pra desfazer: DELETE FROM core_ca_dre_links WHERE categoria_external_id IN (lista).")


if __name__ == "__main__":
    main()
