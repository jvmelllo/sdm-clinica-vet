"""ViaCEP FALSO para testes e demonstrações offline.

Imita o formato do serviço real (https://viacep.com.br/ws/<cep>/json/) e permite provocar
os cenários de falha exigidos pelo enunciado:

  CEP 01001000  -> Praça da Sé / SP            (válido)
  CEP 01310100  -> Avenida Paulista / SP       (válido)
  CEP 99999999  -> {"erro": "true"}            (CEP inexistente, como o ViaCEP real)
  CEP 11111111  -> demora 6 s                  (provoca TIMEOUT na clínica; padrão dela = 3 s)
  CEP 22222222  -> HTTP 500                    (serviço com erro)
  CEP 33333333  -> 200 com corpo que não é JSON

Uso:  python scripts/viacep_falso.py [porta]      (padrão 5002)
      e na clínica:  VIACEP_URL=http://127.0.0.1:5002/ws
"""
import os
import sys
import time

from flask import Flask, jsonify

ATRASO_S = float(os.environ.get("VIACEP_FALSO_ATRASO_S", "6"))   # precisa ser MAIOR que VIACEP_TIMEOUT_S

CONHECIDOS = {
    "01001000": {"cep": "01001-000", "logradouro": "Praça da Sé", "complemento": "lado ímpar", "bairro": "Sé",
                 "localidade": "São Paulo", "uf": "SP", "ibge": "3550308", "ddd": "11"},
    "01310100": {"cep": "01310-100", "logradouro": "Avenida Paulista", "complemento": "", "bairro": "Bela Vista",
                 "localidade": "São Paulo", "uf": "SP", "ibge": "3550308", "ddd": "11"},
}


def criar_app():
    app = Flask("viacep-falso")

    @app.get("/ws/<cep>/json/")
    def cep(cep):
        if len(cep) != 8 or not cep.isdigit():
            return "<h1>Bad Request (400)</h1>", 400
        if cep == "11111111":
            time.sleep(ATRASO_S)
        if cep == "22222222":
            return "erro interno", 500
        if cep == "33333333":
            return "<html>isto não é JSON</html>", 200
        if cep in CONHECIDOS:
            return jsonify(CONHECIDOS[cep])
        return jsonify({"erro": "true"})

    return app


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    print(f"ViaCEP FALSO em http://127.0.0.1:{porta}/ws/<cep>/json/")
    criar_app().run(host="127.0.0.1", port=porta, debug=False, threaded=True)
