"""Construtores de dados usados pelos testes."""
import itertools
from datetime import date, timedelta

from database.seed import cpf_com_digitos

_seq = itertools.count(100)


def novo_cpf():
    return cpf_com_digitos(f"{next(_seq):09d}")


def endereco(**over):
    base = {"cep": "01001000", "logradouro": "Praça da Sé", "numero": "10", "complemento": None,
            "bairro": "Sé", "cidade": "São Paulo", "uf": "SP", "codigo_ibge": "3550308"}
    return {**base, **over}


def tutor_payload(**over):
    n = next(_seq)
    base = {"nome_completo": f"Tutor Teste {n}", "cpf": novo_cpf(), "data_nascimento": "1990-05-20",
            "email": f"tutor{n}@example.com", "telefone": "11999990000", "endereco": endereco()}
    return {**base, **over}


def criar_tutor(api, **over):
    r = api.post("/api/tutores", tutor_payload(**over))
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def animal_payload(tutor_id, **over):
    base = {"nome": "Rex", "data_nascimento": "2022-01-10", "sexo": "MACHO", "cor": "Caramelo",
            "peso_atual": 12.5, "tutor_id": tutor_id, "especie_id": 1, "raca_id": 1}
    return {**base, **over}


def criar_animal(api, tutor_id=None, **over):
    tutor_id = tutor_id or criar_tutor(api)["id"]
    r = api.post("/api/animais", animal_payload(tutor_id, **over))
    assert r.status_code == 201, r.get_json()
    return r.get_json()


_chips = itertools.count(985112345678000)


def novo_microchip():
    return str(next(_chips))


def vincular_chip(api, animal_id, codigo=None, **extra):
    codigo = codigo or novo_microchip()
    r = api.post(f"/api/animais/{animal_id}/microchip", {"codigo": codigo, **extra})
    return r, codigo


def animal_com_chip(api, **over):
    a = criar_animal(api, **over)
    r, codigo = vincular_chip(api, a["id"])
    assert r.status_code == 201, r.get_json()
    return a, codigo, r.get_json()


def vacina_payload(animal_id, tipo="POLIVALENTE", **over):
    ontem = (date.today() - timedelta(days=1)).isoformat()
    base = {"animal_id": animal_id, "nome_vacina": "Vacina Teste", "tipo_vacina": tipo,
            "fabricante": "Lab Exemplo", "numero_lote": "L-2026-01", "data_aplicacao": ontem,
            "dose": "1ª dose", "via_aplicacao": "SUBCUTANEA",
            "data_proxima_dose": (date.today() + timedelta(days=30)).isoformat(),
            "validade_lote": (date.today() + timedelta(days=300)).isoformat()}
    return {**base, **over}


def antirrabica(api, animal_id, **over):
    return api.post("/api/vacinas", vacina_payload(animal_id, "ANTIRRABICA", nome_vacina="Antirrábica", **over))
