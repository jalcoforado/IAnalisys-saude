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

from sqlalchemy import select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    CoreAppointmentCategories,
    CoreAppointments,
    CoreAppointmentStatuses,
    CoreAppointmentTags,
    CoreBusiness,
    CoreCrmCampaigns,
    CoreEstimateProcedures,
    CoreEstimates,
    CoreInvoices,
    CorePatients,
    CorePayments,
    CoreProcedures,
    CoreProfessionals,
    CoreReceipts,
    CoreSpecialties,
    CoreSummaryEntries,
    CoreUsersClinicorp,
)
from app.models.staging import (
    StgCcAppointmentCategories,
    StgCcAppointments,
    StgCcAppointmentStatuses,
    StgCcBusiness,
    StgCcCrmCampaigns,
    StgCcEstimates,
    StgCcInvoices,
    StgCcPayments,
    StgCcProcedures,
    StgCcProfessionals,
    StgCcReceipts,
    StgCcSpecialties,
    StgCcSummaryEntries,
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


def _decimal(value: Any) -> Any:
    """Coerção branda pra DECIMAL — passa float/int direto, vazio vira None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


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


# ── Mappers de eventos ──────────────────────────────────────────

def _duration_from_times(from_time: Any, to_time: Any) -> int | None:
    """Calcula duração em minutos a partir de HH:MM strings.
    Clinicorp tem `ProceduresDuration` mas vem 0 na maioria dos casos —
    fromTime/toTime são as fontes confiáveis.
    """
    try:
        if not from_time or not to_time:
            return None
        fh, fm = str(from_time).split(":")
        th, tm = str(to_time).split(":")
        diff = (int(th) * 60 + int(tm)) - (int(fh) * 60 + int(fm))
        # Filtra anomalias (negativo = cruza meia-noite, > 8h é improvável p/ consulta)
        if diff <= 0 or diff > 480:
            return None
        return diff
    except (ValueError, AttributeError):
        return None


def map_appointments(raw: dict) -> dict:
    # Prioriza fromTime/toTime (sempre presentes) sobre ProceduresDuration (0).
    duration = _duration_from_times(raw.get("fromTime"), raw.get("toTime"))
    if duration is None:
        duration = _int(raw.get("ProceduresDuration"))
    return {
        "patient_external_id": _int(raw.get("Patient_PersonId")),
        "patient_name": _str(raw.get("PatientName"), 255),
        "patient_email": _str(raw.get("Email"), 255),
        "patient_mobile_phone": _str(raw.get("MobilePhone"), 50),
        "professional_external_id": _int(raw.get("Dentist_PersonId")),
        "business_external_id": _int(raw.get("Clinic_BusinessId")),
        "appointment_date": _parse_dt(raw.get("date")),
        "from_time": _str(raw.get("fromTime"), 5),
        "to_time": _str(raw.get("toTime"), 5),
        "duration_minutes": duration,
        "category_id": _int(raw.get("CategoryId")),
        "category_description": _str(raw.get("CategoryDescription"), 255),
        "category_color": _str(raw.get("CategoryColor"), 20),
        "status_id": _int(raw.get("StatusId")),
        "procedures_text": _str(raw.get("Procedures")),
        "notes": _str(raw.get("Notes")),
        "alert_info": _str(raw.get("AlertInfo")),
        "schedule_to_id": _int(raw.get("ScheduleToId")),
        "was_edited": bool(raw.get("wasEdited")),
        "is_deleted": _bool_xflag(raw.get("Deleted")),
        "created_external_at": _parse_dt(raw.get("CreateDate")),
        "created_external_user_id": _int(raw.get("CreateUserId")),
        "created_external_user_name": _str(raw.get("CreateUserName"), 255),
    }


def map_estimate_header(raw: dict) -> dict:
    """Mapper do header do orçamento. Procedure list é processado separado."""
    procs = raw.get("ProcedureList") or []
    return {
        "patient_external_id": _int(raw.get("PatientId")),
        "patient_name": _str(raw.get("PatientName"), 255),
        "patient_mobile_phone": _str(raw.get("PatientMobilePhone"), 50),
        "professional_external_id": _int(raw.get("ProfessionalId")),
        "professional_name": _str(raw.get("ProfessionalName"), 255),
        "business_external_id": _int(raw.get("BusinessId")),
        "amount": _decimal(raw.get("Amount")),
        "status": _str(raw.get("Status"), 50),
        "estimate_date": _parse_dt(raw.get("Date")),
        "search_date": _parse_dt(raw.get("SearchDate")),
        "created_external_at": _parse_dt(raw.get("CreateDate")),
        "procedures_count": len(procs) if isinstance(procs, list) else 0,
        "is_deleted": False,
    }


def map_estimate_procedure(proc: dict) -> dict:
    """Mapper de cada item de ProcedureList[]."""
    return {
        "treatment_external_id": _int(proc.get("TreatmentId")),
        "patient_external_id": _int(proc.get("Patient_PersonId")),
        "dentist_external_id": _int(proc.get("Dentist_PersonId")),
        "dentist_name": _str(proc.get("DentistName"), 255),
        "operation_description": _str(proc.get("OperationDescription")),
        "specialty_id": _int(proc.get("SpecialtyId")),
        "procedure_characteristic_id": _int(proc.get("Procedure_CharacteristicId")),
        "related_characteristic_id": _int(proc.get("Related_CharacteristicId")),
        "amount": _decimal(proc.get("Amount")),
        "final_amount": _decimal(proc.get("FinalAmount")),
        "original_amount": _decimal(proc.get("OriginalAmount")),
        "minimum_procedure_amount": _decimal(proc.get("MinimumProcedureAmount")),
        "bill_type": _str(proc.get("BillType"), 50),
        "sequence": _int(proc.get("Sequence")),
        "tooth": _str(proc.get("Tooth"), 50),
        "surface": _str(proc.get("Surface"), 50),
        "executed": bool(proc.get("Executed")),
        "payment_accounted": bool(proc.get("PaymentAccounted")),
        "payment_plan_id": _int(proc.get("PaymentPlanId")),
        "price_id": _int(proc.get("PriceId")),
        "price_list_id": _int(proc.get("PriceListId")),
        "status_id": _int(proc.get("StatusId")),
        "status_description": _str(proc.get("StatusDescription"), 255),
        "created_external_at": _parse_dt(proc.get("CreateDate")),
        "is_deleted": False,
    }


def map_payments(raw: dict) -> dict:
    return {
        "payment_header_external_id": _int(raw.get("PaymentHeaderId")),
        "treatment_external_id": _int(raw.get("TreatmentId")),
        "patient_external_id": _int(raw.get("PatientId")),
        "patient_name": _str(raw.get("PatientName"), 255),
        "payer_name": _str(raw.get("PayerName"), 255),
        "payer_email": _str(raw.get("PayerEmail"), 255),
        "payer_phone": _str(raw.get("PayerPhone"), 50),
        "payer_document": _str(raw.get("PayerDocumentNumber"), 20),
        "amount": _decimal(raw.get("Amount")),
        "service_amount": _decimal(raw.get("ServiceAmount")),
        "total_amount": _decimal(raw.get("TotalAmount")),
        "fee": _decimal(raw.get("Fee")),
        "interest_fee": _decimal(raw.get("InterestFee")),
        "penalty_fee": _decimal(raw.get("PenaltyFee")),
        "type": _str(raw.get("Type"), 50),
        "payment_form": _str(raw.get("PaymentForm"), 50),
        "payment_form_characteristic_id": _int(raw.get("PaymentForm_CharacteristicId")),
        "installment_number": _int(raw.get("InstallmentNumber")),
        "installments_count": _int(raw.get("InstallmentsCount")),
        "person_type": _str(raw.get("PersonType"), 50),
        "payment_description": _str(raw.get("PaymentDescription")),
        "receiver_business_external_id": _int(raw.get("ReceiverBusinessId")),
        "is_received": _bool_xflag(raw.get("PaymentReceived")),
        "is_confirmed": _bool_xflag(raw.get("PaymentConfirmed")),
        "is_canceled": bool(raw.get("Canceled")),
        "payment_date": _parse_dt(raw.get("PaymentDate")),
        "received_date": _parse_dt(raw.get("ReceivedDate")),
        "confirmed_date": _parse_dt(raw.get("ConfirmedDate")),
        "check_out_date": _parse_dt(raw.get("CheckOutDate")),
        "post_date": _parse_dt(raw.get("PostDate")),
        "due_date": _parse_dt(raw.get("DueDate")),
        "transaction_external_id": _str(raw.get("ExternalTxId") or raw.get("ExternalUuid"), 128),
        "is_deleted": False,
    }


def map_invoices(raw: dict) -> dict:
    return {
        "reference_id": _int(raw.get("ReferenceId")),
        "amount": _decimal(raw.get("Amount")),
        "description": _str(raw.get("Description")),
        "patient_external_id": _int(raw.get("PatientId")),
        "patient_name": _str(raw.get("PatientName"), 255),
        "invoice_date": _parse_dt(raw.get("Date")),
        "type": _str(raw.get("Type"), 50),
        "status": _str(raw.get("Status"), 50),
        "is_received": _bool_xflag(raw.get("PaymentReceived")),
        "is_confirmed": _bool_xflag(raw.get("PaymentConfirmed")),
        "installment_number": _int(raw.get("InstallmentNumber")),
        "receiver_business_external_id": _int(raw.get("ReceiverBusinessId")),
        "url": _str(raw.get("url"), 500),
        "is_deleted": False,
    }


def map_receipts(raw: dict) -> dict:
    return {
        "reference_id": _int(raw.get("ReferenceId")),
        "amount": _decimal(raw.get("Amount")),
        "description": _str(raw.get("Description")),
        "patient_external_id": _int(raw.get("PatientId")),
        "patient_name": _str(raw.get("PatientName"), 255),
        "receipt_date": _parse_dt(raw.get("ReceiptDate")),
        "receiver_business_external_id": _int(raw.get("ReceiverBusinessId")),
        "is_deleted": False,
    }


def map_summary_entries(raw: dict) -> dict:
    ref_id = raw.get("ReferenceId")
    if isinstance(ref_id, (list, dict)):
        import json as _json
        ref_id = _json.dumps(ref_id, ensure_ascii=False)
    return {
        "year": _int(raw.get("Year")),
        "month": _int(raw.get("Month")),
        "entry_date": _parse_dt(raw.get("Date")),
        "post_date": _parse_dt(raw.get("PostDate")),
        "account_id": _int(raw.get("AccountId")),
        "type": _str(raw.get("Type"), 20),
        "post_type": _str(raw.get("PostType"), 50),
        "entry_type": _str(raw.get("EntryType"), 50),
        "related_book_entry_id": _int(raw.get("RelatedBookEntryId")),
        "related_person_id": _int(raw.get("RelatedPersonId")),
        "related_business_id": _int(raw.get("RelatedBusinessId")),
        "business_external_id": _int(raw.get("BusinessId")),
        "business_name": _str(raw.get("BusinessName"), 255),
        "description": _str(raw.get("Description")),
        "reference_entity": _str(raw.get("ReferenceEntity"), 50),
        "reference_id_text": _str(ref_id, 255),
        "additional_info": _str(raw.get("AdditionalInfo")),
        "is_open": bool(raw.get("Open")),
        "is_automated": bool(raw.get("Automated")),
        "is_manual": bool(raw.get("Manual")),
        "person_id": _int(raw.get("PersonId")),
        "amount": _decimal(raw.get("Amount")),
        "amount_before_discounts": _decimal(raw.get("AmountBeforeDiscounts")),
        "payment_form_characteristic_id": _int(raw.get("PaymentForm_CharacteristicId")),
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


# Eventos transacionais. estimates é especial (emite 2 outputs) — fica fora desta tupla.
EVENT_TRANSFORMS: tuple[TransformSpec, ...] = (
    TransformSpec("appointments",    StgCcAppointments,    CoreAppointments,    map_appointments),
    TransformSpec("payments",        StgCcPayments,        CorePayments,        map_payments),
    TransformSpec("invoices",        StgCcInvoices,        CoreInvoices,        map_invoices),
    TransformSpec("receipts",        StgCcReceipts,        CoreReceipts,        map_receipts),
    TransformSpec("summary_entries", StgCcSummaryEntries,  CoreSummaryEntries,  map_summary_entries),
)


_TRANSFORMS_BY_NAME: dict[str, TransformSpec] = {
    s.name: s for s in (*STATIC_TRANSFORMS, *EVENT_TRANSFORMS)
}


def get_transform_spec(name: str) -> TransformSpec:
    if name not in _TRANSFORMS_BY_NAME and name != "estimates":
        valid = ", ".join(list(_TRANSFORMS_BY_NAME.keys()) + ["estimates"])
        raise ValueError(f"Transformação desconhecida '{name}'. Válidas: {valid}")
    return _TRANSFORMS_BY_NAME.get(name)  # type: ignore[return-value]


# ── Especial: estimates (header + ProcedureList nested) ─────────

async def transform_estimates(
    db: AsyncSession, tenant_id: str,
) -> tuple[TransformResult, TransformResult]:
    """
    Transforma estimates emitindo 2 outputs:
      - 1 row em core_estimates (header) por staging row
      - N rows em core_estimate_procedures (ProcedureList[i]) por staging row
    """
    rows_staging = await _read_staging(db, StgCcEstimates, tenant_id)

    header_rows: list[dict] = []
    proc_rows: list[dict] = []
    header_errors = 0
    proc_errors = 0

    for external_id, raw, ext_updated in rows_staging:
        try:
            header = map_estimate_header(raw)
            header["tenant_id"] = tenant_id
            header["external_id"] = external_id
            header["external_updated_at"] = ext_updated
            header_rows.append(header)
        except Exception:
            header_errors += 1
            continue

        for proc in (raw.get("ProcedureList") or []):
            if not isinstance(proc, dict):
                proc_errors += 1
                continue
            proc_id = proc.get("id")
            if proc_id is None:
                proc_errors += 1
                continue
            try:
                mapped = map_estimate_procedure(proc)
                mapped["tenant_id"] = tenant_id
                mapped["external_id"] = str(proc_id)
                mapped["external_updated_at"] = _parse_dt(proc.get("z_LastChange_Date"))
                proc_rows.append(mapped)
            except Exception:
                proc_errors += 1

    # Header upsert
    header_inserted = 0
    header_updated = 0
    if header_rows:
        existing_h = await _existing_external_ids(
            db, CoreEstimates, tenant_id, (r["external_id"] for r in header_rows),
        )
        skip = {"tenant_id", "external_id", "created_at"}
        updatable = [k for k in header_rows[0].keys() if k not in skip]
        stmt = mysql_insert(CoreEstimates).values(header_rows)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
        header_inserted = sum(1 for r in header_rows if r["external_id"] not in existing_h)
        header_updated = len(header_rows) - header_inserted

    # Procedures upsert
    proc_inserted = 0
    proc_updated = 0
    if proc_rows:
        existing_p = await _existing_external_ids(
            db, CoreEstimateProcedures, tenant_id, (r["external_id"] for r in proc_rows),
        )
        skip = {"tenant_id", "external_id", "created_at"}
        updatable = [k for k in proc_rows[0].keys() if k not in skip]
        # Batches de 1000 para não estourar limites do MySQL
        batch_size = 1000
        for i in range(0, len(proc_rows), batch_size):
            batch = proc_rows[i:i + batch_size]
            stmt = mysql_insert(CoreEstimateProcedures).values(batch)
            stmt = stmt.on_duplicate_key_update(
                **{k: getattr(stmt.inserted, k) for k in updatable}
            )
            await db.execute(stmt)
        proc_inserted = sum(1 for r in proc_rows if r["external_id"] not in existing_p)
        proc_updated = len(proc_rows) - proc_inserted

    await db.commit()
    return (
        TransformResult("estimates", len(rows_staging), header_inserted, header_updated, header_errors),
        TransformResult("estimate_procedures", len(proc_rows), proc_inserted, proc_updated, proc_errors),
    )


# ── API pública ─────────────────────────────────────────────────

async def transform_static_entity(
    db: AsyncSession, tenant_id: str, name: str,
) -> TransformResult:
    """Transforma UMA entidade staging → core (estática ou evento simples)."""
    if name == "estimates":
        raise ValueError("Use transform_estimates para 'estimates' (emite 2 outputs).")
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


async def transform_all_events(
    db: AsyncSession, tenant_id: str,
) -> list[TransformResult]:
    """Transforma todos os 6 eventos transacionais (5 simples + estimates especial)."""
    results: list[TransformResult] = []
    # 5 eventos simples
    for spec in EVENT_TRANSFORMS:
        results.append(await transform_entity(db, tenant_id, spec))
    # estimates (header + procedures)
    header_r, procs_r = await transform_estimates(db, tenant_id)
    results.append(header_r)
    results.append(procs_r)
    # appointment_tags — depende do payload de stg_cc_appointments (não core)
    results.append(await transform_appointment_tags(db, tenant_id))
    return results


# ── Especial: appointment tags (N por appointment, vindas do payload) ──

# Classes semânticas das tags do Clinicorp. Heurística simples por substring.
# Ordem importa — primeiro match vence (`encaixe` antes de `lembrete` etc).
def _classify_tag(name: str | None) -> str | None:
    if not name:
        return None
    n = name.upper().strip()
    # Lista de espera por vaga
    if "AGUARDADO VAGA" in n or "AGUARDANDO VAGA" in n or "FILA DE ESPERA" in n:
        return "waitlist"
    # Encaixe explícito (gestor sinalizou que é encaixe)
    if "ENCAIXE" in n:
        return "encaixe"
    # Workflow de remarcação
    if "REMARCAR" in n or n.startswith("AGENDAR"):
        return "remarcar"
    # Orçamento pendente (CRC ORÇAMENTO - contatar etc)
    if "ORÇAMENTO" in n or "ORCAMENTO" in n:
        return "orcamento_pendente"
    # Retorno pendente (Aguardando retorno, RETORNO BOTOX etc)
    if "AGUARDANDO RETORNO" in n or n.startswith("RETORNO"):
        return "retorno_pendente"
    # Conferência financeira
    if "FINANCEIRO CONFERIDO" in n:
        return "financeiro_conferido"
    # Lembrete / chamada / ligação
    if "LEMBRETE" in n or "LIGAR" in n or "CHAMAR" in n or "LEMBRAR" in n:
        return "lembrete"
    return "outro"


async def transform_appointment_tags(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """Extrai tags do array `tags` no raw_data dos appointments.
    Cada tag tem id global próprio (external_id) — UNIQUE(tenant_id, external_id).
    """
    sql = text("""
        SELECT external_id, raw_data
        FROM stg_cc_appointments
        WHERE tenant_id = :tenant_id
          AND JSON_LENGTH(JSON_EXTRACT(raw_data, '$.tags')) > 0
    """)
    rows = (await db.execute(sql, {"tenant_id": tenant_id})).all()
    if not rows:
        return TransformResult("appointment_tags", 0, 0, 0, 0)

    import json
    core_rows: list[dict] = []
    errors = 0
    for row in rows:
        appointment_ext = str(row.external_id)
        payload = row.raw_data
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                errors += 1
                continue
        if not isinstance(payload, dict):
            continue
        tags = payload.get("tags") or []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            tag_id = tag.get("id")
            if tag_id is None:
                continue
            name = _str(tag.get("Name"), 255)
            core_rows.append({
                "tenant_id": tenant_id,
                "external_id": str(tag_id),
                "appointment_external_id": appointment_ext,
                "name": name,
                "color": _str(tag.get("Color"), 20),
                "type": _str(tag.get("Type"), 50),
                "template_id": _str(tag.get("TemplateId"), 64) if tag.get("TemplateId") is not None else None,
                "tag_class": _classify_tag(name),
                "is_deleted": False,
                "external_updated_at": _parse_dt(tag.get("z_LastChange_Date")),
            })

    if not core_rows:
        return TransformResult("appointment_tags", len(rows), 0, 0, errors)

    existing = await _existing_external_ids(
        db, CoreAppointmentTags, tenant_id, (r["external_id"] for r in core_rows),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    updatable = [k for k in core_rows[0].keys() if k not in skip]

    batch_size = 1000
    for i in range(0, len(core_rows), batch_size):
        batch = core_rows[i:i + batch_size]
        stmt = mysql_insert(CoreAppointmentTags).values(batch)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult("appointment_tags", len(core_rows), inserted, updated, errors)


async def transform_patients(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """
    Extrai pacientes únicos por UNION dos eventos (appointments + estimates + payments).

    Para cada PatientId distinto:
    - name e mobile_phone: do evento mais recente (via SUBSTRING_INDEX/GROUP_CONCAT)
    - first_seen_at / last_seen_at: MIN/MAX das datas dos eventos
    - total_appointments / total_estimates / total_payments: COUNT por origem
    - external_updated_at = last_seen_at (último evento conhecido)
    - is_deleted = sempre false (paciente é "inativo", não deletado)

    Enriquecimento (sub-PR 18): se há registro em stg_cc_patients_details
    pra esse PatientId, extrai email/birth_date/cpf/status do payload do
    /patient/get. Phone só sobrescreve se evento não trouxe (mobile_phone null).
    """
    sql = text("""
        SELECT
            CAST(pid AS CHAR(64)) AS external_id,
            SUBSTRING_INDEX(GROUP_CONCAT(name ORDER BY dt DESC SEPARATOR '|||'), '|||', 1) AS name,
            SUBSTRING_INDEX(GROUP_CONCAT(phone ORDER BY dt DESC SEPARATOR '|||'), '|||', 1) AS mobile_phone,
            MIN(dt) AS first_seen_at,
            MAX(dt) AS last_seen_at,
            SUM(CASE WHEN src='appt' THEN 1 ELSE 0 END) AS total_appointments,
            SUM(CASE WHEN src='est'  THEN 1 ELSE 0 END) AS total_estimates,
            SUM(CASE WHEN src='pay'  THEN 1 ELSE 0 END) AS total_payments
        FROM (
            SELECT patient_external_id AS pid, patient_name AS name,
                   patient_mobile_phone AS phone, appointment_date AS dt,
                   'appt' AS src
              FROM core_appointments
             WHERE tenant_id = :tenant_id AND patient_external_id IS NOT NULL
            UNION ALL
            SELECT patient_external_id, patient_name, NULL, estimate_date, 'est'
              FROM core_estimates
             WHERE tenant_id = :tenant_id AND patient_external_id IS NOT NULL
            UNION ALL
            SELECT patient_external_id, patient_name, NULL, payment_date, 'pay'
              FROM core_payments
             WHERE tenant_id = :tenant_id AND patient_external_id IS NOT NULL
        ) events
        GROUP BY pid
    """)
    result = await db.execute(sql, {"tenant_id": tenant_id})
    aggregates = result.all()

    if not aggregates:
        return TransformResult("patients", 0, 0, 0, 0)

    # Carrega enriquecimentos do /patient/get (sub-PR 18). Pode estar vazio
    # se a sync de detalhes nunca rodou — nesse caso, segue sem enriquecer.
    details_q = await db.execute(
        text("""
            SELECT external_id, raw_data
            FROM stg_cc_patients_details
            WHERE tenant_id = :tenant_id
        """),
        {"tenant_id": tenant_id},
    )
    import json
    details_map: dict[str, dict] = {}
    for row in details_q.all():
        payload = row.raw_data
        # MySQL JSON via text()/aiomysql vem como string; SQLAlchemy ORM
        # com type JSON desserializa pra dict. Aceita os dois.
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                continue
        if isinstance(payload, dict):
            details_map[str(row.external_id)] = payload

    def _parse_birth(raw: Any) -> Any:
        """API CC retorna 'YYYY-MM-DDTHH:MM' ou similar — quero só a data."""
        if not raw or not isinstance(raw, str):
            return None
        # Aceita 'YYYY-MM-DD' ou 'YYYY-MM-DDT...' — pega os 10 primeiros chars
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    def _normalize_cpf(raw: Any) -> Any:
        """OtherDocumentId pode vir só com dígitos. Mantemos só dígitos limitando a 14."""
        if not raw:
            return None
        s = "".join(ch for ch in str(raw) if ch.isdigit())
        return s[:14] or None

    def _infer_gender(api_gender: Any, name: str | None) -> str | None:
        """Retorna 'M' | 'F' | None.
        1) Se a API retornar Gender ('M'/'F'/'MALE'/'FEMALE'), usa.
        2) Senão, heurística pelo PRIMEIRO NOME PT-BR (sufixo '*'/' jr'/etc removidos).
        Heurística é conservadora: nomes ambíguos (Sandy, Iran, etc) ficam None.
        """
        if api_gender:
            g = str(api_gender).strip().upper()
            if g.startswith("M"): return "M"
            if g.startswith("F"): return "F"
        if not name:
            return None
        first = name.strip().split(" ")[0].upper()
        # Remove sufixos comuns
        first = first.rstrip("*").rstrip(".")
        if not first:
            return None
        # Sufixos típicos de nomes femininos PT-BR
        if first.endswith("A") or first.endswith("AH") or first.endswith("AS"):
            # Exceções masculinas comuns terminadas em A
            if first in {"NICOLA", "ELIAS", "TOBIAS", "MATIAS", "JONAS",
                         "LUCAS", "JESUS", "JUDAS", "ATILA", "DA", "DE",
                         "CALEBE", "ANDRE", "JOSE", "EZEQUIAS", "ISAIAS",
                         "JEREMIAS", "SAMUEL"}:
                return "M"
            return "F"
        # Sufixos típicos de nomes masculinos PT-BR
        if first.endswith("O") or first.endswith("OS") or first.endswith("OR"):
            return "M"
        # Casos comuns explícitos
        masc = {"ABEL", "AILTON", "ANDERSON", "DAVI", "EDSON", "ELIEL",
                "GABRIEL", "ISMAEL", "ISRAEL", "JOEL", "MANOEL", "MIGUEL",
                "RAFAEL", "RAQUEL", "SAMUEL", "DANIEL", "EZEQUIEL", "URIEL",
                "EMERSON", "JEFFERSON", "ROBSON", "VAGNER", "WAGNER", "WALTER",
                "WANDERSON", "WELLINGTON", "WESLEY", "WILLIAM", "WILSON",
                "JOAO", "JOÃO", "RAIMUNDO", "VITOR", "VICTOR", "PEDRO",
                "JESUS", "MATEUS", "MATHEUS", "RAFAH"}
        fem = {"BEATRIZ", "INES", "INÊS", "ESTHER", "ESTER", "RUTH",
               "RAQUEL", "RACHEL", "ABIGAIL", "MIRIAM", "MIRIÃ", "AGAR",
               "JOICE", "DALILA", "EDITH", "JUDITE", "MERCEDES", "DORIS",
               "IRIS", "ÍRIS", "INGRID", "ELIZABETH", "ISABEL", "MABEL",
               "ANNE", "JOANNE", "JANE", "DAPHNE", "ASTRID", "CARMEM",
               "CARMEN", "MIRTES", "LAIS", "LAÍS", "LUIZ", "TAIS", "TAÍS"}
        # "RAQUEL" aparece nas duas — em PT-BR é majoritariamente fem;
        # remova de masc
        if first == "RAQUEL":
            return "F"
        if first == "LUIZ":
            return "M"
        if first in masc:
            return "M"
        if first in fem:
            return "F"
        return None

    core_rows: list[dict] = []
    for r in aggregates:
        ext_id = str(r.external_id)
        det = details_map.get(ext_id, {})
        core_rows.append({
            "tenant_id": tenant_id,
            "external_id": ext_id,
            "is_deleted": False,
            "external_updated_at": r.last_seen_at,
            "name": r.name,
            "mobile_phone": r.mobile_phone or det.get("Phone"),
            "email": det.get("Email"),
            "birth_date": _parse_birth(det.get("BirthDate")),
            "cpf": _normalize_cpf(det.get("OtherDocumentId")),
            "status": det.get("Status"),
            "gender": _infer_gender(
                det.get("Gender") or det.get("Sex"), r.name,
            ),
            "first_seen_at": r.first_seen_at,
            "last_seen_at": r.last_seen_at,
            "total_appointments": int(r.total_appointments or 0),
            "total_estimates": int(r.total_estimates or 0),
            "total_payments": int(r.total_payments or 0),
        })

    existing = await _existing_external_ids(
        db, CorePatients, tenant_id, (r["external_id"] for r in core_rows),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    updatable = [k for k in core_rows[0].keys() if k not in skip]

    batch_size = 1000
    for i in range(0, len(core_rows), batch_size):
        batch = core_rows[i:i + batch_size]
        stmt = mysql_insert(CorePatients).values(batch)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)

    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult("patients", len(core_rows), inserted, updated, 0)


async def transform_all(
    db: AsyncSession, tenant_id: str,
) -> list[TransformResult]:
    """Transforma cadastros + eventos + patients (derivado dos eventos)."""
    results = await transform_all_static(db, tenant_id)
    results.extend(await transform_all_events(db, tenant_id))
    # patients vem POR ÚLTIMO porque depende de core_appointments/estimates/payments
    results.append(await transform_patients(db, tenant_id))
    return results
