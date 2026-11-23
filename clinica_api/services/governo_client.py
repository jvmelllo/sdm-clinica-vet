"""Cliente HTTP da API governamental simulada.

Classifica cada tentativa em uma categoria que o serviço de integração usa para
decidir a situação da operação:

  OK            200/201 — recebido e processado (ou repetição idempotente)
  INDISPONIVEL  conexão recusada, timeout de conexão, 503/408/429 — o governo NÃO processou
  INCERTO       timeout de leitura, 500/502/504 — pode ter processado; reenviar é seguro
                porque toda chamada leva Idempotency-Key
  REJEITADO     demais 4xx (validação, duplicidade, não autorizado...) — reenviar igual não adianta
"""
import logging
from dataclasses import dataclass, field

import requests
from flask import current_app

log = logging.getLogger("clinica.governo")


@dataclass
class Resultado:
    categoria: str
    status: int | None = None
    corpo: dict = field(default_factory=dict)
    mensagem: str = ""


def _msg_erro(corpo, padrao):
    erro = (corpo or {}).get("erro")
    if isinstance(erro, dict):
        extra = f" {erro['detalhes']}" if erro.get("detalhes") else ""
        return f"{erro.get('codigo', 'ERRO')}: {erro.get('mensagem', padrao)}{extra}"
    return padrao


def chamar(metodo, caminho, payload, chave_idempotencia):
    cfg = current_app.config["SDM"]
    url = cfg["GOV_URL"].rstrip("/") + caminho
    cabecalhos = {"X-API-Key": cfg["GOV_API_KEY"], "Idempotency-Key": chave_idempotencia,
                  "Accept": "application/json"}
    try:
        r = requests.request(metodo, url, json=payload, headers=cabecalhos, timeout=cfg["GOV_TIMEOUT_S"])
    except requests.exceptions.ConnectTimeout:
        return Resultado("INDISPONIVEL", mensagem="Timeout ao conectar na API governamental.")
    except requests.exceptions.ReadTimeout:
        return Resultado("INCERTO", mensagem="A API governamental não respondeu a tempo (resultado desconhecido).")
    except requests.exceptions.ConnectionError:
        return Resultado("INDISPONIVEL", mensagem="Não foi possível conectar à API governamental.")
    except requests.exceptions.RequestException as exc:
        log.exception("Falha inesperada ao chamar o governo")
        return Resultado("INDISPONIVEL", mensagem=f"Falha de comunicação: {exc}")

    try:
        corpo = r.json()
        if not isinstance(corpo, dict):
            corpo = {}
    except ValueError:
        corpo = {}

    if r.status_code in (200, 201):
        return Resultado("OK", r.status_code, corpo)
    if r.status_code in (503, 408, 429):
        return Resultado("INDISPONIVEL", r.status_code, corpo, _msg_erro(corpo, f"Serviço indisponível (HTTP {r.status_code})."))
    if r.status_code >= 500:
        return Resultado("INCERTO", r.status_code, corpo, _msg_erro(corpo, f"Erro no servidor governamental (HTTP {r.status_code})."))
    return Resultado("REJEITADO", r.status_code, corpo, _msg_erro(corpo, f"Requisição rejeitada (HTTP {r.status_code})."))


def verificar_saude():
    """Ping simples usado pelo painel (não afeta nenhuma integração)."""
    cfg = current_app.config["SDM"]
    try:
        r = requests.get(cfg["GOV_URL"].rstrip("/") + "/api/governo/health", timeout=1.5)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False
