"""Gera os scripts SQL entregáveis (MySQL) em database/mysql/ a partir de database/ddl.py.

Uso:  python scripts/gerar_sql.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from database import ddl, seed  # noqa: E402

SAIDA = os.path.join(RAIZ, "database", "mysql")


def escrever(nome, linhas):
    caminho = os.path.join(SAIDA, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas).rstrip() + "\n")
    print("gerado:", os.path.relpath(caminho, RAIZ))


def cabecalho(titulo, banco):
    return [
        f"-- {titulo}",
        "-- Arquivo GERADO por scripts/gerar_sql.py a partir de database/ddl.py (não edite à mão).",
        "-- Requer MySQL >= 8.0.16 (as restrições CHECK só são aplicadas a partir dessa versão).",
        "",
        f"CREATE DATABASE IF NOT EXISTS {banco} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        f"USE {banco};",
        "",
        "SET FOREIGN_KEY_CHECKS = 0;",
    ]


def main():
    os.makedirs(SAIDA, exist_ok=True)

    # --- clínica -----------------------------------------------------------
    linhas = cabecalho("SDM - Banco da API privada da clínica veterinária", "sdm_clinica")
    linhas += [f"DROP TABLE IF EXISTS {t};" for t in ddl.ordem_drop_clinica()]
    linhas += ["SET FOREIGN_KEY_CHECKS = 1;", ""]
    linhas += [c + ";\n" for c in ddl.comandos_clinica("mysql")]
    escrever("01_clinica_schema.sql", linhas)

    linhas = [
        "-- SDM - Dados fictícios da clínica (senha das contas: Senha@123)",
        "-- Arquivo GERADO por scripts/gerar_sql.py a partir de database/seed.py.",
        "USE sdm_clinica;",
        "",
    ]
    linhas += [c + ";" for c in seed.comandos_seed_clinica()]
    escrever("02_clinica_seed.sql", linhas)

    # --- governo -----------------------------------------------------------
    linhas = cabecalho("SDM - Banco da API governamental SIMULADA (independente do banco da clínica)",
                       "sdm_governo")
    linhas += [f"DROP TABLE IF EXISTS {t};" for t in ddl.ordem_drop_governo()]
    linhas += ["SET FOREIGN_KEY_CHECKS = 1;", ""]
    linhas += [c + ";\n" for c in ddl.comandos_governo("mysql")]
    escrever("03_governo_schema.sql", linhas)


if __name__ == "__main__":
    main()
