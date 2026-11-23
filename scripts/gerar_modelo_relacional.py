"""Lê o schema real (via SQLite em memória, mesmo DDL do MySQL) e imprime o modelo
relacional em Markdown: colunas, PK, FK, UNIQUE e CHECK de cada tabela.

Uso interno: importado por scripts/gerar_doc_modelo.py (gera docs/02-modelo-de-dados.md).
"""
import os
import re
import sqlite3
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from database import ddl  # noqa: E402


def descrever(titulo, comandos):
    con = sqlite3.connect(":memory:")
    for c in comandos:
        con.execute(c)
    out = [f"### {titulo}", ""]
    tabelas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for t in tabelas:
        cols = con.execute(f"PRAGMA table_info({t})").fetchall()
        fks = con.execute(f"PRAGMA foreign_key_list({t})").fetchall()
        sql = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()[0]
        uniques = re.findall(r"CONSTRAINT (uq_\w+) UNIQUE \(([^)]*)\)", sql)
        checks = re.findall(r"CONSTRAINT (ck_\w+) CHECK", sql)

        fk_por_col = {}
        for f in fks:
            fk_por_col.setdefault(f[3], []).append(f"{f[2]}.{f[4]}")
        out.append(f"**{t}**")
        out.append("")
        out.append("| Coluna | Tipo | Nulo? | Chave | Observação |")
        out.append("|---|---|---|---|---|")
        for _, nome, tipo, notnull, default, pk in cols:
            chave = []
            if pk:
                chave.append("PK")
            if nome in fk_por_col:
                chave.append("FK")
            uqs = [n for n, c in uniques if nome in [x.strip() for x in c.split(",")]]
            if uqs:
                chave.append("UK")
            obs = []
            if nome in fk_por_col:
                obs.append("→ " + ", ".join(fk_por_col[nome]))
            if default is not None:
                obs.append(f"default {default}")
            out.append(f"| {nome} | {tipo or ''} | {'não' if notnull or pk else 'sim'} | "
                       f"{', '.join(chave)} | {'; '.join(obs)} |")
        out.append("")
        if uniques:
            out.append("Unicidade: " + "; ".join(f"`{n}` ({c.strip()})" for n, c in uniques))
            out.append("")
        if checks:
            out.append("Restrições CHECK: " + ", ".join(f"`{c}`" for c in checks))
            out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    print(descrever("Banco da clínica (`sdm_clinica`)", ddl.comandos_clinica("sqlite")))
    print(descrever("Banco do governo simulado (`sdm_governo`)", ddl.comandos_governo("sqlite")))
