"""
Classificador IA de comentários Meta — Sub-PR 21f.

Para cada comentário novo em `stg_meta_ig_comments` que ainda NÃO está em
`core_meta_comentarios`:

1. Aplica fast-path local (sem chamar IA) pra:
   - Self-replies da própria clínica (autor == ig_username) → entram em core
     como `respondido_flag=True` sem classificação semântica
   - Comentários só-emoji ou muito curtos (< 3 chars úteis) → sentimento "positivo"
     ou "neutro" via heurística, sem chamar IA
2. O resto vai pra DeepSeek em batch (8 comentários por chamada — economiza
   tokens e respeita rate limit).

O classificador é IDEMPOTENTE: re-rodar não duplica nem reclassifica. Para
forçar reclassificação, basta deletar a linha em core_meta_comentarios.

Métricas IA preenchidas (11 colunas em core_meta_comentarios):
  sentimento, lead_quente_flag, depoimento_flag, duvida_clinica_flag,
  objecao_flag, reclamacao_flag, procedimento_mencionado,
  urgencia_atendimento, requer_resposta_humana, respondido_flag,
  horas_para_resposta.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.deepseek.client import DeepSeekClient, DeepSeekError
from app.models.core_meta import CoreMetaComentarios
from app.models.staging_meta import StgMetaIgComments, StgMetaIgPerfil, StgMetaTokens

logger = logging.getLogger(__name__)


_BATCH_SIZE = 8

_SENTIMENTOS = {"positivo", "neutro", "negativo"}
_URGENCIAS = {"alta", "media", "baixa"}

# Regex pra detectar comentários "só emoji + pontuação" (não classificáveis)
_RE_SO_EMOJI = re.compile(
    r"^[\s\W\d👏❤🙌😍🥰🤩🎉✨🌟💪🔥🙏💜💕💖💗💛💚💙🖤🤍🤎😊😀😁😂🤣😘😎😉☺🥺💯⭐🌹🌷🌸🌺💐👍👌🤝🙏❣💝]+$",
    re.UNICODE,
)
_RE_EMOJI_ONLY = re.compile(r"^\s*[\W\d]+\s*$", re.UNICODE)


def _strip(text: str) -> str:
    return (text or "").strip()


def _is_so_emoji(text: str) -> bool:
    """True se o texto é só pontuação/emoji/dígitos (sem letras)."""
    t = _strip(text)
    if not t:
        return True
    # Se NÃO tem nenhuma letra alfabética, classificamos como só emoji/símbolo.
    return not re.search(r"[A-Za-zÀ-ÿ]", t)


SYSTEM_PROMPT = """Você é uma analista de redes sociais de uma clínica odontológica brasileira.

Sua tarefa: classificar comentários do Instagram da clínica.

Para cada comentário, devolva um objeto JSON com os seguintes campos:
- sentimento: "positivo" | "neutro" | "negativo"
- lead_quente: bool — true se o autor demonstra interesse claro em agendar/saber preço/fazer procedimento ("quanto custa?", "como agendo?", "tenho interesse")
- depoimento: bool — true se é elogio à clínica ou conta experiência pessoal positiva (paciente que foi atendido)
- duvida_clinica: bool — true se faz pergunta sobre tratamento/sintoma/procedimento ("isso dói?", "implante pode em quem usa anticoagulante?")
- objecao: bool — true se mostra resistência a tratamento ("muito caro", "tenho medo", "vou esperar")
- reclamacao: bool — true se reclama de atendimento, preço, espera, qualidade
- procedimento: string|null — qual procedimento o comentário menciona ("implante", "clareamento", "lente", "ortodontia", "facetas", "extração", "limpeza", "canal", "prótese"); null se nenhum específico
- urgencia: "alta" | "media" | "baixa" — quão urgente é responder. ALTA pra leads quentes e reclamações; MEDIA pra dúvidas clínicas; BAIXA pra elogios/emojis

Responda APENAS com um JSON no formato:
{"classificacoes": [{"sentimento": ..., "lead_quente": ..., ...}, ...]}

A ordem das classificações DEVE bater com a ordem dos comentários numerados no input.
Seja objetivo. Self-replies da clínica (raros aqui) → sentimento neutro, todas flags false."""


def _build_user_prompt(comments: list[dict[str, str]]) -> str:
    lines = ["Classifique os comentários abaixo:\n"]
    for i, c in enumerate(comments, start=1):
        autor = c.get("username") or "?"
        texto = (c.get("text") or "").replace("\n", " ").strip()[:280]
        lines.append(f"{i}. @{autor}: {texto}")
    return "\n".join(lines)


def _validate_classificacao(c: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza retorno IA: força tipos e ranges válidos."""
    sent = (c.get("sentimento") or "").lower()
    if sent not in _SENTIMENTOS:
        sent = "neutro"
    urg = (c.get("urgencia") or "").lower()
    if urg not in _URGENCIAS:
        urg = "baixa"
    return {
        "sentimento": sent,
        "lead_quente_flag": bool(c.get("lead_quente")),
        "depoimento_flag": bool(c.get("depoimento")),
        "duvida_clinica_flag": bool(c.get("duvida_clinica")),
        "objecao_flag": bool(c.get("objecao")),
        "reclamacao_flag": bool(c.get("reclamacao")),
        "procedimento_mencionado": (c.get("procedimento") or None) or None,
        "urgencia_atendimento": urg,
        "requer_resposta_humana": bool(
            c.get("lead_quente") or c.get("duvida_clinica") or c.get("reclamacao")
        ),
    }


def _fast_path(text: str, autor: str, ig_username: str | None) -> dict[str, Any] | None:
    """Classifica sem chamar IA quando dá. Retorna None se precisa de IA."""
    # Self-reply da clínica
    if ig_username and autor and autor.lower() == ig_username.lower():
        return {
            "sentimento": "neutro",
            "lead_quente_flag": False,
            "depoimento_flag": False,
            "duvida_clinica_flag": False,
            "objecao_flag": False,
            "reclamacao_flag": False,
            "procedimento_mencionado": None,
            "urgencia_atendimento": "baixa",
            "requer_resposta_humana": False,
        }
    # Só emoji / texto sem letras
    if _is_so_emoji(text):
        return {
            "sentimento": "positivo",  # emoji em comentário de clínica é quase sempre positivo
            "lead_quente_flag": False,
            "depoimento_flag": False,
            "duvida_clinica_flag": False,
            "objecao_flag": False,
            "reclamacao_flag": False,
            "procedimento_mencionado": None,
            "urgencia_atendimento": "baixa",
            "requer_resposta_humana": False,
        }
    return None


async def _classify_batch(
    deepseek: DeepSeekClient, batch: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Classifica até _BATCH_SIZE comentários via DeepSeek. Pode levantar DeepSeekError."""
    user = _build_user_prompt(batch)
    resp = await deepseek.complete_json(
        system=SYSTEM_PROMPT,
        user=user,
        temperature=0.2,
        max_tokens=1500,
    )
    classifs = resp.get("classificacoes") or []
    if not isinstance(classifs, list):
        raise DeepSeekError("Resposta sem 'classificacoes' como lista.")
    # Aceita resposta com tamanho diferente (corner case: IA pula 1) — preenche neutro
    out = []
    for i in range(len(batch)):
        if i < len(classifs) and isinstance(classifs[i], dict):
            out.append(_validate_classificacao(classifs[i]))
        else:
            out.append(_validate_classificacao({}))
    return out


async def _get_ig_username(db: AsyncSession, tenant_id: str) -> str | None:
    """Pega @username da clínica pra identificar self-replies."""
    tok = (await db.execute(
        select(StgMetaTokens.ig_username).where(StgMetaTokens.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if tok:
        return tok
    perfil = (await db.execute(
        select(StgMetaIgPerfil.raw_data)
        .where(StgMetaIgPerfil.tenant_id == tenant_id)
        .order_by(StgMetaIgPerfil.data_referencia.desc())
        .limit(1)
    )).scalar_one_or_none()
    return (perfil or {}).get("username") if perfil else None


async def classify_pending_comments(
    db: AsyncSession, tenant_id: str, *, limit: int = 200,
) -> dict[str, Any]:
    """Classifica até `limit` comentários ainda não classificados.

    Retorna stats: total processado, fast-path, ia, erros.
    """
    # Comentários em staging ainda NÃO em core (pelo external_id)
    sub = select(CoreMetaComentarios.external_id).where(
        CoreMetaComentarios.tenant_id == tenant_id,
    )
    rows = (await db.execute(
        select(
            StgMetaIgComments.external_id,
            StgMetaIgComments.post_external_id,
            StgMetaIgComments.commented_at,
            StgMetaIgComments.raw_data,
        )
        .where(StgMetaIgComments.tenant_id == tenant_id)
        .where(~StgMetaIgComments.external_id.in_(sub))
        .order_by(StgMetaIgComments.commented_at.desc())
        .limit(limit)
    )).all()

    if not rows:
        return {"processed": 0, "fast_path": 0, "ia": 0, "errors": 0, "skipped_empty": 0}

    ig_username = await _get_ig_username(db, tenant_id)

    deepseek = DeepSeekClient()
    if not deepseek.is_configured:
        logger.warning("DEEPSEEK_API_KEY ausente — classificador só processará via fast-path")

    fast_count = 0
    ia_count = 0
    err_count = 0
    skipped = 0
    now = datetime.utcnow()

    # Particiona em fast-path e batch IA
    pending_ia: list[tuple[Any, dict[str, str]]] = []  # (row, {username, text})

    for row in rows:
        external_id, post_id, commented_at, raw = row
        raw = raw or {}
        text = raw.get("text") or ""
        autor = raw.get("username") or ""
        if not text and not autor:
            skipped += 1
            continue

        fp = _fast_path(text, autor, ig_username)
        if fp is not None:
            await _persist(db, tenant_id, external_id, post_id, autor, text, commented_at, raw, fp, model_tag="fast-path")
            fast_count += 1
        else:
            pending_ia.append((row, {"username": autor, "text": text}))

    # Batch DeepSeek
    if pending_ia and deepseek.is_configured:
        for start in range(0, len(pending_ia), _BATCH_SIZE):
            chunk = pending_ia[start:start + _BATCH_SIZE]
            try:
                classifs = await _classify_batch(deepseek, [c[1] for c in chunk])
                for (row, _c), classif in zip(chunk, classifs):
                    external_id, post_id, commented_at, raw = row
                    raw = raw or {}
                    await _persist(
                        db, tenant_id, external_id, post_id, raw.get("username") or "", raw.get("text") or "",
                        commented_at, raw, classif, model_tag=f"deepseek/{deepseek._model}",  # noqa: SLF001
                    )
                    ia_count += 1
            except DeepSeekError as exc:
                logger.warning("DeepSeek falhou no batch de %d comentários: %s", len(chunk), exc)
                err_count += len(chunk)

    await db.commit()
    logger.info(
        "Classificação coments tenant=%s: fast=%d ia=%d errs=%d skip=%d",
        tenant_id, fast_count, ia_count, err_count, skipped,
    )

    return {
        "processed": fast_count + ia_count,
        "fast_path": fast_count,
        "ia": ia_count,
        "errors": err_count,
        "skipped_empty": skipped,
        "pending_remaining": len(pending_ia) - ia_count - err_count if not deepseek.is_configured else 0,
    }


async def _persist(
    db: AsyncSession,
    tenant_id: str,
    external_id: str,
    post_external_id: str,
    autor: str,
    texto: str,
    commented_at: datetime | None,
    raw: dict[str, Any],
    classif: dict[str, Any],
    *,
    model_tag: str,
) -> None:
    """Insere em core_meta_comentarios. Se já existe (race condition), atualiza."""
    from sqlalchemy.dialects.mysql import insert as mysql_insert

    parent_id = raw.get("parent_id")  # vem do syncer quando é reply
    stmt = mysql_insert(CoreMetaComentarios).values(
        tenant_id=tenant_id,
        external_id=external_id,
        post_external_id=post_external_id,
        post_id=None,  # FK pra core_meta_posts — pode ficar null até subir CORE de posts
        autor_username=autor or None,
        texto=texto,
        commented_at=commented_at,
        parent_external_id=parent_id,
        sentimento=classif["sentimento"],
        lead_quente_flag=classif["lead_quente_flag"],
        depoimento_flag=classif["depoimento_flag"],
        duvida_clinica_flag=classif["duvida_clinica_flag"],
        objecao_flag=classif["objecao_flag"],
        reclamacao_flag=classif["reclamacao_flag"],
        procedimento_mencionado=classif["procedimento_mencionado"],
        urgencia_atendimento=classif["urgencia_atendimento"],
        requer_resposta_humana=classif["requer_resposta_humana"],
        respondido_flag=parent_id is None and (autor or "").lower() != "" and False,  # marcar depois quando link de reply existir
        horas_para_resposta=None,
        classificacao_ia_modelo=model_tag,
        classificacao_ia_at=datetime.utcnow(),
    )
    stmt = stmt.on_duplicate_key_update(
        texto=stmt.inserted.texto,
        sentimento=stmt.inserted.sentimento,
        lead_quente_flag=stmt.inserted.lead_quente_flag,
        depoimento_flag=stmt.inserted.depoimento_flag,
        duvida_clinica_flag=stmt.inserted.duvida_clinica_flag,
        objecao_flag=stmt.inserted.objecao_flag,
        reclamacao_flag=stmt.inserted.reclamacao_flag,
        procedimento_mencionado=stmt.inserted.procedimento_mencionado,
        urgencia_atendimento=stmt.inserted.urgencia_atendimento,
        requer_resposta_humana=stmt.inserted.requer_resposta_humana,
        classificacao_ia_modelo=stmt.inserted.classificacao_ia_modelo,
        classificacao_ia_at=stmt.inserted.classificacao_ia_at,
        updated_at=datetime.utcnow(),
    )
    await db.execute(stmt)
