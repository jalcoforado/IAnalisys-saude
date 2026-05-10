"""Service do dashboard financeiro (CA / fato_caixa).

Lê apenas da camada ANALYTICS CA (fato_caixa + dim_categoria_ca + dim_centro_custo_ca).
Tudo agregado em SQL puro — multi-tenant via tenant_id.

KPIs:
- entradas / saídas / saldo líquido (do mês selecionado, valor pago realizado)
- a receber / a pagar (open balances)
- inadimplência % (vencidos receita / total receita)
- top 5 categorias receita + despesa
- distribuição por centro de custo (entradas vs saídas)
- mix por status (pago/em aberto/vencido)
- evolução 12 meses (entradas vs saídas)
"""
from __future__ import annotations

from typing import List

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import PeriodInfo
from app.schemas.financeiro import (
    CategoriaItem,
    CentroCustoItem,
    ConciliacaoBlock,
    ContaBancariaItem,
    ContaDestinoItem,
    DreBlock,
    DreGrupoItem,
    DreSubgrupoItem,
    FinanceiroEvolutionPoint,
    FinanceiroKpis,
    FinanceiroOverviewResponse,
    MetodoPagamentoItem,
    MetodosPagamentoBlock,
    SaldosBancariosBlock,
    StatusMixItem,
    TransferenciaFluxoItem,
    TransferenciasBlock,
)

_MONTH_NAMES_PT_FULL = (
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)
_MONTH_NAMES_PT_SHORT = (
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
)


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _period_info(year: int, month: int) -> PeriodInfo:
    return PeriodInfo(
        year=year,
        month=month,
        label=_ym_key(year, month),
        label_pt=f"{_MONTH_NAMES_PT_FULL[month]}/{year}",
    )


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ── KPIs principais ─────────────────────────────────────────────

async def _kpis_periodo(db: AsyncSession, tenant_id: str, ym: str) -> FinanceiroKpis:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_pago_rateado ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_pago_rateado ELSE 0 END), 0) AS saidas,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_em_aberto_rateado ELSE 0 END), 0) AS a_receber,
                COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_em_aberto_rateado ELSE 0 END), 0) AS a_pagar,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' AND is_vencido=1 THEN valor_em_aberto_rateado ELSE 0 END), 0) AS receita_vencida,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_rateado ELSE 0 END), 0) AS receita_total,
                COALESCE(SUM(CASE WHEN is_vencido=1 THEN 1 ELSE 0 END), 0) AS qtd_vencidas
            FROM fato_caixa
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    r = q.one()
    entradas = float(r.entradas or 0)
    saidas = float(r.saidas or 0)
    receita_vencida = float(r.receita_vencida or 0)
    receita_total = float(r.receita_total or 0)
    inad_pct = round((receita_vencida / receita_total) * 100, 2) if receita_total > 0 else 0.0

    # Encargos vêm de core_ca_baixas (apenas /parcelas/{id} traz juros/multa/desconto).
    # Filtra por data_vencimento pra alinhar com fato_caixa.year_month_key (que
    # é vencimento, não pagamento). Em ms sem baixa detalhada, retorna 0.
    q_enc = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='RECEITA'
                    THEN COALESCE(juros,0) + COALESCE(multa,0) - COALESCE(desconto,0)
                    ELSE 0 END), 0) AS enc_rec,
                COALESCE(SUM(CASE WHEN tipo='DESPESA'
                    THEN COALESCE(juros,0) + COALESCE(multa,0) - COALESCE(desconto,0)
                    ELSE 0 END), 0) AS enc_desp
            FROM core_ca_baixas
            WHERE tenant_id = :tid AND is_deleted = 0
              AND DATE_FORMAT(data_vencimento, '%Y-%m') = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    e = q_enc.one()
    encargos_entradas = round(float(e.enc_rec or 0), 2)
    encargos_saidas = round(float(e.enc_desp or 0), 2)

    return FinanceiroKpis(
        entradas=entradas,
        saidas=saidas,
        saldo_liquido=round(entradas - saidas, 2),
        a_receber=float(r.a_receber or 0),
        a_pagar=float(r.a_pagar or 0),
        inadimplencia_pct=inad_pct,
        qtd_parcelas_vencidas=int(r.qtd_vencidas or 0),
        encargos_entradas=encargos_entradas,
        encargos_saidas=encargos_saidas,
    )


# ── Top categorias ──────────────────────────────────────────────

async def _top_categorias(
    db: AsyncSession, tenant_id: str, ym: str, tipo: str, limit: int = 5,
) -> List[CategoriaItem]:
    """tipo = 'RECEITA' | 'DESPESA'"""
    q = await db.execute(
        text("""
            SELECT
                fc.categoria_external_id,
                MAX(dc.nome) AS nome,
                SUM(fc.valor_pago_rateado) AS total
            FROM fato_caixa fc
            LEFT JOIN dim_categoria_ca dc
                ON dc.tenant_id = fc.tenant_id
               AND dc.external_id = fc.categoria_external_id
            WHERE fc.tenant_id = :tid
              AND fc.year_month_key = :ym
              AND fc.tipo = :tipo
              AND fc.is_pago = 1
            GROUP BY fc.categoria_external_id
            ORDER BY total DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "tipo": tipo, "lim": limit},
    )
    rows = q.all()
    grand = sum(float(r.total or 0) for r in rows) or 1.0
    return [
        CategoriaItem(
            external_id=r.categoria_external_id,
            nome=r.nome or "Sem categoria",
            total=float(r.total or 0),
            pct=round((float(r.total or 0) / grand) * 100, 2),
        )
        for r in rows
    ]


# ── Centros de custo ────────────────────────────────────────────

async def _centros_custo(db: AsyncSession, tenant_id: str, ym: str) -> List[CentroCustoItem]:
    q = await db.execute(
        text("""
            SELECT
                fc.centro_custo_external_id,
                MAX(dcc.nome) AS nome,
                COALESCE(SUM(CASE WHEN fc.tipo='RECEITA' THEN fc.valor_pago_rateado ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN fc.tipo='DESPESA' THEN fc.valor_pago_rateado ELSE 0 END), 0) AS saidas
            FROM fato_caixa fc
            LEFT JOIN dim_centro_custo_ca dcc
                ON dcc.tenant_id = fc.tenant_id
               AND dcc.external_id = fc.centro_custo_external_id
            WHERE fc.tenant_id = :tid
              AND fc.year_month_key = :ym
              AND fc.is_pago = 1
            GROUP BY fc.centro_custo_external_id
            ORDER BY (entradas + saidas) DESC
        """),
        {"tid": tenant_id, "ym": ym},
    )
    return [
        CentroCustoItem(
            external_id=r.centro_custo_external_id,
            nome=r.nome or "Sem centro de custo",
            entradas=float(r.entradas or 0),
            saidas=float(r.saidas or 0),
            saldo=round(float(r.entradas or 0) - float(r.saidas or 0), 2),
        )
        for r in q.all()
    ]


# ── Mix por status ──────────────────────────────────────────────

async def _status_mix(db: AsyncSession, tenant_id: str, ym: str) -> List[StatusMixItem]:
    q = await db.execute(
        text("""
            SELECT status, COUNT(*) AS qtd, COALESCE(SUM(valor_rateado), 0) AS total
            FROM (
                SELECT
                    CASE
                        WHEN is_pago = 1 THEN 'pago'
                        WHEN is_vencido = 1 THEN 'vencido'
                        ELSE 'em_aberto'
                    END AS status,
                    valor_rateado
                FROM fato_caixa
                WHERE tenant_id = :tid AND year_month_key = :ym
            ) sub
            GROUP BY status
            ORDER BY FIELD(status, 'pago', 'em_aberto', 'vencido')
        """),
        {"tid": tenant_id, "ym": ym},
    )
    labels = {"pago": "Pago", "em_aberto": "Em aberto", "vencido": "Vencido"}
    return [
        StatusMixItem(
            status=r.status,
            label_pt=labels.get(r.status, r.status),
            qtd=int(r.qtd or 0),
            total=float(r.total or 0),
        )
        for r in q.all()
    ]


# ── Evolução 12 meses ───────────────────────────────────────────

async def _evolution(db: AsyncSession, tenant_id: str, end_year: int, end_month: int) -> List[FinanceiroEvolutionPoint]:
    months: list[tuple[int, int]] = []
    y, m = end_year, end_month
    for _ in range(12):
        months.append((y, m))
        y, m = _previous_month(y, m)
    months.reverse()
    keys = [_ym_key(yy, mm) for yy, mm in months]

    stmt = text("""
        SELECT
            year_month_key,
            COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_pago_rateado ELSE 0 END), 0) AS entradas,
            COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_pago_rateado ELSE 0 END), 0) AS saidas
        FROM fato_caixa
        WHERE tenant_id = :tid AND year_month_key IN :keys
        GROUP BY year_month_key
    """).bindparams(bindparam("keys", expanding=True))
    q = await db.execute(stmt, {"tid": tenant_id, "keys": keys})
    by_key = {r.year_month_key: (float(r.entradas or 0), float(r.saidas or 0)) for r in q.all()}

    out: List[FinanceiroEvolutionPoint] = []
    for yy, mm in months:
        key = _ym_key(yy, mm)
        ent, sai = by_key.get(key, (0.0, 0.0))
        out.append(FinanceiroEvolutionPoint(
            year_month_key=key,
            label_pt=f"{_MONTH_NAMES_PT_SHORT[mm]}/{str(yy)[-2:]}",
            entradas=ent,
            saidas=sai,
            saldo=round(ent - sai, 2),
        ))
    return out


# ── Métodos pagamento + Conciliação (Onda 2) ────────────────────

# Tradução das chaves CA pra labels PT-BR (display only).
_METODO_PAGAMENTO_LABEL = {
    "PIX_PAGAMENTO_INSTANTANEO": "PIX",
    "PIX": "PIX",
    "BOLETO_BANCARIO": "Boleto",
    "BOLETO": "Boleto",
    "CARTAO_CREDITO": "Cartão de crédito",
    "CARTAO_DEBITO": "Cartão de débito",
    "DINHEIRO": "Dinheiro",
    "TRANSFERENCIA_BANCARIA": "Transferência",
    "DEBITO_AUTOMATICO": "Débito automático",
    "CHEQUE": "Cheque",
    "OUTRO": "Outros",
    "OUTROS": "Outros",
}


def _metodo_label(metodo: str | None) -> str:
    if not metodo:
        return "Sem método"
    return _METODO_PAGAMENTO_LABEL.get(metodo.upper(), metodo)


async def _metodos_pagamento(
    db: AsyncSession, tenant_id: str, ym: str,
) -> MetodosPagamentoBlock:
    """Distribuição "onde caiu o dinheiro" — só RECEITAS no mês.

    Usa core_ca_baixas (data_pagamento real, não vencimento).
    Calcula cobertura = % das parcelas pagas com vencimento no mês que já
    têm baixa detalhada — se baixa, mostra CTA pra rodar /sync/contaazul/baixas.
    """
    # 1. Distribuição por método (RECEITAS pagas no mês via baixa)
    q = await db.execute(
        text("""
            SELECT COALESCE(metodo_pagamento, 'OUTRO') AS metodo,
                   COUNT(*) AS qtd,
                   COALESCE(SUM(valor_pago), 0) AS total
            FROM core_ca_baixas
            WHERE tenant_id = :tid AND tipo = 'RECEITA' AND is_deleted = 0
              AND DATE_FORMAT(data_pagamento, '%Y-%m') = :ym
            GROUP BY metodo
            ORDER BY total DESC
        """),
        {"tid": tenant_id, "ym": ym},
    )
    rows = q.all()
    total_valor = sum(float(r.total or 0) for r in rows) or 1.0
    metodos = [
        MetodoPagamentoItem(
            metodo=r.metodo,
            label=_metodo_label(r.metodo),
            qtd_baixas=int(r.qtd or 0),
            valor_total=float(r.total or 0),
            pct_valor=round((float(r.total or 0) / total_valor) * 100, 2),
        )
        for r in rows
    ]
    qtd_total = sum(m.qtd_baixas for m in metodos)

    # 2. Cobertura: % das parcelas RECEITA pagas em fato_caixa (no mês) que
    # têm pelo menos 1 baixa detalhada em core_ca_baixas
    q_cov = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT fc.parcela_external_id) AS pagas_total,
                COUNT(DISTINCT CASE WHEN b.parcela_external_id IS NOT NULL
                    THEN fc.parcela_external_id END) AS pagas_com_baixa
            FROM fato_caixa fc
            LEFT JOIN core_ca_baixas b
                ON b.tenant_id = fc.tenant_id
               AND b.parcela_external_id = fc.parcela_external_id
               AND b.is_deleted = 0
            WHERE fc.tenant_id = :tid
              AND fc.year_month_key = :ym
              AND fc.tipo = 'RECEITA'
              AND fc.is_pago = 1
        """),
        {"tid": tenant_id, "ym": ym},
    )
    cov = q_cov.one()
    pagas_total = int(cov.pagas_total or 0)
    pagas_com_baixa = int(cov.pagas_com_baixa or 0)
    cobertura_pct = round((pagas_com_baixa / pagas_total) * 100, 1) if pagas_total > 0 else 0.0
    pendentes = max(pagas_total - pagas_com_baixa, 0)

    return MetodosPagamentoBlock(
        metodos=metodos,
        qtd_total=qtd_total,
        valor_total=round(sum(m.valor_total for m in metodos), 2),
        cobertura_pct=cobertura_pct,
        pendentes_detalhamento=pendentes,
    )


async def _conciliacao(
    db: AsyncSession, tenant_id: str, ym: str,
) -> ConciliacaoBlock:
    """% das baixas reconciliadas com extrato bancário CA + top contas destino."""
    # 1. Totais de conciliação no mês
    q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN conciliado = 1 THEN 1 ELSE 0 END), 0) AS conciliadas,
                COALESCE(SUM(CASE WHEN conciliado = 1 THEN valor_pago ELSE 0 END), 0) AS valor_conc,
                COALESCE(SUM(CASE WHEN conciliado = 0 OR conciliado IS NULL THEN valor_pago ELSE 0 END), 0) AS valor_nao_conc
            FROM core_ca_baixas
            WHERE tenant_id = :tid AND is_deleted = 0
              AND DATE_FORMAT(data_pagamento, '%Y-%m') = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    r = q.one()
    total = int(r.total or 0)
    conc = int(r.conciliadas or 0)
    nao_conc = max(total - conc, 0)
    pct = round((conc / total) * 100, 1) if total > 0 else 0.0

    # 2. Top contas destino (RECEITA + DESPESA juntos pra ver onde dinheiro flui)
    q_contas = await db.execute(
        text("""
            SELECT conta_financeira_external_id, MAX(conta_financeira_nome) AS nome,
                   MAX(conta_financeira_banco) AS banco,
                   COUNT(*) AS qtd, SUM(valor_pago) AS total
            FROM core_ca_baixas
            WHERE tenant_id = :tid AND is_deleted = 0
              AND DATE_FORMAT(data_pagamento, '%Y-%m') = :ym
              AND conta_financeira_external_id IS NOT NULL
            GROUP BY conta_financeira_external_id
            ORDER BY total DESC
            LIMIT 8
        """),
        {"tid": tenant_id, "ym": ym},
    )
    contas_rows = q_contas.all()
    grand = sum(float(c.total or 0) for c in contas_rows) or 1.0
    contas = [
        ContaDestinoItem(
            external_id=c.conta_financeira_external_id,
            nome=c.nome or "(sem nome)",
            banco=c.banco,
            qtd_baixas=int(c.qtd or 0),
            valor_total=float(c.total or 0),
            pct_valor=round((float(c.total or 0) / grand) * 100, 2),
        )
        for c in contas_rows
    ]

    return ConciliacaoBlock(
        qtd_total=total,
        qtd_conciliadas=conc,
        qtd_nao_conciliadas=nao_conc,
        pct_conciliado=pct,
        valor_conciliado=round(float(r.valor_conc or 0), 2),
        valor_nao_conciliado=round(float(r.valor_nao_conc or 0), 2),
        contas_destino=contas,
    )


# ── DRE estruturada (Fase 2 Show no Financeiro) ─────────────────

async def _dre_block(db: AsyncSession, tenant_id: str, ym: str) -> DreBlock:
    """DRE hierárquico do mês — agrupa fato_caixa por nó DRE via
    `core_ca_dre_links` (ponte DRE ↔ categoria_financeira plana).

    Estratégia:
      1. Pega todos os totais de fato_caixa por categoria_external_id no mês
      2. Lê todos os nós DRE + links pra construir mapa categoria→nó
      3. Soma cada categoria no seu nó DRE folha (e propaga pro pai)
      4. Devolve só os 8 grupos com `codigo` (raízes operacionais — totalizadores
         sem código são linhas calculadas, sem transações)
    """
    # 1. Totais por categoria no mês
    q = await db.execute(
        text("""
            SELECT categoria_external_id, COALESCE(SUM(valor_pago_rateado), 0) AS total
            FROM fato_caixa
            WHERE tenant_id = :tid AND year_month_key = :ym AND is_pago = 1
            GROUP BY categoria_external_id
        """),
        {"tid": tenant_id, "ym": ym},
    )
    totais_por_categoria: dict[str, float] = {}
    total_geral = 0.0
    for r in q.all():
        cat_id = r.categoria_external_id
        v = float(r.total or 0)
        if cat_id:
            totais_por_categoria[cat_id] = v
        total_geral += v

    # 2. Lê estrutura DRE + links
    q_nos = await db.execute(
        text("""
            SELECT external_id, descricao, codigo, posicao, nivel,
                   parent_external_id, root_external_id, qtd_categorias_financeiras
            FROM core_ca_categorias_dre
            WHERE tenant_id = :tid AND is_deleted = 0
        """),
        {"tid": tenant_id},
    )
    nos = q_nos.all()

    q_links = await db.execute(
        text("""
            SELECT dre_external_id, categoria_external_id
            FROM core_ca_dre_links
            WHERE tenant_id = :tid
        """),
        {"tid": tenant_id},
    )
    cat_para_dre: dict[str, list[str]] = {}
    for r in q_links.all():
        cat_para_dre.setdefault(r.categoria_external_id, []).append(r.dre_external_id)

    # 3. Soma por nó DRE (categoria pode estar em múltiplos nós — somamos em todos)
    total_por_no: dict[str, float] = {}
    classificado = 0.0
    cats_classificadas: set[str] = set()
    for cat_id, valor in totais_por_categoria.items():
        nos_alvo = cat_para_dre.get(cat_id, [])
        if not nos_alvo:
            continue
        cats_classificadas.add(cat_id)
        # Distribui a categoria nos nós DRE em que está vinculada (geralmente 1)
        for no_id in nos_alvo:
            total_por_no[no_id] = total_por_no.get(no_id, 0.0) + valor
        # Pra "total_classificado", contamos UMA vez por categoria
        classificado += valor

    # 4. Propaga totais filhos→pai (subgrupo nivel 1 → grupo nivel 0)
    for n in nos:
        if n.nivel >= 1 and n.parent_external_id:
            v = total_por_no.get(n.external_id, 0.0)
            if v:
                total_por_no[n.parent_external_id] = total_por_no.get(n.parent_external_id, 0.0) + v

    # 5. Monta resposta — só raízes com código (operacionais)
    grupos: list[DreGrupoItem] = []
    raizes = [n for n in nos if n.nivel == 0 and n.codigo]
    raizes.sort(key=lambda x: (x.posicao or 99, x.codigo or ""))
    for r in raizes:
        subitens = [n for n in nos if n.parent_external_id == r.external_id]
        subitens.sort(key=lambda x: (x.posicao or 99, x.codigo or ""))
        sub_dto = [
            DreSubgrupoItem(
                external_id=s.external_id,
                descricao=s.descricao or "(sem descrição)",
                codigo=s.codigo,
                posicao=s.posicao,
                qtd_categorias=int(s.qtd_categorias_financeiras or 0),
                total=round(total_por_no.get(s.external_id, 0.0), 2),
            )
            for s in subitens
        ]
        grupos.append(DreGrupoItem(
            external_id=r.external_id,
            descricao=r.descricao or "(sem descrição)",
            codigo=r.codigo or "",
            posicao=r.posicao,
            total=round(total_por_no.get(r.external_id, 0.0), 2),
            subgrupos=sub_dto,
        ))

    nao_classificado = round(total_geral - classificado, 2)
    return DreBlock(
        grupos=grupos,
        total_classificado=round(classificado, 2),
        total_nao_classificado=nao_classificado,
    )


# ── Transferências internas (Fase 3 Show no Financeiro) ─────────

async def _transferencias(
    db: AsyncSession, tenant_id: str, ym: str,
) -> TransferenciasBlock:
    """Movimentação interna entre contas no mês — não conta como receita/despesa.

    Lê core_ca_transferencias agrupado por (origem, destino) pra montar
    top fluxos. Usado pelo card "Transferências internas" em /financeiro.
    """
    # 1. Totais agregados
    q_tot = await db.execute(
        text("""
            SELECT
                COUNT(*) AS qtd,
                COALESCE(SUM(valor), 0) AS valor_total,
                COUNT(DISTINCT origem_conta_external_id) AS qtd_origem,
                COUNT(DISTINCT destino_conta_external_id) AS qtd_destino
            FROM core_ca_transferencias
            WHERE tenant_id = :tid AND is_deleted = 0
              AND DATE_FORMAT(data, '%Y-%m') = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    r = q_tot.one()
    qtd = int(r.qtd or 0)
    valor_total = round(float(r.valor_total or 0), 2)

    # 2. Top fluxos (origem → destino)
    q_flx = await db.execute(
        text("""
            SELECT
                origem_conta_external_id, MAX(origem_conta_nome) AS origem_nome,
                MAX(origem_conta_banco) AS origem_banco,
                destino_conta_external_id, MAX(destino_conta_nome) AS destino_nome,
                MAX(destino_conta_banco) AS destino_banco,
                COUNT(*) AS qtd, COALESCE(SUM(valor),0) AS total
            FROM core_ca_transferencias
            WHERE tenant_id = :tid AND is_deleted = 0
              AND DATE_FORMAT(data, '%Y-%m') = :ym
            GROUP BY origem_conta_external_id, destino_conta_external_id
            ORDER BY total DESC
            LIMIT 8
        """),
        {"tid": tenant_id, "ym": ym},
    )
    fluxos = [
        TransferenciaFluxoItem(
            origem_external_id=row.origem_conta_external_id,
            origem_nome=row.origem_nome or "(sem nome)",
            origem_banco=row.origem_banco,
            destino_external_id=row.destino_conta_external_id,
            destino_nome=row.destino_nome or "(sem nome)",
            destino_banco=row.destino_banco,
            qtd=int(row.qtd or 0),
            valor_total=round(float(row.total or 0), 2),
        )
        for row in q_flx.all()
    ]

    return TransferenciasBlock(
        qtd=qtd,
        valor_total=valor_total,
        qtd_contas_origem=int(r.qtd_origem or 0),
        qtd_contas_destino=int(r.qtd_destino or 0),
        fluxos=fluxos,
    )


# ── Saldos bancários (Fase 1 Show no Financeiro) ────────────────

def _is_banco_real(tipo: str | None, banco: str | None) -> bool:
    """Decide se uma conta financeira é banco real ou cofre/caixinha contábil.

    Caixinhas (cofre da loja, controles internos) entram com `banco="NAO_BANCO"`
    ou `tipo="CAIXINHA"` — não são bancos reais e distorcem o saldo total
    se somados (ex: COFRE PARENTE com -R$ 234k é registro contábil, não dinheiro).
    """
    tipo_up = (tipo or "").upper()
    banco_up = (banco or "").upper()
    if tipo_up == "CAIXINHA":
        return False
    if banco_up == "NAO_BANCO":
        return False
    return True


async def _saldos_bancarios(db: AsyncSession, tenant_id: str) -> SaldosBancariosBlock:
    """Lê core_ca_contas_financeiras e separa bancos reais de caixinhas.

    "Bancos reais" = saldo agregado pra mostrar como "saldo total". As
    caixinhas/cofres ficam num bucket à parte, somadas separado mas visíveis
    pro usuário expandir.
    """
    q = await db.execute(
        text("""
            SELECT external_id, nome, banco, codigo_banco, tipo,
                   saldo_atual, ativo, saldo_atualizado_em
            FROM core_ca_contas_financeiras
            WHERE tenant_id = :tid AND is_deleted = 0
            ORDER BY ativo DESC, ABS(COALESCE(saldo_atual, 0)) DESC
        """),
        {"tid": tenant_id},
    )
    rows = q.all()

    contas: list[ContaBancariaItem] = []
    saldo_bancos = 0.0
    saldo_caixinhas = 0.0
    qtd_bancos = 0
    qtd_caixinhas = 0
    last_updated: str | None = None

    for r in rows:
        ativo = bool(r.ativo)
        saldo = float(r.saldo_atual or 0)
        is_banco = _is_banco_real(r.tipo, r.banco)
        if ativo:
            if is_banco:
                qtd_bancos += 1
                saldo_bancos += saldo
            else:
                qtd_caixinhas += 1
                saldo_caixinhas += saldo
        if r.saldo_atualizado_em:
            iso = r.saldo_atualizado_em.isoformat() if hasattr(r.saldo_atualizado_em, "isoformat") else str(r.saldo_atualizado_em)
            if last_updated is None or iso > last_updated:
                last_updated = iso
        contas.append(ContaBancariaItem(
            external_id=r.external_id,
            nome=r.nome or "(sem nome)",
            banco=r.banco,
            codigo_banco=r.codigo_banco,
            tipo=r.tipo,
            saldo_atual=saldo,
            ativo=ativo,
            is_banco_real=is_banco,
        ))

    return SaldosBancariosBlock(
        saldo_bancos=round(saldo_bancos, 2),
        saldo_caixinhas=round(saldo_caixinhas, 2),
        qtd_bancos_ativos=qtd_bancos,
        qtd_caixinhas_ativas=qtd_caixinhas,
        qtd_contas_total=len(rows),
        atualizado_em=last_updated,
        contas=contas,
    )


# ── Orquestrador ────────────────────────────────────────────────

async def get_financeiro_overview(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> FinanceiroOverviewResponse:
    prev_y, prev_m = _previous_month(year, month)
    ym = _ym_key(year, month)
    prev_ym = _ym_key(prev_y, prev_m)

    kpis = await _kpis_periodo(db, tenant_id, ym)
    kpis_prev = await _kpis_periodo(db, tenant_id, prev_ym)
    saldos = await _saldos_bancarios(db, tenant_id)
    dre = await _dre_block(db, tenant_id, ym)
    metodos_pag = await _metodos_pagamento(db, tenant_id, ym)
    conciliacao = await _conciliacao(db, tenant_id, ym)
    transferencias = await _transferencias(db, tenant_id, ym)
    top_rec = await _top_categorias(db, tenant_id, ym, "RECEITA")
    top_desp = await _top_categorias(db, tenant_id, ym, "DESPESA")
    cc = await _centros_custo(db, tenant_id, ym)
    mix = await _status_mix(db, tenant_id, ym)
    evolution = await _evolution(db, tenant_id, year, month)

    return FinanceiroOverviewResponse(
        period=_period_info(year, month),
        previous=_period_info(prev_y, prev_m),
        kpis=kpis,
        kpis_previous=kpis_prev,
        saldos_bancarios=saldos,
        dre=dre,
        metodos_pagamento=metodos_pag,
        conciliacao=conciliacao,
        transferencias=transferencias,
        top_receitas=top_rec,
        top_despesas=top_desp,
        centros_custo=cc,
        status_mix=mix,
        evolution=evolution,
    )
