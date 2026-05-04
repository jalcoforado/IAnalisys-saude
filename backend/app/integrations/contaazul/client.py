"""
Cliente HTTP para a API Conta Azul.

Endpoints validados em produção (smoke-test 2026-05-04, doc em
`reference_contaazul_v1.md`):

  - GET /v1/pessoas
  - GET /v1/produtos
  - GET /v1/servico                                       (singular!)
  - GET /v1/venda/vendedores                              (array puro)
  - GET /v1/financeiro/eventos-financeiros/contas-a-receber/buscar
  - GET /v1/financeiro/eventos-financeiros/contas-a-pagar/buscar
  - GET /v1/categorias                                    (`permite_apenas_filhos` obrigatório!)
  - GET /v1/centro-de-custo                               (wrapper `itens` em PT — doc oficial mente dizendo `items` em EN)

🔥 PEGADINHA CRÍTICA: o gateway exige Content-Type+Accept JSON em TODA
request, mesmo GET. Sem isso retorna 401 "Invalid token: policy(JWT-VERIFY)"
mesmo com token válido.

Convenção de wrapper inconsistente entre endpoints:
  - pessoas/produtos:    {"totalItems": N, "items": [...]}
  - servicos/eventos:    {"itens_totais": N, "itens": [...], "totais": {...}}
  - categorias:          {"itens_totais": N, "itens": [...], "totais": {...}}
  - centros_custo:       {"itens_totais": N, "itens": [...], "totais": {...}}
                         ⚠ doc oficial diz `items` (EN) mas payload real é `itens` (PT) — confirmado em 2026-05-04
  - vendedores:          [...] (array puro)
"""
from datetime import date
from typing import Any

import httpx


_BASE_URL = "https://api-v2.contaazul.com"

# Sem esses dois cabeçalhos a API retorna 401 — confirmar antes de mexer.
_REQUIRED_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class ContaAzulError(Exception):
    pass


class ContaAzulClient:
    def __init__(self, access_token: str, *, timeout: float = 30.0) -> None:
        self._token = access_token
        self._timeout = timeout
        self._headers = {
            **_REQUIRED_JSON_HEADERS,
            "Authorization": f"Bearer {access_token}",
        }
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        # Reusa um único client httpx pro lifetime do ContaAzulClient — keep-alive
        # acelera muito a paginação e evita o gateway CA travar em handshakes
        # repetidos. Padrão validado em smoke-test direto (8 páginas em 3s).
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        client = self._get_client()
        resp = await client.get(
            f"{_BASE_URL}{path}",
            headers=self._headers,
            params=params or {},
        )

        if resp.status_code == 401:
            raise ContaAzulError(
                "Token expirado ou inválido — reconecte ou renove via /contaazul/refresh."
            )
        if resp.status_code == 429:
            raise ContaAzulError(
                "Rate limit do Conta Azul atingido. Espere alguns minutos e tente novamente."
            )
        if resp.status_code >= 400:
            raise ContaAzulError(
                f"Conta Azul API error {resp.status_code} em {path}: {resp.text[:240]}"
            )
        return resp.json()

    # ── Pessoas (clientes + fornecedores) ─────────────────────

    async def list_pessoas(
        self,
        *,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        nome: str | None = None,
        ativo: bool | None = None,
    ) -> dict:
        """Lista pessoas (clientes + fornecedores em uma só chamada).

        Retorno: {"totalItems": int, "items": [...]}.
        Cada item: id, nome, documento, email, telefone, ativo, perfis (array),
        tipo_pessoa ("Física"|"Jurídica"), id_legado, uuid_legado, datas.

        Paginação: `pagina` (1-indexed) + `tamanho_pagina` (enum: 10, 20, 50,
        100, 200, 500, 1000). NÃO use `offset` — a API ignora silenciosamente
        e devolve sempre a página 1.
        """
        params: dict[str, Any] = {"tamanho_pagina": tamanho_pagina, "pagina": pagina}
        if nome:
            params["nome"] = nome
        if ativo is not None:
            params["ativo"] = "true" if ativo else "false"
        return await self._get("/v1/pessoas", params)

    async def get_pessoa(self, pessoa_id: str) -> dict:
        """Detalhe completo de uma pessoa (com endereço etc.)."""
        return await self._get(f"/v1/pessoas/{pessoa_id}")

    async def get_conta_conectada(self) -> dict:
        """Dados da empresa CA vinculada ao token (single record, sem wrapper).

        Retorno: documento, razao_social, nome_fantasia, data_fundacao, email.
        Usado no callback OAuth pra exibir na UI qual empresa está conectada.
        """
        return await self._get("/v1/pessoas/conta-conectada")

    # ── Produtos ──────────────────────────────────────────────

    async def list_produtos(
        self,
        *,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        status: str | None = None,
    ) -> dict:
        """Retorno: {"totalItems": int, "items": [...]}.
        Item: id, nome, codigo, tipo (PRODUCT|SERVICE), status, saldo,
        valor_venda, custo_medio, nivel_estoque, ean, etc.

        Paginação: mesmo padrão de /v1/pessoas — `pagina` (1-indexed) +
        `tamanho_pagina`. Não usar `offset`.
        """
        params: dict[str, Any] = {"tamanho_pagina": tamanho_pagina, "pagina": pagina}
        if status:
            params["status"] = status
        return await self._get("/v1/produtos", params)

    # ── Serviços ──────────────────────────────────────────────

    async def list_servicos(self) -> dict:
        """Lista serviços odontológicos (sem paginação aparente).

        Retorno: {"itens_totais": int, "itens": [...]}.
        Item: id, id_servico, codigo, descricao, nome, preco, custo,
        status, tipo_servico (PRESTADO|CONTRATADO).
        """
        return await self._get("/v1/servico")

    # ── Vendedores ────────────────────────────────────────────

    async def list_vendedores(self) -> list[dict]:
        """Lista vendedores. ATENÇÃO: resposta é array puro, sem wrapper."""
        return await self._get("/v1/venda/vendedores")

    # ── Financeiro ────────────────────────────────────────────

    async def list_contas_receber(
        self,
        *,
        data_vencimento_de: date | str,
        data_vencimento_ate: date | str,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        status: str | None = None,
        data_alteracao_de: str | None = None,
        data_alteracao_ate: str | None = None,
    ) -> dict:
        """Contas a receber no período (por data de vencimento).

        Retorno: {"itens_totais", "itens": [...], "totais": {...}}.
        Item tem `cliente` + `renegociacao` + `categorias[]` + `centros_custo[]`
        inline (id+nome). `status` em EN, `status_traduzido` em PT.

        Obrigatórios na API: pagina, tamanho_pagina, data_vencimento_de/ate.

        Para delta sync: passe `data_alteracao_de`/`ate` (ISO 8601 SP/GMT-3) +
        janela de vencimento ampla (ex: 2020→2030) para pegar tudo alterado
        independente do mês de vencimento.
        """
        params: dict[str, Any] = {
            "data_vencimento_de": _date_str(data_vencimento_de),
            "data_vencimento_ate": _date_str(data_vencimento_ate),
            "tamanho_pagina": tamanho_pagina,
            "pagina": pagina,
        }
        if status:
            params["status"] = status
        if data_alteracao_de:
            params["data_alteracao_de"] = data_alteracao_de
        if data_alteracao_ate:
            params["data_alteracao_ate"] = data_alteracao_ate
        return await self._get(
            "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar",
            params,
        )

    async def list_contas_pagar(
        self,
        *,
        data_vencimento_de: date | str,
        data_vencimento_ate: date | str,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        status: str | None = None,
        data_alteracao_de: str | None = None,
        data_alteracao_ate: str | None = None,
    ) -> dict:
        """Contas a pagar no período. Mesma estrutura de receber, mas com
        `fornecedor` no lugar de `cliente` e sem `renegociacao`.
        """
        params: dict[str, Any] = {
            "data_vencimento_de": _date_str(data_vencimento_de),
            "data_vencimento_ate": _date_str(data_vencimento_ate),
            "tamanho_pagina": tamanho_pagina,
            "pagina": pagina,
        }
        if status:
            params["status"] = status
        if data_alteracao_de:
            params["data_alteracao_de"] = data_alteracao_de
        if data_alteracao_ate:
            params["data_alteracao_ate"] = data_alteracao_ate
        return await self._get(
            "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar",
            params,
        )

    # ── Categorias e Centros de Custo ─────────────────────────

    async def list_categorias(
        self,
        *,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        tipo: str | None = None,
        permite_apenas_filhos: bool = False,
    ) -> dict:
        """Lista categorias (RECEITA/DESPESA) com hierarquia pai/filho.

        Retorno: {"itens_totais", "itens": [...], "totais": {...}}.
        Item: id, versao, nome, categoria_pai (nullable), tipo, entrada_dre,
        considera_custo_dre.

        ATENÇÃO: `permite_apenas_filhos` é obrigatório na API (default false
        traz a árvore inteira; true traz só folhas).
        """
        params: dict[str, Any] = {
            "tamanho_pagina": tamanho_pagina,
            "pagina": pagina,
            "permite_apenas_filhos": "true" if permite_apenas_filhos else "false",
        }
        if tipo:
            params["tipo"] = tipo
        return await self._get("/v1/categorias", params)

    async def list_centros_custo(
        self,
        *,
        tamanho_pagina: int = 500,
        pagina: int = 1,
        filtro_rapido: str = "TODOS",
    ) -> dict:
        """Lista centros de custo.

        Retorno: {"itens_totais", "itens": [...], "totais": {...}}.
        ⚠ Doc oficial diz wrapper "items" (EN) mas o payload real usa "itens"
        (PT) — confirmado em 2026-05-04 contra Parente (7 CCs).
        Item: id, codigo (nullable), nome, ativo.

        ⚠ `filtro_rapido` default é "TODOS" — sem isso, a API às vezes
        retorna `itens_totais > 0` mas array vazio (bug do CA).
        """
        params: dict[str, Any] = {
            "tamanho_pagina": tamanho_pagina,
            "pagina": pagina,
            "filtro_rapido": filtro_rapido,
        }
        return await self._get("/v1/centro-de-custo", params)


def _date_str(d: date | str) -> str:
    return d.isoformat() if isinstance(d, date) else d


def _parse_retry_after_unused(value: str | None) -> float | None:
    """Header `Retry-After` pode vir como número de segundos ou data HTTP."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None
