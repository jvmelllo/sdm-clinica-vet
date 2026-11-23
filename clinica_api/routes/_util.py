"""Utilitários das rotas (camada HTTP)."""
from flask import jsonify, request

from ..errors import ApiError


def corpo():
    dados = request.get_json(silent=True)
    if dados is None:
        raise ApiError(400, "JSON_INVALIDO", "Corpo JSON ausente ou malformado (use Content-Type: application/json).")
    return dados


def resposta(dados, status=200):
    return jsonify(dados), status
