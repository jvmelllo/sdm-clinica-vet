"""Apoio à DEMONSTRAÇÃO: liga/desliga a indisponibilidade do governo simulado pela interface.

Só existe com DEMO_SIMULACAO=1 (padrão em APP_ENV=dev). A chave da API governamental continua
no servidor da clínica: o navegador nunca a vê.
"""
import requests
from flask import Blueprint, current_app

from ..errors import ApiError
from ..security import login_required
from ._util import corpo, resposta

bp = Blueprint("demo", __name__, url_prefix="/api/demo")


def _chamar(metodo, json=None):
    cfg = current_app.config["SDM"]
    if not cfg["DEMO_SIMULACAO"]:
        raise ApiError(404, "ROTA_NAO_ENCONTRADA", "Endpoint inexistente.")
    try:
        r = requests.request(metodo, cfg["GOV_URL"].rstrip("/") + "/api/governo/simulacao", json=json,
                             headers={"X-API-Key": cfg["GOV_API_KEY"]}, timeout=2)
    except requests.exceptions.RequestException:
        raise ApiError(503, "GOVERNO_INDISPONIVEL", "A API governamental simulada não está no ar (processo parado).")
    return resposta(r.json(), r.status_code)


@bp.get("/governo/simulacao")
@login_required
def ver():
    return _chamar("GET")


@bp.put("/governo/simulacao")
@login_required
def definir():
    return _chamar("PUT", corpo())
