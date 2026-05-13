"""Validação Conta Azul × DBF Parente (12/05/2026).

A única fonte oficial do CA da Parente que temos é `visao_contas_a_pagar.xls`
(09/05) com os 201 títulos quitados de abril/2026 — esses BATEM AO CENTAVO.

Demais ondas são validações INTERNAS de coerência do ETL e CROSS-CHECK contra
Clinicorp (única fonte externa que temos validada).

Ondas:
  A — Quitados abril vs Excel (já validada: Δ R$ 0,00)
  B — DRE / categorias (estrutura + cobertura)
  C — Transferências + saldos por conta financeira
  D — Encargos (juros/multa/desconto)
  E — Coerência interna: eventos ACQUITTED == baixas
  F — Cross-check CA RECEITA × Clinicorp fato_financeiro
"""
import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RELATORIOS = ROOT / "relatorios"
RELATORIOS.mkdir(exist_ok=True)


def fmt_br(v: float) -> str:
    if v is None: return "—"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def sql(query: str) -> pd.DataFrame:
    cmd = [
        "docker", "compose", "exec", "-T", "mysql",
        "mysql", "-uianalisys", "-pianalisys123",
        "-D", "ianalisys_saude", "-e", query,
    ]
    proj = ROOT.parent.parent.parent
    r = subprocess.run(cmd, cwd=proj, capture_output=True, timeout=60)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"SQL failed: {stderr}\n---\n{query}")
    r.stdout = stdout
    r.stderr = stderr
    lines = [l for l in r.stdout.splitlines()
             if not l.startswith("mysql:") and not l.startswith("time=") and l.strip()]
    if not lines:
        return pd.DataFrame()
    header = lines[0].split("\t")
    rows = [l.split("\t") for l in lines[1:]]
    df = pd.DataFrame(rows, columns=header)
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df


def section(title: str):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


# ============================================================
# ONDA A — Quitados abril vs Excel
# ============================================================
def onda_a():
    section("ONDA A — Quitados ABR/2026 vs visao_contas_a_pagar.xls")
    df = pd.read_excel(ROOT / "visao_contas_a_pagar.xls")
    xls_pago = df["Valor pago da parcela (R$)"].sum()
    xls_total = df["Valor total pago da parcela (R$)"].sum()
    dbf = sql("""
        SELECT COUNT(*) n, ROUND(SUM(valor_pago),2) v
        FROM core_ca_eventos_financeiros
        WHERE tipo='DESPESA' AND status='ACQUITTED'
          AND data_vencimento BETWEEN '2026-04-01' AND '2026-04-30'
          AND is_deleted=0
    """)
    print(f"  CA Excel: {len(df)} títulos · {fmt_br(xls_pago)} (s/ encargos)")
    print(f"  CA Excel: {len(df)} títulos · {fmt_br(xls_total)} (c/ encargos)")
    print(f"  DBF:      {dbf.iloc[0]['n']} títulos · {fmt_br(float(dbf.iloc[0]['v']))}")
    diff = xls_pago - float(dbf.iloc[0]["v"])
    print(f"  Δ s/ encargos: {fmt_br(diff)}")
    return {
        "xls_n": int(len(df)), "xls_pago": float(xls_pago),
        "xls_total_pago": float(xls_total),
        "dbf_n": int(dbf.iloc[0]["n"]), "dbf_pago": float(dbf.iloc[0]["v"]),
        "diff": float(diff),
        "veredito": "✅ MATCH PERFEITO" if abs(diff) < 0.01 else f"⚠️ Δ={diff:.2f}",
    }


# ============================================================
# ONDA B — DRE / Categorias
# ============================================================
def onda_b():
    section("ONDA B — DRE / Categorias")

    # Estrutura DRE
    estrutura = sql("""
        SELECT
          COUNT(*) AS total_dre,
          SUM(CASE WHEN indica_totalizador=1 THEN 1 ELSE 0 END) AS totalizadores,
          SUM(CASE WHEN nivel=0 THEN 1 ELSE 0 END) AS raiz,
          MAX(nivel) AS profundidade_max
        FROM core_ca_categorias_dre
        WHERE is_deleted=0
    """)
    print(f"\nEstrutura DRE: {estrutura.iloc[0].to_dict()}")

    # Cobertura: % rateios com categoria_external_id preenchida?
    cobertura = sql("""
        SELECT
          COUNT(*) total_rateios,
          SUM(CASE WHEN categoria_external_id IS NOT NULL THEN 1 ELSE 0 END) com_categoria,
          ROUND(100 * SUM(CASE WHEN categoria_external_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) pct
        FROM core_ca_rateio
    """)
    print(f"\nCobertura categoria nos rateios: {cobertura.iloc[0].to_dict()}")

    # Categorias linkadas a DRE
    link = sql("""
        SELECT
          (SELECT COUNT(*) FROM core_ca_categorias WHERE is_deleted=0) total_categorias,
          COUNT(DISTINCT categoria_external_id) categorias_no_dre,
          ROUND(100 * COUNT(DISTINCT categoria_external_id) /
            (SELECT COUNT(*) FROM core_ca_categorias WHERE is_deleted=0), 1) pct
        FROM core_ca_dre_links
    """)
    print(f"\nLink categorias↔DRE: {link.iloc[0].to_dict()}")

    # Despesas abr/2026 por DRE (top 10)
    desp = sql("""
        SELECT
          COALESCE(dre.descricao, '(sem DRE)') AS dre,
          dre.codigo,
          COUNT(DISTINCT ef.external_id) n,
          ROUND(SUM(r.valor), 2) valor
        FROM core_ca_eventos_financeiros ef
        JOIN core_ca_rateio r
          ON r.tenant_id=ef.tenant_id AND r.evento_financeiro_external_id=ef.external_id
        LEFT JOIN core_ca_dre_links lnk
          ON lnk.tenant_id=r.tenant_id AND lnk.categoria_external_id=r.categoria_external_id
        LEFT JOIN core_ca_categorias_dre dre
          ON dre.tenant_id=lnk.tenant_id AND dre.external_id=lnk.dre_external_id
        WHERE ef.tipo='DESPESA' AND ef.status='ACQUITTED'
          AND ef.data_vencimento BETWEEN '2026-04-01' AND '2026-04-30'
          AND ef.is_deleted=0
        GROUP BY dre.descricao, dre.codigo
        ORDER BY valor DESC LIMIT 15
    """)
    print(f"\nTop 15 categorias DRE (despesas ABR/2026):")
    print(desp.to_string(index=False))
    total = desp["valor"].astype(float).sum() if not desp.empty else 0
    print(f"\n  Soma top 15: {fmt_br(total)}  (target ≈ R$ 231.874,29)")
    return {
        "estrutura_dre": estrutura.iloc[0].to_dict(),
        "cobertura_rateios": cobertura.iloc[0].to_dict(),
        "categorias_no_dre": link.iloc[0].to_dict(),
        "soma_top15_dre_abr": float(total),
    }


# ============================================================
# ONDA C — Transferências + Saldos
# ============================================================
def onda_c():
    section("ONDA C — Transferências + Saldos por conta financeira")

    tr_total = sql("SELECT COUNT(*) n, ROUND(SUM(valor),2) v FROM core_ca_transferencias")
    print(f"\nTotal transferências lifetime: {tr_total.iloc[0]['n']} · {fmt_br(float(tr_total.iloc[0]['v']))}")

    # Por mês 2026
    tr_mes = sql("""
        SELECT DATE_FORMAT(data,'%Y-%m') mes,
               COUNT(*) n, ROUND(SUM(valor),2) v
        FROM core_ca_transferencias
        WHERE data BETWEEN '2026-01-01' AND '2026-12-31'
        GROUP BY mes ORDER BY mes
    """)
    print(f"\nTransferências por mês 2026:")
    print(tr_mes.to_string(index=False))

    # Validação: transferências entram em fato_caixa?
    em_fato = sql("""
        SELECT COUNT(*) n, ROUND(COALESCE(SUM(valor_rateado), 0), 2) v
        FROM fato_caixa fc
        JOIN core_ca_transferencias t
          ON t.tenant_id=fc.tenant_id AND t.external_id=fc.parcela_external_id
        WHERE fc.year_month_key BETWEEN '2026-01' AND '2026-12'
    """)
    em_fato_n = int(em_fato.iloc[0]["n"])
    em_fato_v = float(em_fato.iloc[0]["v"]) if str(em_fato.iloc[0]["v"]) != "NULL" else 0.0
    print(f"\nTransferências em fato_caixa (deveria ser 0): {em_fato_n} · {fmt_br(em_fato_v)}")

    # Contas financeiras
    contas = sql("""
        SELECT
          s.external_id,
          JSON_UNQUOTE(JSON_EXTRACT(s.raw_data,'$.saldo_atual')) AS saldo_atual,
          cf.nome AS conta_nome,
          cf.tipo AS conta_tipo,
          cf.banco AS conta_banco
        FROM stg_ca_saldos_atuais s
        LEFT JOIN core_ca_contas_financeiras cf
          ON cf.tenant_id=s.tenant_id AND cf.external_id=s.external_id
        ORDER BY s.synced_at DESC
    """)
    print(f"\nContas financeiras ({len(contas)}):")
    print(contas.to_string(index=False))
    return {
        "tr_total": tr_total.iloc[0].to_dict(),
        "tr_em_fato_caixa": em_fato.iloc[0].to_dict(),
        "n_contas_financeiras": int(len(contas)),
    }


# ============================================================
# ONDA D — Encargos
# ============================================================
def onda_d():
    section("ONDA D — Encargos (juros/multa/desconto)")

    df = pd.read_excel(ROOT / "visao_contas_a_pagar.xls")
    xls = {
        "juros":    float(df["Juros realizado (R$)"].sum()),
        "multa":    float(df["Multa realizado (R$)"].sum()),
        "desconto": float(df["Desconto realizado (R$)"].sum()),
    }
    xls["liquido_encargo"] = xls["juros"] + xls["multa"] - xls["desconto"]

    # DBF: encargos nas baixas dos eventos ACQUITTED abr/2026
    dbf = sql("""
        SELECT
          ROUND(SUM(b.juros), 2) juros,
          ROUND(SUM(b.multa), 2) multa,
          ROUND(SUM(b.desconto), 2) desconto
        FROM core_ca_baixas b
        JOIN core_ca_eventos_financeiros ef
          ON ef.tenant_id=b.tenant_id AND ef.external_id=b.parcela_external_id
        WHERE ef.tipo='DESPESA' AND ef.status='ACQUITTED'
          AND ef.data_vencimento BETWEEN '2026-04-01' AND '2026-04-30'
          AND ef.is_deleted=0 AND b.is_deleted=0
    """)
    db = {
        "juros":    float(dbf.iloc[0]["juros"] or 0),
        "multa":    float(dbf.iloc[0]["multa"] or 0),
        "desconto": float(dbf.iloc[0]["desconto"] or 0),
    }
    db["liquido_encargo"] = db["juros"] + db["multa"] - db["desconto"]

    print(f"\n{'Encargo':<18} {'CA Excel':>14} {'DBF':>14} {'Δ':>12}")
    print("-"*60)
    for k in ["juros", "multa", "desconto", "liquido_encargo"]:
        diff = xls[k] - db[k]
        ok = "✅" if abs(diff) < 0.01 else "⚠️"
        print(f"  {k:<16} {fmt_br(xls[k]):>14} {fmt_br(db[k]):>14} {fmt_br(diff):>10}  {ok}")
    return {"xls": xls, "dbf": db, "diff_liquido": xls["liquido_encargo"] - db["liquido_encargo"]}


# ============================================================
# ONDA E — Coerência interna
# ============================================================
def onda_e():
    section("ONDA E — Coerência interna ETL")

    # Test 1: eventos ACQUITTED têm baixa correspondente?
    print("\nTest 1: eventos ACQUITTED têm baixa correspondente?")
    sem_baixa = sql("""
        SELECT
          DATE_FORMAT(ef.data_vencimento,'%Y-%m') mes,
          COUNT(*) n_eventos_sem_baixa
        FROM core_ca_eventos_financeiros ef
        LEFT JOIN core_ca_baixas b
          ON b.tenant_id=ef.tenant_id AND b.parcela_external_id=ef.external_id
        WHERE ef.status='ACQUITTED' AND ef.is_deleted=0
          AND ef.data_vencimento BETWEEN '2026-01-01' AND '2026-12-31'
          AND b.id IS NULL
        GROUP BY mes ORDER BY mes
    """)
    if sem_baixa.empty:
        print("  ✅ Todos eventos ACQUITTED têm baixa correspondente")
    else:
        print(f"  ⚠️ {sem_baixa['n_eventos_sem_baixa'].astype(int).sum()} eventos ACQUITTED SEM baixa:")
        print(sem_baixa.to_string(index=False))

    # Test 2: SUM(valor_pago da baixa) ≈ valor_pago do evento
    print("\nTest 2: soma valor_pago(baixas) ≈ valor_pago(evento)?")
    coerencia = sql("""
        SELECT
          DATE_FORMAT(ef.data_vencimento,'%Y-%m') mes,
          ROUND(SUM(ef.valor_pago), 2) v_evento,
          ROUND(SUM(b.valor_pago), 2)  v_baixa,
          ROUND(SUM(ef.valor_pago) - SUM(b.valor_pago), 2) diff
        FROM core_ca_eventos_financeiros ef
        JOIN core_ca_baixas b
          ON b.tenant_id=ef.tenant_id AND b.parcela_external_id=ef.external_id
        WHERE ef.status='ACQUITTED' AND ef.is_deleted=0 AND b.is_deleted=0
          AND ef.data_vencimento BETWEEN '2026-01-01' AND '2026-12-31'
        GROUP BY mes ORDER BY mes
    """)
    print(coerencia.to_string(index=False))

    # Test 3: soma rateio == valor_total do evento
    print("\nTest 3: SUM(core_ca_rateio.valor) por evento == ef.valor_total")
    rateio_check = sql("""
        SELECT
          COUNT(*) total_eventos,
          SUM(CASE WHEN ABS(soma_rateio - valor_total) < 0.05 THEN 1 ELSE 0 END) coerentes,
          SUM(CASE WHEN ABS(soma_rateio - valor_total) >= 0.05 THEN 1 ELSE 0 END) incoerentes,
          ROUND(SUM(CASE WHEN ABS(soma_rateio - valor_total) >= 0.05 THEN ABS(soma_rateio - valor_total) ELSE 0 END), 2) gap_total
        FROM (
          SELECT ef.external_id, ef.valor_total, SUM(r.valor) AS soma_rateio
          FROM core_ca_eventos_financeiros ef
          JOIN core_ca_rateio r
            ON r.tenant_id=ef.tenant_id AND r.evento_financeiro_external_id=ef.external_id
          WHERE ef.is_deleted=0 AND ef.data_vencimento BETWEEN '2026-01-01' AND '2026-12-31'
          GROUP BY ef.external_id, ef.valor_total
        ) t
    """)
    print(rateio_check.to_string(index=False))

    return {
        "eventos_acquitted_sem_baixa": int(sem_baixa["n_eventos_sem_baixa"].astype(int).sum()) if not sem_baixa.empty else 0,
        "coerencia_rateio": rateio_check.iloc[0].to_dict(),
        "coerencia_baixas_por_mes": coerencia.to_dict(orient="records"),
    }


# ============================================================
# ONDA F — CA RECEITA × Clinicorp fato_financeiro
# ============================================================
def onda_f():
    section("ONDA F — Cross-check CA RECEITA × Clinicorp fato_financeiro")

    # Receita CA por mês
    ca = sql("""
        SELECT
          DATE_FORMAT(data_vencimento,'%Y-%m') mes,
          ROUND(SUM(valor_pago), 2) v_pago,
          ROUND(SUM(valor_total), 2) v_total,
          COUNT(*) n
        FROM core_ca_eventos_financeiros
        WHERE tipo='RECEITA' AND is_deleted=0
          AND data_vencimento BETWEEN '2026-01-01' AND '2026-05-31'
        GROUP BY mes ORDER BY mes
    """)
    print(f"\nCA RECEITA por mês 2026:")
    print(ca.to_string(index=False))

    # Clinicorp fato_financeiro por mês (se existe a tabela)
    try:
        cc = sql("""
            SELECT
              DATE_FORMAT(date_key,'%Y-%m') mes,
              ROUND(SUM(amount), 2) v_total,
              ROUND(SUM(CASE WHEN is_received=1 THEN amount ELSE 0 END), 2) v_recebido,
              COUNT(*) n
            FROM fato_financeiro
            WHERE date_key BETWEEN '2026-01-01' AND '2026-05-31'
              AND is_canceled = 0
            GROUP BY mes ORDER BY mes
        """)
        print(f"\nClinicorp fato_financeiro por mês:")
        print(cc.to_string(index=False))
    except Exception as e:
        print(f"\nClinicorp fato_financeiro indisponível: {e}")
        cc = pd.DataFrame()

    # Comparativo
    print("\n📊 Cross-check:")
    print(f"{'Mês':<10} {'CA pago':>14} {'CC recebido':>14} {'CC total':>14} {'CC/CA':>8}")
    print("-"*70)
    for _, r in ca.iterrows():
        mes = r["mes"]
        cc_rec, cc_tot = 0, 0
        if not cc.empty:
            row = cc[cc["mes"] == mes]
            if not row.empty:
                cc_rec = float(row.iloc[0]["v_recebido"])
                cc_tot = float(row.iloc[0]["v_total"])
        ca_pago = float(r["v_pago"])
        razao = cc_rec / ca_pago if ca_pago else 0
        print(f"{mes:<10} {fmt_br(ca_pago):>14} {fmt_br(cc_rec):>14} {fmt_br(cc_tot):>14} {razao:>7.0f}x")

    return {
        "ca_receita_por_mes": ca.to_dict(orient="records"),
        "clinicorp_por_mes": cc.to_dict(orient="records") if not cc.empty else None,
    }


# ============================================================
# MAIN
# ============================================================
def main():
    out = {}
    print("\n🔍 VALIDAÇÃO CA × DBF Parente · 2026-05-12")
    out["A"] = onda_a()
    out["B"] = onda_b()
    out["C"] = onda_c()
    out["D"] = onda_d()
    out["E"] = onda_e()
    out["F"] = onda_f()
    (RELATORIOS / "resultados.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\n✓ resultados.json salvo")
    return out


if __name__ == "__main__":
    main()
