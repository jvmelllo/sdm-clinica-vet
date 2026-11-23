"""A documentação OpenAPI (Swagger) não pode divergir do código.

* todo endpoint /api/* registrado no Flask está documentado — e nada documentado deixou de existir;
* todos os $ref resolvem;
* os YAML em docs/openapi/ estão atualizados em relação ao gerador (scripts/gerar_openapi.py);
* /docs e /openapi.yaml respondem.
"""
import importlib.util
import os
import re

import pytest
import yaml

from governo_api.app import criar_app as criar_app_governo

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def gerador():
    spec = importlib.util.spec_from_file_location("gerar_openapi", os.path.join(RAIZ, "scripts", "gerar_openapi.py"))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def rotas_reais(app):
    return {(m, re.sub(r"<[^>]+>", "{}", r.rule)) for r in app.url_map.iter_rules() if r.rule.startswith("/api/")
            for m in r.methods - {"HEAD", "OPTIONS"}}


def _refs(no):
    if isinstance(no, dict):
        for k, v in no.items():
            if k == "$ref":
                yield v
            else:
                yield from _refs(v)
    elif isinstance(no, list):
        for v in no:
            yield from _refs(v)


def test_clinica_openapi_cobre_exatamente_as_rotas_do_flask(app, gerador):
    documentadas = gerador.caminhos_documentados(gerador.SPEC_CLINICA)
    reais = rotas_reais(app)
    assert reais - documentadas == set(), f"rotas SEM documentação: {sorted(reais - documentadas)}"
    assert documentadas - reais == set(), f"documentadas mas inexistentes: {sorted(documentadas - reais)}"


def test_governo_openapi_cobre_exatamente_as_rotas_do_flask(tmp_path, gerador):
    app_gov = criar_app_governo({"DB_BACKEND": "sqlite", "SQLITE_PATH": str(tmp_path / "gov.db")})
    documentadas = gerador.caminhos_documentados(gerador.SPEC_GOV)
    reais = rotas_reais(app_gov)
    assert reais - documentadas == set(), f"rotas SEM documentação: {sorted(reais - documentadas)}"
    assert documentadas - reais == set(), f"documentadas mas inexistentes: {sorted(documentadas - reais)}"


@pytest.mark.parametrize("nome", ["SPEC_CLINICA", "SPEC_GOV"])
def test_todos_os_refs_resolvem(gerador, nome):
    spec = getattr(gerador, nome)
    for r in set(_refs(spec)):
        _, _, tipo, chave = r.split("/")          # "#/components/schemas/Nome"
        assert chave in spec["components"][tipo], f"$ref quebrado: {r}"


@pytest.mark.parametrize("nome,arquivo", [("SPEC_CLINICA", "clinica.yaml"), ("SPEC_GOV", "governo.yaml")])
def test_arquivos_yaml_estao_atualizados(gerador, nome, arquivo):
    caminho = os.path.join(RAIZ, "docs", "openapi", arquivo)
    assert os.path.isfile(caminho), "rode: python scripts/gerar_openapi.py"
    esperado = yaml.safe_load(yaml.safe_dump(getattr(gerador, nome), sort_keys=False, allow_unicode=True))
    with open(caminho, encoding="utf-8") as f:
        assert yaml.safe_load(f) == esperado, f"{arquivo} desatualizado: rode python scripts/gerar_openapi.py"


def test_toda_operacao_tem_resposta_de_sucesso_e_resumo(gerador):
    for spec in (gerador.SPEC_CLINICA, gerador.SPEC_GOV):
        for caminho, ops in spec["paths"].items():
            for metodo, op in ops.items():
                assert op["summary"], f"{metodo} {caminho} sem resumo"
                assert any(c.startswith("2") for c in op["responses"]), f"{metodo} {caminho} sem resposta 2xx"


def test_swagger_e_arquivo_openapi_sao_servidos(anonimo):
    r = anonimo.get("/openapi.yaml")
    assert r.status_code == 200
    assert yaml.safe_load(r.data)["info"]["title"].startswith("API da Clínica")
    assert anonimo.get("/docs").status_code == 200
