"""Camada de acesso a dados. Esconde as diferenças entre MySQL (PyMySQL) e SQLite.

Convenções:
  * SQL escrito com placeholders %s (convertidos para ? no SQLite);
  * linhas retornadas como dict, com DECIMAL -> float e datas -> texto ISO
    ("YYYY-MM-DD" / "YYYY-MM-DD HH:MM:SS"), iguais nos dois bancos;
  * uma conexão por requisição (flask.g); a transação só vale se o serviço
    chamar commit() — tudo que não foi confirmado sofre rollback no fim.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

from flask import current_app, g

FMT_DATAHORA = "%Y-%m-%d %H:%M:%S"
FMT_DATA = "%Y-%m-%d"


def agora():
    return datetime.now().strftime(FMT_DATAHORA)


def hoje():
    return date.today().strftime(FMT_DATA)


def erros_de_integridade():
    """Tupla com a(s) exceção(ões) de violação de integridade do driver em uso."""
    return (sqlite3.IntegrityError, *_mysql_integrity())


def _mysql_integrity():
    try:
        import pymysql
        return (pymysql.err.IntegrityError,)
    except ImportError:
        return ()


def _normaliza(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.strftime(FMT_DATAHORA)
    if isinstance(valor, date):
        return valor.strftime(FMT_DATA)
    return valor


class Conexao:
    def __init__(self, bruta, backend):
        self.raw = bruta
        self.backend = backend

    def _sql(self, sql):
        if self.backend == "sqlite":
            return sql.replace("%%", "\0").replace("%s", "?").replace("\0", "%")
        return sql

    def consultar(self, sql, params=()):
        """SELECT que retorna lista de dicts."""
        if self.backend == "sqlite":
            cur = self.raw.execute(self._sql(sql), tuple(params))
            linhas = [dict(r) for r in cur.fetchall()]
        else:
            with self.raw.cursor() as cur:
                cur.execute(sql, tuple(params))
                linhas = list(cur.fetchall())
        return [{k: _normaliza(v) for k, v in l.items()} for l in linhas]

    def um(self, sql, params=()):
        linhas = self.consultar(sql, params)
        return linhas[0] if linhas else None

    def escalar(self, sql, params=()):
        linha = self.um(sql, params)
        return next(iter(linha.values())) if linha else None

    def executar(self, sql, params=()):
        """INSERT/UPDATE/DELETE. Retorna o lastrowid (útil nos INSERTs)."""
        if self.backend == "sqlite":
            cur = self.raw.execute(self._sql(sql), tuple(params))
            return cur.lastrowid
        with self.raw.cursor() as cur:
            cur.execute(sql, tuple(params))
            return cur.lastrowid

    def inserir(self, tabela, **cols):
        nomes = ", ".join(cols)
        marcas = ", ".join(["%s"] * len(cols))
        return self.executar(f"INSERT INTO {tabela} ({nomes}) VALUES ({marcas})", list(cols.values()))

    def atualizar(self, tabela, id_, **cols):
        sets = ", ".join(f"{c} = %s" for c in cols)
        self.executar(f"UPDATE {tabela} SET {sets} WHERE id = %s", [*cols.values(), id_])

    def commit(self):
        self.raw.commit()

    def rollback(self):
        try:
            self.raw.rollback()
        except Exception:  # conexão já fechada
            pass

    def fechar(self):
        try:
            self.raw.close()
        except Exception:
            pass


def abrir_conexao(cfg, criar_banco=False):
    """Abre uma conexão nova conforme DB_BACKEND. criar_banco=True cria o schema MySQL se faltar."""
    if cfg["DB_BACKEND"] == "sqlite":
        caminho = cfg["SQLITE_PATH"]
        if caminho != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        bruta = sqlite3.connect(caminho, check_same_thread=False, timeout=30)
        bruta.row_factory = sqlite3.Row
        bruta.execute("PRAGMA foreign_keys = ON")  # no SQLite as FKs vêm desligadas por padrão
        if caminho != ":memory:":
            bruta.execute("PRAGMA journal_mode = WAL")
        return Conexao(bruta, "sqlite")

    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ImportError as exc:  # mensagem clara para o aluno
        raise RuntimeError(
            "Driver MySQL ausente. Instale com: pip install -r requirements.txt "
            "(ou use DB_BACKEND=sqlite para testar sem MySQL)."
        ) from exc

    parametros = dict(host=cfg["MYSQL_HOST"], port=cfg["MYSQL_PORT"], user=cfg["MYSQL_USER"],
                      password=cfg["MYSQL_PASSWORD"], charset="utf8mb4", cursorclass=DictCursor,
                      autocommit=False, connect_timeout=5)
    if criar_banco:
        tmp = pymysql.connect(**parametros)
        with tmp.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {cfg['DB_NAME']} "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        tmp.commit()
        tmp.close()
    bruta = pymysql.connect(database=cfg["DB_NAME"], **parametros)
    return Conexao(bruta, "mysql")


# --- integração com o ciclo de vida da requisição Flask -----------------------
def get_db():
    if "db" not in g:
        g.db = abrir_conexao(current_app.config["SDM"])
    return g.db


def fechar_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.rollback()  # o que não recebeu commit() explícito é descartado
        conn.fechar()


@contextmanager
def sessao(app):
    """Conexão avulsa para fora de requisições (worker de reenvio, scripts)."""
    conn = abrir_conexao(app.config["SDM"])
    try:
        yield conn
    finally:
        conn.rollback()
        conn.fechar()
