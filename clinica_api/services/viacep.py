"""Consumo da API pública ViaCEP (https://viacep.com.br) com tratamento de falhas.

Falha                          -> resposta da NOSSA API
------------------------------------------------------------------
CEP com formato inválido        -> 422 VALIDACAO
CEP inexistente (erro:true)     -> 404 CEP_NAO_ENCONTRADO
Timeout                         -> 504 CEP_TIMEOUT
Serviço fora do ar / 5xx        -> 503 CEP_INDISPONIVEL
Resposta que não é JSON         -> 502 CEP_RESPOSTA_INVALIDA

Nos três últimos casos o frontend deixa o usuário preencher o endereço manualmente.
"""
import logging

import requests
from flask import current_app

from ..errors import ApiError
from ..validators import sanitiza_cep_param

log = logging.getLogger("clinica.viacep")


def consultar(cep):
    cep = sanitiza_cep_param(cep)
    cfg = current_app.config["SDM"]
    url = f"{cfg['VIACEP_URL'].rstrip('/')}/{cep}/json/"
    try:
        r = requests.get(url, timeout=cfg["VIACEP_TIMEOUT_S"], headers={"Accept": "application/json"})
    except requests.exceptions.Timeout:
        log.warning("ViaCEP timeout (%s)", cep)
        raise ApiError(504, "CEP_TIMEOUT", "O serviço de CEP demorou demais para responder. "
                       "Tente novamente ou preencha o endereço manualmente.")
    except requests.exceptions.RequestException as exc:
        log.warning("ViaCEP indisponível (%s): %s", cep, exc)
        raise ApiError(503, "CEP_INDISPONIVEL", "O serviço de CEP está indisponível no momento. "
                       "Preencha o endereço manualmente.")

    if r.status_code == 400:
        raise ApiError(422, "VALIDACAO", "CEP inválido.", {"cep": "Formato de CEP rejeitado pelo ViaCEP."})
    if r.status_code != 200:
        log.warning("ViaCEP respondeu HTTP %s (%s)", r.status_code, cep)
        raise ApiError(503, "CEP_INDISPONIVEL", f"O serviço de CEP respondeu com erro (HTTP {r.status_code}).")
    try:
        corpo = r.json()
    except ValueError:
        raise ApiError(502, "CEP_RESPOSTA_INVALIDA", "Resposta inesperada do serviço de CEP.")
    if not isinstance(corpo, dict):
        raise ApiError(502, "CEP_RESPOSTA_INVALIDA", "Resposta inesperada do serviço de CEP.")
    if corpo.get("erro") in (True, "true"):
        raise ApiError(404, "CEP_NAO_ENCONTRADO", "CEP não encontrado.", {"cep": cep})

    return {
        "cep": cep,
        "logradouro": corpo.get("logradouro") or "",
        "complemento": corpo.get("complemento") or "",
        "bairro": corpo.get("bairro") or "",
        "cidade": corpo.get("localidade") or "",
        "uf": corpo.get("uf") or "",
        "codigo_ibge": corpo.get("ibge") or None,
        "fonte": "ViaCEP",
    }
