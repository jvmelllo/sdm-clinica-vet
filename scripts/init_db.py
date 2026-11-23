"""Cria (e opcionalmente popula) os bancos da clínica e do governo simulado.

Uso:
  python scripts/init_db.py --reset --seed            # recria tudo e carrega dados fictícios
  python scripts/init_db.py --servico governo --reset # só o banco do governo
  DB_BACKEND=sqlite python scripts/init_db.py --reset --seed   # sem MySQL (arquivos em data/)

Com MySQL, o script cria o database (CREATE DATABASE IF NOT EXISTS) se o usuário tiver permissão.
Alternativa manual: executar database/mysql/*.sql no cliente mysql (ver README).
"""
import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from database import ddl, seed  # noqa: E402


def preparar(nome, modulo_cfg, modulo_db, comandos, ordem_drop, reset, com_seed):
    cfg = modulo_cfg.config_do_ambiente()
    alvo = cfg["SQLITE_PATH"] if cfg["DB_BACKEND"] == "sqlite" else f"mysql://{cfg['MYSQL_HOST']}/{cfg['DB_NAME']}"
    print(f"[{nome}] banco: {alvo}")
    conn = modulo_db.abrir_conexao(cfg, criar_banco=True)
    try:
        if reset:
            for tabela in ordem_drop:
                conn.executar(f"DROP TABLE IF EXISTS {tabela}")
            conn.commit()
            print(f"[{nome}] tabelas antigas removidas")
        try:
            for cmd in comandos(cfg["DB_BACKEND"]):
                conn.executar(cmd)
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            sys.exit(f"[{nome}] não foi possível criar as tabelas ({exc}). Já existem? Use --reset.")
        print(f"[{nome}] tabelas criadas")
        if com_seed and nome == "clinica":
            for cmd in seed.comandos_seed_clinica():
                conn.executar(cmd)
            conn.commit()
            print(f"[{nome}] dados fictícios carregados (senha das contas: {seed.SENHA_DEMO})")
    finally:
        conn.fechar()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--servico", choices=["clinica", "governo", "todos"], default="todos")
    p.add_argument("--reset", action="store_true", help="apaga e recria as tabelas")
    p.add_argument("--seed", action="store_true", help="carrega dados fictícios (só a clínica tem seed)")
    a = p.parse_args()

    if a.servico in ("clinica", "todos"):
        from clinica_api import config as cc, db as cd
        preparar("clinica", cc, cd, ddl.comandos_clinica, ddl.ordem_drop_clinica(), a.reset, a.seed)
    if a.servico in ("governo", "todos"):
        from governo_api import config as gc, db as gd
        preparar("governo", gc, gd, ddl.comandos_governo, ddl.ordem_drop_governo(), a.reset, a.seed)


if __name__ == "__main__":
    main()
