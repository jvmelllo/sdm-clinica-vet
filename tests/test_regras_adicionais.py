"""Catálogos, veterinários, painel, formato de erros e fluxo de atendimento das consultas."""
from datetime import datetime, timedelta

from tests.helpers import animal_com_chip, criar_animal, novo_cpf


def _erro(r):
    return r.get_json()["erro"]


def test_catalogo_de_especies_e_racas(api):
    r = api.post("/api/especies", {"nome": "Réptil", "descricao": "Répteis de companhia"})
    assert r.status_code == 201
    esp = r.get_json()
    assert api.post("/api/especies", {"nome": "Réptil"}).status_code == 409
    r = api.post("/api/racas", {"nome": "Iguana Verde", "especie_id": esp["id"]})
    assert r.status_code == 201 and r.get_json()["especie_nome"] == "Réptil"
    assert api.post("/api/racas", {"nome": "Iguana Verde", "especie_id": esp["id"]}).status_code == 409
    assert api.post("/api/racas", {"nome": "Mesmo nome, outra espécie", "especie_id": 99999}).status_code == 404
    lista = api.get(f"/api/racas?especie_id={esp['id']}").get_json()
    assert [x["nome"] for x in lista] == ["Iguana Verde"]
    assert api.put(f"/api/especies/{esp['id']}", {"nome": "Répteis", "descricao": "x"}).get_json()["nome"] == "Répteis"
    # inativar espécie inativa as raças; espécie em uso por animal ativo não pode ser inativada
    assert api.delete(f"/api/especies/{esp['id']}").get_json()["situacao"] == "INATIVA"
    assert api.get(f"/api/racas?especie_id={esp['id']}").get_json()[0]["situacao"] == "INATIVA"
    r = api.delete("/api/especies/1")                      # Cão tem animais ativos? (seed) -> sim
    assert r.status_code == 409 and _erro(r)["codigo"] == "ESPECIE_EM_USO"
    assert api.post("/api/animais", {"nome": "R", "sexo": "MACHO", "cor": "v", "peso_atual": 1, "idade_estimada_meses": 5,
                                     "tutor_id": 1, "especie_id": esp["id"]}).status_code == 422   # espécie inativa


def test_cadastro_de_veterinario_valida_e_nao_expoe_hash(api):
    base = {"nome_completo": "Dr. Fulano de Tal", "cpf": novo_cpf(), "crmv_numero": "55555", "crmv_uf": "RS",
            "email": "fulano@clinicavet.example", "telefone": "51999990000", "senha": "Segura@123"}
    r = api.post("/api/veterinarios", base)
    assert r.status_code == 201 and "senha_hash" not in r.get_json() and r.get_json()["senha_confirmada"] is False
    assert api.post("/api/veterinarios", {**base, "cpf": novo_cpf()}).status_code == 409           # e-mail repetido
    r = api.post("/api/veterinarios", {**base, "email": "x@x.com", "cpf": novo_cpf(), "senha": "curta"})
    assert r.status_code == 422 and "senha" in _erro(r)["detalhes"]
    r = api.post("/api/veterinarios", {**base, "email": "y@x.com", "cpf": novo_cpf(), "senha": "somenteletras"})
    assert r.status_code == 422
    r = api.post("/api/veterinarios", {**base, "email": "z@x.com", "cpf": novo_cpf(), "crmv_uf": "XX"})
    assert r.status_code == 422 and "crmv_uf" in _erro(r)["detalhes"]


def test_painel_resumo(api, governo):
    animal_com_chip(api)
    r = api.get("/api/resumo").get_json()
    assert r["animais_ativos"] == 5 and r["tutores_ativos"] == 4 and r["governo_disponivel"] is True
    assert r["integracoes"] == {"PENDENTE": 0, "ENVIADA": 0, "CONFIRMADA": 1, "FALHA": 0}
    assert r["vacinas_com_reforco_atrasado"] == 1          # polivalente do seed (reforço previsto em 2026-10-15)


def test_erros_sempre_em_json_padronizado(api, anonimo):
    r = anonimo.c.get("/api/rota-inexistente")
    assert r.status_code == 404 and _erro(r)["codigo"] == "ROTA_NAO_ENCONTRADA"
    r = api.c.open("/api/tutores/1", method="PATCH", headers=api._h())
    assert r.status_code == 405 and _erro(r)["codigo"] == "METODO_NAO_PERMITIDO"
    r = api.c.post("/api/tutores", data="{isto não é json", headers={**api._h(), "Content-Type": "application/json"})
    assert r.status_code == 400 and _erro(r)["codigo"] == "JSON_INVALIDO"
    assert api.get("/api/tutores/999999").status_code == 404
    assert api.get("/api/animais/abc").status_code == 404           # id não numérico não casa com a rota
    assert api.get("/api/tutores?limite=abc").status_code == 422


def test_sincronizacao_manual_do_animal(api, governo):
    a, codigo, _ = animal_com_chip(api)
    r = api.post(f"/api/animais/{a['id']}/sincronizar")                # já confirmado -> envia atualização dos dados
    assert r.status_code == 200 and r.get_json()["operacao"]["tipo_operacao"] == "ATUALIZACAO_ANIMAL"
    assert r.get_json()["integracao_governo"]["sincronizado"] is True
    sem_chip = criar_animal(api)
    assert api.post(f"/api/animais/{sem_chip['id']}/sincronizar").status_code == 422
    estado = api.get(f"/api/animais/{a['id']}/integracao-governo").get_json()
    assert estado["situacao_cadastro"] == "CONFIRMADA" and len(estado["operacoes"]) == 2


def test_frontend_e_estaticos_sao_servidos_pela_api(anonimo):
    r = anonimo.c.get("/")
    assert r.status_code == 200 and b"<html" in r.data.lower()
    assert anonimo.c.get("/api/status").get_json()["api"] == "ok"


def test_atendimento_da_consulta_agendada_e_peso_atual(api):
    """Fluxo usado pela tela: AGENDADA -> REALIZADA, AGENDADA -> NAO_COMPARECEU, edição e peso atual."""
    a = criar_animal(api, peso_atual=10.0)
    fmt = "%Y-%m-%dT%H:%M"                         # formato que o <input datetime-local> envia
    agora = datetime.now()
    # o formulário envia os campos vazios como null / "" e o veterinário logado assume o atendimento
    vazios = {k: None for k in ("peso_kg", "temperatura_c", "anamnese", "sintomas", "diagnostico", "tratamento",
                                "prescricao_medicamentos", "observacoes")}
    corpo = {"animal_id": a["id"], "motivo": "Retorno vacinal", "situacao": "AGENDADA", **vazios,
             "data_hora": (agora + timedelta(days=3)).strftime(fmt)}
    cid = api.post("/api/consultas", corpo).get_json()["id"]

    # atender: a data passa a ser "agora" (realizada não pode estar no futuro) e o peso entra no animal
    atendida = {**corpo, "situacao": "REALIZADA", "data_hora": agora.strftime(fmt), "peso_kg": 11.2,
                "diagnostico": "Saudável", "anamnese": ""}
    r = api.put(f"/api/consultas/{cid}", atendida)
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["situacao"] == "REALIZADA" and r.get_json()["diagnostico"] == "Saudável"
    assert api.get(f"/api/animais/{a['id']}").get_json()["peso_atual"] == 11.2

    # consulta antiga registrada depois (ou corrigida depois) não pode sobrescrever o peso mais novo
    antiga = {**corpo, "situacao": "REALIZADA", "data_hora": (agora - timedelta(days=40)).strftime(fmt), "peso_kg": 9.0}
    antiga_id = api.post("/api/consultas", antiga).get_json()["id"]
    assert api.get(f"/api/animais/{a['id']}").get_json()["peso_atual"] == 11.2
    assert api.put(f"/api/consultas/{antiga_id}", {**antiga, "peso_kg": 9.5}).status_code == 200
    assert api.get(f"/api/animais/{a['id']}").get_json()["peso_atual"] == 11.2
    # corrigir a consulta mais recente atualiza o peso
    assert api.put(f"/api/consultas/{cid}", {**atendida, "peso_kg": 11.5}).status_code == 200
    assert api.get(f"/api/animais/{a['id']}").get_json()["peso_atual"] == 11.5

    # "Faltou": reenvia o registro com a situação trocada
    faltou_id = api.post("/api/consultas", corpo).get_json()["id"]
    r = api.put(f"/api/consultas/{faltou_id}", {**corpo, "situacao": "NAO_COMPARECEU"})
    assert r.status_code == 200 and r.get_json()["situacao"] == "NAO_COMPARECEU"
    assert api.get(f"/api/animais/{a['id']}").get_json()["peso_atual"] == 11.5      # falta não mexe no peso

    # cancelada não volta a ser editada; realizada não pode ser cancelada
    cancelada_id = api.post("/api/consultas", corpo).get_json()["id"]
    assert api.delete(f"/api/consultas/{cancelada_id}").get_json()["situacao"] == "CANCELADA"
    r = api.put(f"/api/consultas/{cancelada_id}", corpo)
    assert r.status_code == 409 and _erro(r)["codigo"] == "CONSULTA_CANCELADA"
    r = api.delete(f"/api/consultas/{cid}")
    assert r.status_code == 409 and _erro(r)["codigo"] == "CONSULTA_REALIZADA"
