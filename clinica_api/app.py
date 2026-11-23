"""Fábrica da aplicação Flask da API privada da clínica."""
import logging
import threading
import time

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import db
from .config import config_do_ambiente
from .errors import ApiError
from .routes import (animais, auth, catalogos, consultas, demo, enderecos, integracoes, sistema, tutores,
                     vacinas, veterinarios)
from .services import integracao

log = logging.getLogger("clinica")


def create_app(overrides=None):
    app = Flask(__name__)
    cfg = config_do_ambiente()
    cfg.update(overrides or {})
    app.config["SDM"] = cfg
    app.config["TESTING"] = bool(cfg.get("TESTING"))
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.teardown_appcontext(db.fechar_db)

    for modulo in (auth, veterinarios, tutores, enderecos, catalogos, animais, consultas, vacinas,
                   integracoes, demo, sistema):
        app.register_blueprint(modulo.bp)

    registrar_erros(app)
    registrar_cors(app)
    if cfg["AUTO_RETRY"] and not cfg.get("TESTING"):
        iniciar_reenvio_automatico(app)
    return app


def registrar_erros(app):
    @app.errorhandler(ApiError)
    def _api_error(e):
        return jsonify(e.to_dict()), e.status

    @app.errorhandler(HTTPException)
    def _http(e):
        codigos = {404: "ROTA_NAO_ENCONTRADA", 405: "METODO_NAO_PERMITIDO", 413: "CORPO_MUITO_GRANDE"}
        return jsonify({"erro": {"codigo": codigos.get(e.code, f"HTTP_{e.code}"), "mensagem": e.description}}), e.code

    @app.errorhandler(Exception)
    def _inesperado(e):
        if isinstance(e, db.erros_de_integridade()):
            log.warning("Violação de integridade: %s", e)
            return jsonify({"erro": {"codigo": "VIOLACAO_INTEGRIDADE",
                                     "mensagem": "A operação viola uma regra de integridade dos dados."}}), 409
        if "OperationalError" in type(e).__name__:
            log.error("Banco indisponível: %s", e)
            return jsonify({"erro": {"codigo": "BANCO_INDISPONIVEL",
                                     "mensagem": "Banco de dados indisponível. Tente novamente."}}), 503
        log.exception("Erro não tratado em %s %s", request.method, request.path)
        return jsonify({"erro": {"codigo": "ERRO_INTERNO", "mensagem": "Erro interno do servidor."}}), 500


def registrar_cors(app):
    origens = [o.strip() for o in app.config["SDM"]["CORS_ORIGINS"].split(",") if o.strip()]
    if not origens:
        return

    @app.after_request
    def _cors(resp):
        origem = request.headers.get("Origin")
        if origem and ("*" in origens or origem in origens):
            resp.headers["Access-Control-Allow-Origin"] = origem
            resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            resp.headers["Vary"] = "Origin"
        return resp

    @app.route("/api/<path:_>", methods=["OPTIONS"])
    def _preflight(_):
        return "", 204


def iniciar_reenvio_automatico(app):
    """Thread que reenvia periodicamente as comunicações PENDENTE/ENVIADA ao governo."""
    intervalo = app.config["SDM"]["AUTO_RETRY_INTERVALO_S"]

    def laco():
        log.info("Reenvio automático ativo (a cada %.0fs).", intervalo)
        while True:
            time.sleep(intervalo)
            try:
                with app.app_context(), db.sessao(app) as conn:
                    resumo = integracao.reprocessar(conn, automatico=True)
                    if resumo["analisadas"]:
                        log.info("Reenvio automático: %s", resumo)
            except Exception:  # noqa: BLE001 - o worker nunca pode morrer
                log.exception("Falha no reenvio automático")

    threading.Thread(target=laco, name="reenvio-governo", daemon=True).start()
