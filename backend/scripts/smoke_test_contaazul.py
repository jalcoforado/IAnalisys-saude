"""
Smoke-test do client Conta Azul.

Lê o token salvo do tenant Parente (`00000000-...-001`), bate nos 6
endpoints reais e imprime contagem de itens. Reproduzível.

Uso: docker exec ianalisys_backend python scripts/smoke_test_contaazul.py

Pré-requisito: token Conta Azul ativo no banco. Se expirado, chamar
`/contaazul/refresh` antes ou injetar via OAuth.
"""
import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.contaazul.client import ContaAzulClient, ContaAzulError
from app.models.contaazul_token import ContaAzulToken


PARENTE_TENANT_ID = "00000000-0000-0000-0000-000000000001"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ContaAzulToken).where(ContaAzulToken.tenant_id == PARENTE_TENANT_ID)
        )
        token = result.scalar_one_or_none()

    if not token:
        print("❌ Sem token Conta Azul para a Parente. Conecte primeiro.")
        return

    print(f"✓ Token encontrado, expira em {token.expires_at}")
    client = ContaAzulClient(token.access_token)

    checks = [
        ("Pessoas",
         lambda: client.list_pessoas(tamanho_pagina=1),
         lambda d: f"totalItems={d['totalItems']} (sample={d['items'][0]['nome'][:40]!r})"),
        ("Produtos",
         lambda: client.list_produtos(tamanho_pagina=1),
         lambda d: f"totalItems={d['totalItems']}"),
        ("Servicos",
         lambda: client.list_servicos(),
         lambda d: f"itens_totais={d['itens_totais']}"),
        ("Vendedores",
         lambda: client.list_vendedores(),
         lambda d: f"count={len(d)} (array puro)"),
        ("Contas a Receber (jan-abr/2026)",
         lambda: client.list_contas_receber(
             data_vencimento_de="2026-01-01", data_vencimento_ate="2026-04-30", tamanho_pagina=1),
         lambda d: f"itens_totais={d['itens_totais']} totais.todos=R$ {d['totais']['todos']:.2f}"),
        ("Contas a Pagar (jan-abr/2026)",
         lambda: client.list_contas_pagar(
             data_vencimento_de="2026-01-01", data_vencimento_ate="2026-04-30", tamanho_pagina=1),
         lambda d: f"itens_totais={d['itens_totais']} totais.todos=R$ {d['totais']['todos']:.2f}"),
    ]

    failures = 0
    for name, call, summarize in checks:
        try:
            data = await call()
            print(f"✓ {name:>40s} → {summarize(data)}")
        except ContaAzulError as e:
            failures += 1
            print(f"✗ {name:>40s} → {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"✗ {name:>40s} → INESPERADO {type(e).__name__}: {e}")

    print()
    if failures:
        print(f"❌ {failures}/{len(checks)} endpoints falharam")
        raise SystemExit(1)
    print(f"✅ {len(checks)}/{len(checks)} endpoints OK")


if __name__ == "__main__":
    asyncio.run(main())
