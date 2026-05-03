"""
Builders da camada ANALYTICS — popula dim_*/fato_* a partir do CORE.

Idempotência: cada builder é uma operação repetível (DELETE + INSERT
ou INSERT...ON DUPLICATE KEY UPDATE). Não corrompe dados em execuções
sucessivas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import DimTempo


_MONTH_NAMES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

# Python: weekday() 0=segunda .. 6=domingo
# MySQL DAYOFWEEK: 1=domingo .. 7=sábado
# Convertendo Python → MySQL convention:
_DAY_NAMES_PT = {
    1: "Domingo", 2: "Segunda", 3: "Terça", 4: "Quarta",
    5: "Quinta", 6: "Sexta", 7: "Sábado",
}


@dataclass
class BuilderResult:
    entity: str
    rows_built: int
    inserted: int
    updated: int


def _build_dim_tempo_rows(start: date, end: date) -> list[dict]:
    """Gera dicts de linhas para dim_tempo cobrindo [start, end] inclusivo."""
    rows: list[dict] = []
    current = start
    while current <= end:
        # Python weekday: 0=mon..6=sun → converter para MySQL DAYOFWEEK (1=sun..7=sat)
        py_wd = current.weekday()
        mysql_dow = (py_wd + 2) if py_wd <= 5 else 1  # mon=2, tue=3, .., sat=7, sun=1
        quarter = (current.month - 1) // 3 + 1
        iso_year, iso_week, _ = current.isocalendar()  # noqa: F841
        rows.append({
            "date_key": current,
            "year": current.year,
            "quarter": quarter,
            "month": current.month,
            "day": current.day,
            "week": iso_week,
            "day_of_week": mysql_dow,
            "day_of_year": current.timetuple().tm_yday,
            "year_month_key": f"{current.year}-{current.month:02d}",
            "year_quarter_key": f"{current.year}-Q{quarter}",
            "is_weekend": mysql_dow in (1, 7),
            "month_name_pt": _MONTH_NAMES_PT[current.month],
            "day_of_week_name_pt": _DAY_NAMES_PT[mysql_dow],
        })
        current += timedelta(days=1)
    return rows


async def build_dim_tempo(
    db: AsyncSession,
    start_year: int = 2019,
    end_year: int = 2030,
) -> BuilderResult:
    """
    Popula dim_tempo de 1º jan(start_year) a 31 dez(end_year) — inclusive.
    Default: 2019..2030 = 12 anos = ~4.383 dias.

    Idempotente: usa INSERT ... ON DUPLICATE KEY UPDATE.
    """
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    rows = _build_dim_tempo_rows(start, end)

    if not rows:
        return BuilderResult("dim_tempo", 0, 0, 0)

    # Conta quantos já existem pra distinguir inserted vs updated
    from sqlalchemy import select, func as sa_func
    existing_q = await db.execute(
        select(sa_func.count())
        .select_from(DimTempo)
        .where(DimTempo.date_key.between(start, end))
    )
    existing_count = int(existing_q.scalar_one() or 0)

    skip_on_update = {"date_key"}
    updatable = [k for k in rows[0].keys() if k not in skip_on_update]

    # Insert em batches de 500 (12 anos × 366 dias ÷ batch_size = 9 batches)
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        stmt = mysql_insert(DimTempo).values(batch)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)

    await db.commit()

    inserted = max(0, len(rows) - existing_count)
    updated = len(rows) - inserted
    return BuilderResult("dim_tempo", len(rows), inserted, updated)
