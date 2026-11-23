"""Fixtures dos testes.

Os testes sobem, de verdade, três servidores HTTP em threads (porta aleatória):
  * API governamental simulada (com banco SQLite próprio)
  * um ViaCEP FALSO local (o real não é acessível no ambiente de testes; ver docs/04)
e usam a API da clínica pelo test client do Flask — que chama os outros dois por HTTP real
(biblioteca requests). Assim timeouts, conexão recusada e indisponibilidade são exercitados de verdade.
"""
import os
import sqlite3
import threading

import pytest
import requests
from werkzeug.serving import make_server

from clinica_api.app import create_app
from database import ddl, seed
from governo_api.app import criar_app as criar_app_governo

API_KEY = "chave-de-teste"
EMAIL_ANA = "ana.souza@clinicavet.example"
SENHA = seed.SENHA_DEMO


class ServidorHTTP:
    """Servidor WSGI em thread, que pode ser parado e religado na MESMA porta (simula queda)."""

    def __init__(self, app):
        self.app = app
        self.srv = make_server("127.0.0.1", 0, app, threaded=True)
        self.porta = self.srv.server_port
        self.thread = None
        self.iniciar()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.porta}"

    def iniciar(self):
        if self.thread is None or not self.thread.is_alive():
            if getattr(self.srv, "socket", None) is None or self.srv.socket.fileno() == -1:
                self.srv = make_server("127.0.0.1", self.porta, self.app, threaded=True)
            self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
            self.thread.start()

    def parar(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=5)


def _criar_schema(caminho, comandos, extras=()):
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    for c in comandos:
        con.execute(c)
    for s in extras:
        con.execute(s)
    con.commit()
    con.close()


# ------------------------------------------------------------------ ViaCEP falso
def _viacep_falso():
    """Mesma implementação usada em demonstrações offline (scripts/viacep_falso.py)."""
    import importlib.util
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "viacep_falso.py")
    spec = importlib.util.spec_from_file_location("viacep_falso", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.criar_app()


@pytest.fixture(scope="session")
def viacep_url():
    srv = ServidorHTTP(_viacep_falso())
    yield srv.url + "/ws"
    srv.parar()


@pytest.fixture(scope="session")
def seed_sql():
    return seed.comandos_seed_clinica()


# ------------------------------------------------------------------ governo simulado
class Governo:
    def __init__(self, tmp_path):
        self.banco = str(tmp_path / "governo.db")
        _criar_schema(self.banco, ddl.comandos_governo("sqlite"))
        self.app = criar_app_governo({"DB_BACKEND": "sqlite", "SQLITE_PATH": self.banco, "API_KEY": API_KEY})
        self.servidor = ServidorHTTP(self.app)
        self.headers = {"X-API-Key": API_KEY}

    @property
    def url(self):
        return self.servidor.url

    def simular(self, **kw):
        r = requests.put(self.url + "/api/governo/simulacao", json=kw, headers=self.headers, timeout=3)
        assert r.status_code == 200, r.text
        return r.json()

    def vacinacoes(self, microchip=None):
        r = requests.get(self.url + "/api/governo/vacinacoes-antirrabicas", headers=self.headers, timeout=3,
                         params={"microchip": microchip} if microchip else None)
        return r.json()

    def animal(self, microchip):
        return requests.get(f"{self.url}/api/governo/animais/{microchip}", headers=self.headers, timeout=3)

    def derrubar(self):
        self.servidor.parar()

    def religar(self):
        self.servidor.iniciar()


@pytest.fixture
def governo(tmp_path):
    g = Governo(tmp_path)
    yield g
    try:
        g.servidor.parar()
    except Exception:  # já parado pelo teste
        pass


# ------------------------------------------------------------------ clínica
class Api:
    """Cliente de teste da API da clínica (guarda o token do login)."""

    def __init__(self, app):
        self.app = app
        self.c = app.test_client()
        self.token = None

    def login(self, email=EMAIL_ANA, senha=SENHA):
        r = self.c.post("/api/auth/login", json={"email": email, "senha": senha})
        assert r.status_code == 200, r.get_json()
        self.token = r.get_json()["token"]
        return r

    def _h(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def get(self, caminho, **kw):
        return self.c.get(caminho, headers=self._h(), **kw)

    def post(self, caminho, json=None, **kw):
        return self.c.post(caminho, json=json if json is not None else {}, headers=self._h(), **kw)

    def put(self, caminho, json=None, **kw):
        return self.c.put(caminho, json=json, headers=self._h(), **kw)

    def delete(self, caminho, **kw):
        return self.c.delete(caminho, headers=self._h(), **kw)

    def sem_token(self):
        outro = Api(self.app)
        return outro


@pytest.fixture
def app(tmp_path, governo, viacep_url, seed_sql):
    banco = str(tmp_path / "clinica.db")
    _criar_schema(banco, ddl.comandos_clinica("sqlite"), seed_sql)
    return create_app({
        "TESTING": True, "AUTO_RETRY": False, "DB_BACKEND": "sqlite", "SQLITE_PATH": banco,
        "GOV_URL": governo.url, "GOV_API_KEY": API_KEY, "GOV_TIMEOUT_S": 1.0, "GOV_MAX_TENTATIVAS": 3,
        "VIACEP_URL": viacep_url, "VIACEP_TIMEOUT_S": 0.8, "EXPOR_CODIGO_NA_RESPOSTA": True,
        "EMAIL_SIMULADO_ARQUIVO": str(tmp_path / "emails.log"),
    })


@pytest.fixture
def api(app):
    a = Api(app)
    a.login()
    return a


@pytest.fixture
def anonimo(app):
    return Api(app)
