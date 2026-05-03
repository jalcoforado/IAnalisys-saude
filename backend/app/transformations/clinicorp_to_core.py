"""
Transformação STAGING → CORE para a Clinicorp.

Padrão por entidade:
  1. Lê linhas de stg_cc_<entity> (raw_data JSON) em batch
  2. Aplica mapper(raw_data) → dict com campos tipados
  3. Faz INSERT ... ON DUPLICATE KEY UPDATE em core_<entity>
  4. Retorna (fetched, inserted, updated)

Idempotência: chave única (tenant_id, external_id) — re-rodar não duplica.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    CoreAppointmentCategories,
    CoreAppointmentStatuses,
    CoreBusiness,
    CoreCrmCampaigns,
    CoreProcedures,
    CoreProfessionals,
    CoreSpecialties,
    CoreUsersClinicorp,
)
from app.models.staging import (
    StgCcAppointmentCategories,
    StgCcAppointmentStatuses,
    StgCcBusiness,
    StgCcCrmCampaigns,
    StgCcProcedures,
    StgCcProfessionals,
    StgCcSpecialties,
    StgCcUsers,
)


# ── Helpers de coerção ──────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _parse_date(value: Any) -> date | None:
    dt = _parse_dt(value)
    return dt.date() if dt else None


def _str(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _bool_xflag(value: Any) -> bool:
    """Convenção Clinicorp: 'X' = true, qualquer outra coisa = false."""
    return value == "X"


# ── Helper genérico de transformação ────────────────────────────

@dataclass(frozen=True)
class TransformSpec:
    """Define como transformar uma entidade staging → core."""
    name: str                                  # 'business', 'users', etc.
    staging_model: type
    core_model: type
    mapper: Callable[[dict], dict]             # raw_data → dict de campos core


@dataclass
class TransformResult:
    """Resultado de uma execução de transformação."""
    entity: str
    fetched: int
    inserted: int
    updated: int
    errors: int


async def _existing_external_ids(
    db: AsyncSession, model: type, tenant_id: str, ids: Iterable[str],
) -> set[str]:
    ids_list = list(ids)
    if not ids_list:
        return set()
    result = await db.execute(
        select(model.external_id).where(
            model.tenant_id == tenant_id,
            model.external_id.in_(ids_list),
        )
    )
    return {row[0] for row in result}


async def _read_staging(
    db: AsyncSession, staging_model: type, tenant_id: str,
) -> list[tuple[str, dict, datetime | None]]:
    """Retorna lista de (external_id, raw_data, external_updated_at) de staging."""
    result = await db.execute(
        select(
            staging_model.external_id,
            staging_model.raw_data,
            staging_model.external_updated_at,
        ).where(staging_model.tenant_id == tenant_id)
    )
    return [(row[0], row[1] or {}, row[2]) for row in result]


async def transform_entity(
    db: AsyncSession, tenant_id: str, spec: TransformSpec,
) -> TransformResult:
    """Executa transformação de uma entidade. Faz upsert em massa via ON DUPLICATE KEY UPDATE."""
    rows_staging = await _read_staging(db, spec.staging_model, tenant_id)
    if not rows_staging:
        return TransformResult(spec.name, 0, 0, 0, 0)

    core_rows: list[dict] = []
    errors = 0
    for external_id, raw, ext_updated in rows_staging:
        try:
            mapped = spec.mapper(raw)
            mapped["tenant_id"] = tenant_id
            mapped["external_id"] = external_id
            mapped["external_updated_at"] = ext_updated
            core_rows.append(mapped)
        except Exception:
            errors += 1
            continue

    if not core_rows:
        return TransformResult(spec.name, len(rows_staging), 0, 0, errors)

    # Pre-query existentes pra contar inserted vs updated
    existing = await _existing_external_ids(
        db, spec.core_model, tenant_id, (r["external_id"] for r in core_rows),
    )

    # Update fields = todos os campos exceto chaves e timestamps locais
    skip_on_update = {"tenant_id", "external_id", "created_at"}
    sample = core_rows[0]
    updatable = [k for k in sample.keys() if k not in skip_on_update]

    stmt = mysql_insert(spec.core_model).values(core_rows)
    stmt = stmt.on_duplicate_key_update(
        **{k: getattr(stmt.inserted, k) for k in updatable}
    )
    await db.execute(stmt)
    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult(spec.name, len(rows_staging), inserted, updated, errors)


# ── Mappers (1 por entidade estática) ───────────────────────────
# Cada mapper recebe raw_data (JSON da Clinicorp) e devolve dict de campos core.
# Campos comuns (tenant_id, external_id, external_updated_at) são preenchidos
# pelo helper transform_entity, NÃO pelos mappers.

def map_business(raw: dict) -> dict:
    return {
        "name": _str(raw.get("Name"), 255),
        "business_name": _str(raw.get("BusinessName"), 255),
        "company_id": _str(raw.get("CompanyId"), 32),
        "email": _str(raw.get("Email"), 255),
        "is_deleted": False,
    }


def map_users(raw: dict) -> dict:
    return {
        "username": _str(raw.get("UserName"), 255),
        "full_name": _str(raw.get("FullName"), 255),
        "is_deleted": _bool_xflag(raw.get("Deleted")),
    }


def map_professionals(raw: dict) -> dict:
    return {
        "name": _str(raw.get("name") or raw.get("Name"), 255),
        "cpf": _str(raw.get("cpf") or raw.get("CPF"), 20),
        "is_deleted": False,
    }


def map_specialties(raw: dict) -> dict:
    return {
        "description": _str(raw.get("Description"), 255),
        "type": _str(raw.get("Type"), 50),
        "language": _str(raw.get("Language"), 10),
        "initial_id": _int(raw.get("InitialId")),
        "related_characteristic_id": _int(raw.get("Related_CharacteristicId")),
        "is_active": _bool_xflag(raw.get("Active")),
        "is_deleted": False,
    }


def map_procedures(raw: dict) -> dict:
    return {
        "internal_code": _str(raw.get("InternalCode"), 50),
        "procedure_name": _str(raw.get("ProcedureName"), 500),
        "procedure_expertise_name": _str(raw.get("ProcedureExpertiseName"), 255),
        "type": _str(raw.get("Type"), 50),
        "price_list_id": _int(raw.get("PriceListId")),
        "price_list_name": _str(raw.get("PriceListName"), 255),
        "is_deleted": False,
    }


def map_appointment_categories(raw: dict) -> dict:
    return {
        "description": _str(raw.get("Description"), 255),
        "color": _str(raw.get("Color"), 20),
        "is_deleted": False,
    }


def map_appointment_statuses(raw: dict) -> dict:
    return {
        "description": _str(raw.get("Description"), 255),
        "color": _str(raw.get("Color"), 20),
        "type": _str(raw.get("Type"), 50),
        "reference": _str(raw.get("Reference"), 100),
        "is_active": _bool_xflag(raw.get("Active")),
        "is_deleted": False,
    }


def map_crm_campaigns(raw: dict) -> dict:
    return {
        "name": _str(raw.get("Name"), 255),
        "status": _str(raw.get("Status"), 50),
        "description": _str(raw.get("Description")),
        "is_deleted": False,
    }


# ── Catálogo: lookup name → spec ────────────────────────────────

STATIC_TRANSFORMS: tuple[TransformSpec, ...] = (
    TransformSpec("business",               StgCcBusiness,              CoreBusiness,              map_business),
    TransformSpec("users",                  StgCcUsers,                 CoreUsersClinicorp,        map_users),
    TransformSpec("professionals",          StgCcProfessionals,         CoreProfessionals,         map_professionals),
    TransformSpec("specialties",            StgCcSpecialties,           CoreSpecialties,           map_specialties),
    TransformSpec("procedures",             StgCcProcedures,            CoreProcedures,            map_procedures),
    TransformSpec("appointment_categories", StgCcAppointmentCategories, CoreAppointmentCategories, map_appointment_categories),
    TransformSpec("appointment_statuses",   StgCcAppointmentStatuses,   CoreAppointmentStatuses,   map_appointment_statuses),
    TransformSpec("crm_campaigns",          StgCcCrmCampaigns,          CoreCrmCampaigns,          map_crm_campaigns),
)

_TRANSFORMS_BY_NAME: dict[str, TransformSpec] = {s.name: s for s in STATIC_TRANSFORMS}


def get_transform_spec(name: str) -> TransformSpec:
    if name not in _TRANSFORMS_BY_NAME:
        valid = ", ".join(_TRANSFORMS_BY_NAME.keys())
        raise ValueError(f"Transformação desconhecida '{name}'. Válidas: {valid}")
    return _TRANSFORMS_BY_NAME[name]


# ── API pública ─────────────────────────────────────────────────

async def transform_static_entity(
    db: AsyncSession, tenant_id: str, name: str,
) -> TransformResult:
    """Transforma UMA entidade estática staging → core."""
    spec = get_transform_spec(name)
    return await transform_entity(db, tenant_id, spec)


async def transform_all_static(
    db: AsyncSession, tenant_id: str,
) -> list[TransformResult]:
    """Transforma todas as 8 entidades estáticas em sequência."""
    results: list[TransformResult] = []
    for spec in STATIC_TRANSFORMS:
        results.append(await transform_entity(db, tenant_id, spec))
    return results
