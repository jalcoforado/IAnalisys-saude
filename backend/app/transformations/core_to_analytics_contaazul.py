"""
Builders ANALYTICS Conta Azul — popula dim_*_ca / fato_caixa a partir
do CORE CA. Mesmo padrão do core_to_analytics.py do Clinicorp:
SQL puro INSERT...SELECT...ON DUPLICATE KEY UPDATE (rápido e idempotente).

3 dimensões + 1 fato:
- dim_pessoa_ca:        de core_ca_pessoas (UPSERT por external_id)
- dim_categoria_ca:     de core_ca_categorias (UPSERT)
- dim_centro_custo_ca:  de core_ca_centros_custo (UPSERT)
- fato_caixa:           de core_ca_rateio JOIN core_ca_eventos_financeiros
                        (DELETE + INSERT — mesma estratégia do core_ca_rateio
                         já que a granularidade rateio não tem chave natural)

Granularidade do fato_caixa: 1 linha POR LINHA DE RATEIO. Métricas rateadas:
- valor_rateado: já dividido pela transform (linha do rateio)
- valor_pago_rateado:        parcela.valor_pago × (valor_rateado / valor_total)
- valor_em_aberto_rateado:   idem com valor_em_aberto

Tratamento de divisão por zero: parcelas com valor_total = 0 (estornos,
rateios zerados) ficam com valor_pago_rateado = 0 e valor_em_aberto_rateado = 0.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func as sa_func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics_contaazul import (
    DimCategoriaCa, DimCentroCustoCa, DimPessoaCa, FatoCaixa,
)


@dataclass
class BuilderResult:
    entity: str
    rows_built: int
    inserted: int
    updated: int


async def _count_rows(db: AsyncSession, model: type, tenant_id: str) -> int:
    result = await db.execute(
        select(sa_func.count()).select_from(model).where(model.tenant_id == tenant_id)
    )
    return int(result.scalar_one() or 0)


# ── Dimensões (UPSERT por external_id) ──────────────────────────

async def build_dim_pessoa_ca(
    db: AsyncSession, tenant_id: str,
) -> BuilderResult:
    """Popula dim_pessoa_ca a partir de core_ca_pessoas."""
    pre = await _count_rows(db, DimPessoaCa, tenant_id)
    sql = text("""
        INSERT INTO dim_pessoa_ca (
          tenant_id, external_id, rebuilt_at,
          documento, nome, tipo_pessoa,
          is_cliente, is_fornecedor, is_transportadora, ativo
        )
        SELECT
          tenant_id, external_id, NOW(),
          documento, nome, tipo_pessoa,
          is_cliente, is_fornecedor, is_transportadora, ativo
        FROM core_ca_pessoas
        WHERE tenant_id = :tenant_id AND is_deleted = 0
        ON DUPLICATE KEY UPDATE
          rebuilt_at = NOW(),
          documento = VALUES(documento),
          nome = VALUES(nome),
          tipo_pessoa = VALUES(tipo_pessoa),
          is_cliente = VALUES(is_cliente),
          is_fornecedor = VALUES(is_fornecedor),
          is_transportadora = VALUES(is_transportadora),
          ativo = VALUES(ativo)
    """)
    await db.execute(sql, {"tenant_id": tenant_id})
    await db.commit()
    post = await _count_rows(db, DimPessoaCa, tenant_id)
    inserted = max(0, post - pre)
    return BuilderResult("dim_pessoa_ca", post, inserted, post - inserted)


async def build_dim_categoria_ca(
    db: AsyncSession, tenant_id: str,
) -> BuilderResult:
    pre = await _count_rows(db, DimCategoriaCa, tenant_id)
    sql = text("""
        INSERT INTO dim_categoria_ca (
          tenant_id, external_id, rebuilt_at,
          nome, tipo, categoria_pai_external_id, entrada_dre, considera_custo_dre
        )
        SELECT
          tenant_id, external_id, NOW(),
          nome, tipo, categoria_pai_external_id, entrada_dre, considera_custo_dre
        FROM core_ca_categorias
        WHERE tenant_id = :tenant_id AND is_deleted = 0
        ON DUPLICATE KEY UPDATE
          rebuilt_at = NOW(),
          nome = VALUES(nome),
          tipo = VALUES(tipo),
          categoria_pai_external_id = VALUES(categoria_pai_external_id),
          entrada_dre = VALUES(entrada_dre),
          considera_custo_dre = VALUES(considera_custo_dre)
    """)
    await db.execute(sql, {"tenant_id": tenant_id})
    await db.commit()
    post = await _count_rows(db, DimCategoriaCa, tenant_id)
    inserted = max(0, post - pre)
    return BuilderResult("dim_categoria_ca", post, inserted, post - inserted)


async def build_dim_centro_custo_ca(
    db: AsyncSession, tenant_id: str,
) -> BuilderResult:
    pre = await _count_rows(db, DimCentroCustoCa, tenant_id)
    sql = text("""
        INSERT INTO dim_centro_custo_ca (
          tenant_id, external_id, rebuilt_at,
          codigo, nome, ativo
        )
        SELECT
          tenant_id, external_id, NOW(),
          codigo, nome, ativo
        FROM core_ca_centros_custo
        WHERE tenant_id = :tenant_id AND is_deleted = 0
        ON DUPLICATE KEY UPDATE
          rebuilt_at = NOW(),
          codigo = VALUES(codigo),
          nome = VALUES(nome),
          ativo = VALUES(ativo)
    """)
    await db.execute(sql, {"tenant_id": tenant_id})
    await db.commit()
    post = await _count_rows(db, DimCentroCustoCa, tenant_id)
    inserted = max(0, post - pre)
    return BuilderResult("dim_centro_custo_ca", post, inserted, post - inserted)


# ── Fato (DELETE + INSERT) ──────────────────────────────────────

async def build_fato_caixa(
    db: AsyncSession, tenant_id: str,
) -> BuilderResult:
    """Reconstroi fato_caixa a partir do JOIN core_ca_rateio + core_ca_eventos_financeiros.

    Métricas rateadas: valor_pago_rateado e valor_em_aberto_rateado são
    proporcionais ao valor da linha de rateio sobre o valor total da parcela.

    Estratégia DELETE+INSERT do tenant (não tem chave natural pra UPSERT
    em rateio — id do rateio é instável, regerado a cada transform).

    is_vencido: status = 'OVERDUE'
    is_pago:    status = 'ACQUITTED' (quitado totalmente)
    is_em_aberto: status IN ('PENDING','PARTIAL') OU is_vencido
    dias_atraso: diff de hoje vs data_vencimento se vencido (CURDATE() em MySQL).
    """
    # Limpa do tenant (idempotente)
    await db.execute(
        text("DELETE FROM fato_caixa WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    await db.commit()

    sql = text("""
        INSERT INTO fato_caixa (
          tenant_id, parcela_external_id, evento_origem_id,
          pessoa_external_id, categoria_external_id, centro_custo_external_id,
          date_key, year, month, year_month_key,
          date_key_competencia, year_competencia, month_competencia, year_month_competencia_key,
          tipo, status,
          is_pago, is_vencido, is_em_aberto, is_aproximado,
          valor_rateado, valor_pago_rateado, valor_em_aberto_rateado,
          dias_atraso, rebuilt_at
        )
        SELECT
          ef.tenant_id,
          ef.external_id AS parcela_external_id,
          ef.evento_origem_id,
          ef.pessoa_external_id,
          r.categoria_external_id,
          r.centro_custo_external_id,
          ef.data_vencimento AS date_key,
          YEAR(ef.data_vencimento) AS year,
          MONTH(ef.data_vencimento) AS month,
          DATE_FORMAT(ef.data_vencimento, '%Y-%m') AS year_month_key,
          ef.data_competencia AS date_key_competencia,
          YEAR(ef.data_competencia) AS year_competencia,
          MONTH(ef.data_competencia) AS month_competencia,
          DATE_FORMAT(ef.data_competencia, '%Y-%m') AS year_month_competencia_key,
          ef.tipo,
          ef.status,
          (ef.status = 'ACQUITTED') AS is_pago,
          (ef.status = 'OVERDUE') AS is_vencido,
          (ef.status IN ('PENDING','PARTIAL','OVERDUE')) AS is_em_aberto,
          r.is_aproximado,
          r.valor AS valor_rateado,
          CASE
            WHEN ef.valor_total > 0
              THEN ROUND(COALESCE(ef.valor_pago, 0) * r.valor / ef.valor_total, 2)
            ELSE 0
          END AS valor_pago_rateado,
          CASE
            WHEN ef.valor_total > 0
              THEN ROUND(COALESCE(ef.valor_em_aberto, 0) * r.valor / ef.valor_total, 2)
            ELSE 0
          END AS valor_em_aberto_rateado,
          CASE
            WHEN ef.status = 'OVERDUE' AND ef.data_vencimento < CURDATE()
              THEN DATEDIFF(CURDATE(), ef.data_vencimento)
            ELSE NULL
          END AS dias_atraso,
          NOW()
        FROM core_ca_rateio r
        INNER JOIN core_ca_eventos_financeiros ef
          ON ef.tenant_id = r.tenant_id
         AND ef.external_id = r.evento_financeiro_external_id
        WHERE r.tenant_id = :tenant_id
          AND ef.data_vencimento IS NOT NULL
          AND ef.is_deleted = 0
    """)
    await db.execute(sql, {"tenant_id": tenant_id})
    await db.commit()

    post = await _count_rows(db, FatoCaixa, tenant_id)
    return BuilderResult("fato_caixa", post, post, 0)


# ── Orquestrador ────────────────────────────────────────────────

async def build_all_dimensions_ca(
    db: AsyncSession, tenant_id: str,
) -> list[BuilderResult]:
    """Reconstroi as 3 dimensões CA. dim_tempo é shared com CC."""
    return [
        await build_dim_pessoa_ca(db, tenant_id),
        await build_dim_categoria_ca(db, tenant_id),
        await build_dim_centro_custo_ca(db, tenant_id),
    ]


async def build_all_analytics_ca(
    db: AsyncSession, tenant_id: str,
) -> list[BuilderResult]:
    """Reconstroi toda a camada analytics CA: 3 dims + fato_caixa."""
    results = await build_all_dimensions_ca(db, tenant_id)
    results.append(await build_fato_caixa(db, tenant_id))
    return results
