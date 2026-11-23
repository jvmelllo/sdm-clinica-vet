"""Configuração da API governamental SIMULADA (serviço independente da clínica)."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carregar_env(caminho=None):
    caminho = caminho or os.path.join(RAIZ, ".env")
    if not os.path.isfile(caminho):
        return
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def config_do_ambiente():
    carregar_env()
    e = os.environ.get
    return {
        "DB_BACKEND": e("DB_BACKEND", "mysql"),
        "MYSQL_HOST": e("MYSQL_HOST", "127.0.0.1"),
        "MYSQL_PORT": int(e("MYSQL_PORT", "3306")),
        "MYSQL_USER": e("MYSQL_USER", "root"),
        "MYSQL_PASSWORD": e("MYSQL_PASSWORD", ""),
        "DB_NAME": e("GOVERNO_DB_NAME", "sdm_governo"),
        "SQLITE_PATH": e("GOVERNO_SQLITE_PATH", os.path.join(RAIZ, "data", "governo.db")),
        "API_KEY": e("GOV_API_KEY", "chave-demo-governo"),
        "PORT": int(e("GOVERNO_PORT", "5001")),
    }
