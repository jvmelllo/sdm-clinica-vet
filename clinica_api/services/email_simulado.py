"""Simulação do envio de e-mail (permitido pelo enunciado, seção 3.1).

O "e-mail" é gravado em arquivo e no log da aplicação. Em ambiente de desenvolvimento
o código também pode voltar na resposta da API (EXPOR_CODIGO_NA_RESPOSTA) para facilitar
a demonstração; em produção isso deve ficar desligado.
"""
import logging
import os
from datetime import datetime

from flask import current_app

log = logging.getLogger("clinica.email")


def enviar(destino, assunto, corpo):
    linha = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] PARA={destino} ASSUNTO={assunto} | {corpo}"
    log.info("E-mail simulado: %s", linha)
    caminho = current_app.config["SDM"]["EMAIL_SIMULADO_ARQUIVO"]
    try:
        os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:  # a simulação nunca deve derrubar a requisição
        log.warning("Não foi possível gravar o e-mail simulado em %s", caminho)
