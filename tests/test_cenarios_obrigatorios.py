"""Os 16 testes obrigatórios do enunciado (seção 9), um ou mais testes por item.

O nome de cada teste começa com T01..T16 para o relatório (scripts/gerar_relatorio_testes.py)
mapear o resultado de volta para a lista do PDF.
"""
from datetime import date, datetime, timedelta

import requests

from clinica_api.db import sessao
from clinica_api.services import integracao
from tests.conftest import EMAIL_ANA, SENHA
from tests.helpers import (animal_com_chip, antirrabica, criar_animal, criar_tutor, endereco, novo_cpf,
                           tutor_payload, vacina_payload, vincular_chip)


def _corpo(r):
    return r.get_json()


def _erro(r):
    return _corpo(r)["erro"]


# ====================================================================== AUTENTICAÇÃO
def test_T01_login_de_veterinario_ativo_com_senha_confirmada(anonimo):
    r = anonimo.c.post("/api/auth/login", json={"email": EMAIL_ANA, "senha": SENHA})
    assert r.status_code == 200
    corpo = _corpo(r)
    assert corpo["token"] and corpo["tipo"] == "Bearer"
    assert corpo["veterinario"]["ultimo_acesso_em"] is not None
    assert "senha_hash" not in corpo["veterinario"] and "senha" not in corpo["veterinario"]
    anonimo.token = corpo["token"]
    assert anonimo.get("/api/auth/me").status_code == 200


def test_T01_logout_encerra_a_sessao(api):
    assert api.get("/api/tutores").status_code == 200
    assert api.post("/api/auth/logout").status_code == 200
    r = api.get("/api/tutores")
    assert r.status_code == 401 and _erro(r)["codigo"] == "SESSAO_ENCERRADA"


def test_T01_endpoints_privados_exigem_autenticacao(anonimo):
    protegidos = [("get", "/api/tutores"), ("post", "/api/tutores"), ("get", "/api/animais"),
                  ("post", "/api/animais"), ("post", "/api/animais/1/microchip"), ("post", "/api/consultas"),
                  ("post", "/api/vacinas"), ("get", "/api/integracoes"), ("get", "/api/cep/01001000"),
                  ("get", "/api/veterinarios"), ("get", "/api/resumo")]
    for metodo, caminho in protegidos:
        r = getattr(anonimo.c, metodo)(caminho)
        assert r.status_code == 401, (metodo, caminho)
        assert _erro(r)["codigo"] == "NAO_AUTENTICADO"
    r = anonimo.c.get("/api/tutores", headers={"Authorization": "Bearer token.invalido.aqui"})
    assert r.status_code == 401 and _erro(r)["codigo"] == "TOKEN_INVALIDO"


def test_T02_bloqueio_de_veterinario_inativo(anonimo):
    r = anonimo.c.post("/api/auth/login", json={"email": "bruno.lima@clinicavet.example", "senha": SENHA})
    assert r.status_code == 403
    assert _erro(r)["codigo"] == "VETERINARIO_INATIVO"
    assert "token" not in _corpo(r)


def test_T02_inativar_derruba_o_acesso_imediatamente(api, app):
    novo = api.post("/api/veterinarios", {
        "nome_completo": "Dr. Novo Colega", "cpf": novo_cpf(), "crmv_numero": "99887", "crmv_uf": "PR",
        "email": "novo.colega@clinicavet.example", "telefone": "41988887777", "senha": "Outra@1234"})
    assert novo.status_code == 201
    codigo = _corpo(novo)["codigo_simulado"]
    anon = api.sem_token()
    assert anon.c.post("/api/auth/confirmar-senha", json={"email": "novo.colega@clinicavet.example", "codigo": codigo}).status_code == 200
    anon.login("novo.colega@clinicavet.example", "Outra@1234")
    assert anon.get("/api/tutores").status_code == 200

    assert api.delete(f"/api/veterinarios/{_corpo(novo)['id']}").status_code == 200   # inativa
    r = anon.get("/api/tutores")                      # inativar revoga as sessões abertas
    assert r.status_code == 401 and _erro(r)["codigo"] == "SESSAO_ENCERRADA"
    r = anon.c.post("/api/auth/login", json={"email": "novo.colega@clinicavet.example", "senha": "Outra@1234"})
    assert r.status_code == 403 and _erro(r)["codigo"] == "VETERINARIO_INATIVO"
    assert api.delete("/api/veterinarios/1").status_code == 422                       # não pode se autoinativar


def test_T03_bloqueio_de_veterinario_com_senha_nao_confirmada(anonimo):
    r = anonimo.c.post("/api/auth/login", json={"email": "carla.mendes@clinicavet.example", "senha": SENHA})
    assert r.status_code == 403
    assert _erro(r)["codigo"] == "SENHA_NAO_CONFIRMADA"
    assert "token" not in _corpo(r)


def test_T03_confirmacao_por_codigo_libera_o_acesso(anonimo, app, tmp_path):
    email = "carla.mendes@clinicavet.example"
    r = anonimo.c.post("/api/auth/reenviar-codigo", json={"email": email})
    assert r.status_code == 202
    codigo = _corpo(r)["codigo_simulado"]
    assert "E-mail simulado" or True
    assert codigo in (tmp_path / "emails.log").read_text(encoding="utf-8")   # o "e-mail" foi simulado em arquivo

    errado = "000000" if codigo != "000000" else "111111"
    r = anonimo.c.post("/api/auth/confirmar-senha", json={"email": email, "codigo": errado})
    assert r.status_code == 400 and _erro(r)["codigo"] == "CODIGO_INVALIDO"
    assert anonimo.c.post("/api/auth/login", json={"email": email, "senha": SENHA}).status_code == 403   # ainda bloqueada

    r = anonimo.c.post("/api/auth/confirmar-senha", json={"email": email, "codigo": codigo})
    assert r.status_code == 200 and _corpo(r)["veterinario"]["senha_confirmada"] is True
    assert _corpo(r)["veterinario"]["senha_confirmada_em"]
    assert anonimo.c.post("/api/auth/login", json={"email": email, "senha": SENHA}).status_code == 200
    # o código é de uso único
    r = anonimo.c.post("/api/auth/confirmar-senha", json={"email": email, "codigo": codigo})
    assert r.status_code == 200 and "já confirmada" in _corpo(r)["mensagem"]


def test_T03_codigo_bloqueado_apos_muitas_tentativas(anonimo, app):
    email = "carla.mendes@clinicavet.example"
    codigo = _corpo(anonimo.c.post("/api/auth/reenviar-codigo", json={"email": email}))["codigo_simulado"]
    errado = "000000" if codigo != "000000" else "111111"
    for _ in range(5):
        assert anonimo.c.post("/api/auth/confirmar-senha", json={"email": email, "codigo": errado}).status_code == 400
    r = anonimo.c.post("/api/auth/confirmar-senha", json={"email": email, "codigo": codigo})   # até o certo é recusado
    assert r.status_code == 429 and _erro(r)["codigo"] == "CODIGO_BLOQUEADO"


def test_T04_rejeicao_de_senha_incorreta(anonimo):
    r = anonimo.c.post("/api/auth/login", json={"email": EMAIL_ANA, "senha": "SenhaErrada1"})
    assert r.status_code == 401 and _erro(r)["codigo"] == "CREDENCIAIS_INVALIDAS"
    assert "token" not in _corpo(r)
    # e-mail inexistente recebe exatamente a mesma resposta (não revela quem está cadastrado)
    r2 = anonimo.c.post("/api/auth/login", json={"email": "ninguem@clinicavet.example", "senha": "SenhaErrada1"})
    assert r2.status_code == 401 and _erro(r2) == _erro(r)
    # veterinário inativo com senha ERRADA também não vaza o motivo do bloqueio
    r3 = anonimo.c.post("/api/auth/login", json={"email": "bruno.lima@clinicavet.example", "senha": "SenhaErrada1"})
    assert r3.status_code == 401


def test_T04_senha_nunca_e_guardada_em_texto_puro(app):
    from clinica_api.db import sessao
    with sessao(app) as conn:
        for vet in conn.consultar("SELECT senha_hash FROM veterinario"):
            assert SENHA not in vet["senha_hash"] and vet["senha_hash"].startswith(("scrypt:", "pbkdf2:"))


# ====================================================================== TUTORES
def test_T05_cadastro_de_tutor_e_cpf_duplicado(api):
    payload = tutor_payload()
    r = api.post("/api/tutores", payload)
    assert r.status_code == 201
    t = _corpo(r)
    assert t["situacao"] == "ATIVO" and t["data_cadastro"] and t["endereco"]["cep"] == "01001000"
    assert api.get(f"/api/tutores/{t['id']}").status_code == 200

    # mesmo CPF, agora formatado com máscara: continua sendo duplicidade
    c = payload["cpf"]
    formatado = f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
    r = api.post("/api/tutores", tutor_payload(cpf=formatado, email="outro@example.com"))
    assert r.status_code == 409 and _erro(r)["codigo"] == "CPF_DUPLICADO"


def test_T05_cpf_invalido_e_demais_validacoes(api):
    r = api.post("/api/tutores", tutor_payload(cpf="111.111.111-11"))
    assert r.status_code == 422 and "cpf" in _erro(r)["detalhes"]
    r = api.post("/api/tutores", tutor_payload(cpf="123.456.789-00"))
    assert r.status_code == 422
    r = api.post("/api/tutores", tutor_payload(email="isso-nao-e-email", telefone="123",
                                               data_nascimento="2999-01-01"))
    d = _erro(r)["detalhes"]
    assert r.status_code == 422 and {"email", "telefone", "data_nascimento"} <= set(d)
    r = api.post("/api/tutores", {k: v for k, v in tutor_payload().items() if k != "endereco"})
    assert r.status_code == 422 and "endereco" in _erro(r)["detalhes"]


def test_T05_alterar_e_inativar_tutor(api):
    t = criar_tutor(api)
    novo = tutor_payload(cpf=t["cpf"], nome_completo="Nome Alterado Silva",
                         endereco=endereco(numero="999", bairro="Outro Bairro"))
    r = api.put(f"/api/tutores/{t['id']}", novo)
    assert r.status_code == 200 and _corpo(r)["nome_completo"] == "Nome Alterado Silva"
    assert _corpo(r)["endereco"]["numero"] == "999" and _corpo(r)["endereco_id"] == t["endereco_id"]
    a = criar_animal(api, t["id"])
    r = api.delete(f"/api/tutores/{t['id']}")                     # tem animal ativo
    assert r.status_code == 409 and _erro(r)["codigo"] == "TUTOR_COM_ANIMAIS_ATIVOS"
    api.delete(f"/api/animais/{a['id']}")
    r = api.delete(f"/api/tutores/{t['id']}")
    assert r.status_code == 200 and _corpo(r)["situacao"] == "INATIVO"
    assert api.post(f"/api/tutores/{t['id']}/reativar").status_code == 200


# ====================================================================== CEP
def test_T06_consulta_de_cep_valido(api):
    r = api.get("/api/cep/01001-000")
    assert r.status_code == 200
    e = _corpo(r)
    assert (e["cep"], e["logradouro"], e["bairro"], e["cidade"], e["uf"], e["codigo_ibge"]) == (
        "01001000", "Praça da Sé", "Sé", "São Paulo", "SP", "3550308")


def test_T06_cep_inexistente_e_formato_invalido(api):
    r = api.get("/api/cep/99999999")
    assert r.status_code == 404 and _erro(r)["codigo"] == "CEP_NAO_ENCONTRADO"
    r = api.get("/api/cep/123")
    assert r.status_code == 422


def test_T06_timeout_e_indisponibilidade_do_servico_de_cep(api):
    r = api.get("/api/cep/11111111")                     # o ViaCEP falso demora 2,5 s; o limite é 0,8 s
    assert r.status_code == 504 and _erro(r)["codigo"] == "CEP_TIMEOUT"
    r = api.get("/api/cep/22222222")
    assert r.status_code == 503 and _erro(r)["codigo"] == "CEP_INDISPONIVEL"
    r = api.get("/api/cep/33333333")
    assert r.status_code == 502 and _erro(r)["codigo"] == "CEP_RESPOSTA_INVALIDA"
    api.app.config["SDM"]["VIACEP_URL"] = "http://127.0.0.1:9/ws"      # nada escutando nessa porta
    r = api.get("/api/cep/01001000")
    assert r.status_code == 503 and _erro(r)["codigo"] == "CEP_INDISPONIVEL"


def test_T06_endereco_pode_ser_completado_manualmente_quando_o_cep_falha(api):
    # CEP geral (sem logradouro/bairro): o usuário digita os campos que faltam
    r = api.post("/api/tutores", tutor_payload(endereco=endereco(cep="22222222", logradouro="Rua Digitada à Mão",
                                                                 bairro="Bairro Manual", cidade="Cidade Pequena",
                                                                 uf="MG", codigo_ibge=None)))
    assert r.status_code == 201 and _corpo(r)["endereco"]["codigo_ibge"] is None


# ====================================================================== ANIMAL + MICROCHIP
def test_T07_cadastro_de_animal_e_vinculo_de_microchip(api, governo):
    a = criar_animal(api)
    assert a["microchip_atual"] is None and a["integracao_governo"]["situacao_cadastro"] == "SEM_MICROCHIP"
    assert a["tutor_nome"] and a["especie_nome"] == "Cão" and a["raca_nome"] == "Labrador Retriever"

    r, codigo = vincular_chip(api, a["id"])
    assert r.status_code == 201
    v = _corpo(r)["vinculo"]
    assert v["codigo_microchip"] == codigo and v["veterinario_id"] == 1 and v["data_vinculo"]
    assert v["veterinario_nome"] == "Dra. Ana Souza" and v["situacao"] == "ATIVO"

    gov = _corpo(r)["integracao_governo"]
    assert gov["tipo_operacao"] == "CADASTRO_ANIMAL" and gov["situacao"] == "CONFIRMADA"
    assert gov["protocolo_externo"].startswith("GOV-")
    atual = _corpo(api.get(f"/api/animais/{a['id']}"))
    assert atual["microchip_atual"]["codigo"] == codigo and atual["integracao_governo"]["sincronizado"] is True
    registrado = governo.animal(codigo)
    assert registrado.status_code == 200 and registrado.json()["nome"] == "Rex"


def test_T07_animal_exige_tutor_e_raca_compativel_com_a_especie(api):
    r = api.post("/api/animais", {k: v for k, v in
                                  {"nome": "SemTutor", "sexo": "MACHO", "cor": "Preto", "peso_atual": 3,
                                   "data_nascimento": "2023-01-01", "especie_id": 1}.items()})
    assert r.status_code == 422 and "tutor_id" in _erro(r)["detalhes"]
    t = criar_tutor(api)
    r = api.post("/api/animais", {"nome": "Mimi", "sexo": "FEMEA", "cor": "Cinza", "peso_atual": 4,
                                  "data_nascimento": "2023-01-01", "tutor_id": t["id"],
                                  "especie_id": 2, "raca_id": 1})          # raça 1 é de Cão, espécie 2 é Gato
    assert r.status_code == 422 and _erro(r)["codigo"] == "RACA_INCOMPATIVEL"
    r = api.post("/api/animais", {"nome": "Mimi", "sexo": "FEMEA", "cor": "Cinza", "peso_atual": 4,
                                  "idade_estimada_meses": 8, "tutor_id": t["id"], "especie_id": 2})  # sem raça definida
    assert r.status_code == 201 and _corpo(r)["sem_raca_definida"] is True
    r = api.post("/api/animais", {"nome": "X", "sexo": "MACHO", "cor": "a", "peso_atual": 1, "tutor_id": t["id"],
                                  "especie_id": 1})                         # sem data nem idade
    assert r.status_code == 422


def test_T08_rejeicao_de_microchip_ja_utilizado(api, governo):
    a1, codigo, _ = animal_com_chip(api)
    a2 = criar_animal(api)
    r, _ = vincular_chip(api, a2["id"], codigo)
    assert r.status_code == 409 and _erro(r)["codigo"] == "MICROCHIP_JA_UTILIZADO"
    assert _corpo(api.get(f"/api/animais/{a2['id']}"))["microchip_atual"] is None
    # nada foi enviado ao governo para o segundo animal
    assert api.get(f"/api/animais/{a2['id']}/integracao-governo").get_json()["operacoes"] == []


def test_T08_formato_do_microchip_e_um_chip_por_animal(api):
    a = criar_animal(api)
    for ruim in ("123", "98511234567890A", "9851123456789012"):
        r, _ = vincular_chip(api, a["id"], ruim)
        assert r.status_code == 422, ruim
    r, c1 = vincular_chip(api, a["id"])
    assert r.status_code == 201
    r, _ = vincular_chip(api, a["id"])                                         # segundo chip sem pedir substituição
    assert r.status_code == 409 and _erro(r)["codigo"] == "ANIMAL_JA_POSSUI_MICROCHIP"


def test_T08_substituicao_de_microchip_preserva_o_historico(api, governo):
    a, antigo, _ = animal_com_chip(api)
    r, _ = vincular_chip(api, a["id"], substituir=True)                        # falta o motivo
    assert r.status_code == 422
    r, novo = vincular_chip(api, a["id"], substituir=True, motivo_substituicao="Chip antigo com defeito de leitura")
    assert r.status_code == 201
    hist = _corpo(api.get(f"/api/animais/{a['id']}/microchips"))
    assert [h["codigo_microchip"] for h in hist] == [novo, antigo]
    assert hist[0]["situacao"] == "ATIVO" and hist[1]["situacao"] == "SUBSTITUIDO"
    assert hist[1]["motivo_substituicao"] and hist[1]["data_substituicao"]
    assert _corpo(api.get(f"/api/animais/{a['id']}"))["microchip_atual"]["codigo"] == novo
    # o chip antigo continua "usado": não pode ser reaproveitado por outro animal
    outro = criar_animal(api)
    assert vincular_chip(api, outro["id"], antigo)[0].status_code == 409


# ====================================================================== CONSULTAS
def test_T09_registro_de_consulta_e_historico_clinico(api):
    a = criar_animal(api, peso_atual=10.0)
    agora = datetime.now()
    c1 = {"animal_id": a["id"], "data_hora": (agora - timedelta(days=30)).strftime("%Y-%m-%d %H:%M"),
          "motivo": "Vômito", "anamnese": "Comeu algo na rua", "sintomas": "Vômito, apatia",
          "diagnostico": "Gastrite", "tratamento": "Dieta leve", "prescricao_medicamentos": "Omeprazol 10 mg",
          "peso_kg": 10.4, "temperatura_c": 39.1, "observacoes": "Retorno em 7 dias", "situacao": "REALIZADA"}
    r = api.post("/api/consultas", c1)
    assert r.status_code == 201
    c = _corpo(r)
    assert c["veterinario_id"] == 1 and c["veterinario_nome"] == "Dra. Ana Souza" and c["animal_nome"] == "Rex"
    assert c["temperatura_c"] == 39.1 and c["situacao"] == "REALIZADA"
    api.post("/api/consultas", {**c1, "data_hora": (agora - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                                "motivo": "Retorno", "peso_kg": 10.1})

    hist = _corpo(api.get(f"/api/animais/{a['id']}/consultas"))
    assert [h["motivo"] for h in hist] == ["Retorno", "Vômito"]                  # mais recente primeiro
    assert _corpo(api.get(f"/api/animais/{a['id']}"))["peso_atual"] == 10.1       # consulta atualiza o peso atual
    assert api.get(f"/api/consultas/{c['id']}").status_code == 200


def test_T09_regras_da_consulta(api):
    a = criar_animal(api)
    base = {"animal_id": a["id"], "motivo": "Check-up", "data_hora": "2999-01-01 10:00"}
    assert api.post("/api/consultas", {**base, "situacao": "REALIZADA"}).status_code == 422     # realizada no futuro
    r = api.post("/api/consultas", {**base, "situacao": "AGENDADA", "temperatura_c": 50})
    assert r.status_code == 422 and "temperatura_c" in _erro(r)["detalhes"]
    r = api.post("/api/consultas", {**base, "situacao": "AGENDADA"})
    assert r.status_code == 201
    cid = _corpo(r)["id"]
    r = api.put(f"/api/consultas/{cid}", {**base, "situacao": "NAO_COMPARECEU"})
    assert r.status_code == 200 and _corpo(r)["situacao"] == "NAO_COMPARECEU"
    assert api.delete(f"/api/consultas/{cid}").status_code == 200                              # cancela (exclusão lógica)
    assert api.put(f"/api/consultas/{cid}", {**base, "situacao": "AGENDADA"}).status_code == 409
    inativa = criar_animal(api)
    api.delete(f"/api/animais/{inativa['id']}")
    assert api.post("/api/consultas", {**base, "animal_id": inativa["id"]}).status_code == 422
    assert api.get("/api/animais/99999/consultas").status_code == 404


# ====================================================================== VACINAS (não antirrábica)
def test_T10_registro_de_vacina_e_proximas_doses(api):
    a = criar_animal(api)
    r = api.post("/api/vacinas", vacina_payload(a["id"], nome_vacina="V10"))
    assert r.status_code == 201
    v = _corpo(r)["vacina"]
    assert v["situacao"] == "APLICADA" and v["antirrabica"] is False and v["veterinario_id"] == 1
    assert v["comunicacao_governo"]["obrigatoria"] is False

    amanha = (date.today() + timedelta(days=1)).isoformat()
    api.post("/api/vacinas", vacina_payload(a["id"], "GIARDIA", nome_vacina="Giárdia", situacao="AGENDADA",
                                            data_aplicacao=amanha, fabricante=None, numero_lote=None,
                                            validade_lote=None, data_proxima_dose=None))
    hist = _corpo(api.get(f"/api/animais/{a['id']}/vacinas"))
    assert {h["nome_vacina"] for h in hist} == {"V10", "Giárdia"}

    prox = _corpo(api.get(f"/api/animais/{a['id']}/vacinas/proximas-doses"))
    assert [p["nome_vacina"] for p in prox] == ["Giárdia", "V10"]
    assert prox[0]["origem"] == "AGENDADA" and prox[1]["origem"] == "REFORCO_PREVISTO"
    assert prox[1]["situacao_prazo"] == "NO_PRAZO" and prox[1]["dias_para_a_data"] == 30

    # nova aplicação da mesma vacina substitui o reforço previsto anterior
    api.post("/api/vacinas", vacina_payload(a["id"], nome_vacina="V10", dose="2ª dose", data_aplicacao=date.today().isoformat(),
                                            data_proxima_dose=(date.today() + timedelta(days=365)).isoformat()))
    prox = _corpo(api.get(f"/api/animais/{a['id']}/vacinas/proximas-doses"))
    assert [p["dias_para_a_data"] for p in prox if p["nome_vacina"] == "V10"] == [365]


def test_T10_validacoes_da_vacina(api):
    a = criar_animal(api)
    hoje = date.today()
    r = api.post("/api/vacinas", vacina_payload(a["id"], validade_lote=(hoje - timedelta(days=5)).isoformat()))
    assert r.status_code == 422 and _erro(r)["codigo"] == "LOTE_VENCIDO"
    r = api.post("/api/vacinas", vacina_payload(a["id"], fabricante=None, numero_lote=None))
    assert r.status_code == 422 and {"fabricante", "numero_lote"} <= set(_erro(r)["detalhes"])
    r = api.post("/api/vacinas", vacina_payload(a["id"], data_aplicacao=(hoje + timedelta(days=2)).isoformat()))
    assert r.status_code == 422                                       # aplicada no futuro
    r = api.post("/api/vacinas", vacina_payload(a["id"], data_proxima_dose=(hoje - timedelta(days=40)).isoformat()))
    assert r.status_code == 422                                       # próxima dose antes da aplicação
    r = api.post("/api/vacinas", vacina_payload(a["id"], tipo_vacina="INVENTADA"))
    assert r.status_code == 422


# ====================================================================== GOVERNO (cadastro/atualização)
def test_T11_cadastro_e_atualizacao_de_animal_na_api_governamental(api, governo):
    h, url = governo.headers, governo.url
    micro = "985000000000001"
    payload = {"microchip": micro, "nome": "Luna", "especie": "Gato", "raca": "Siamês", "sexo": "FEMEA",
               "data_nascimento": "2021-03-04", "tutor": {"nome_completo": "Tutora Teste", "cpf": novo_cpf()}}
    r = requests.post(url + "/api/governo/animais", json=payload, headers={**h, "Idempotency-Key": "k1"}, timeout=3)
    assert r.status_code == 201 and r.json()["protocolo"].startswith("GOV-") and r.json()["status"] == "PROCESSADA"
    proto = r.json()["protocolo"]
    assert requests.get(f"{url}/api/governo/animais/{micro}", headers=h, timeout=3).json()["nome"] == "Luna"

    dup = requests.post(url + "/api/governo/animais", json=payload, headers={**h, "Idempotency-Key": "k2"}, timeout=3)
    assert dup.status_code == 409 and dup.json()["erro"]["codigo"] == "ANIMAL_JA_CADASTRADO"
    assert dup.json()["protocolo"] != proto                                   # a tentativa rejeitada também gera protocolo

    payload["nome"] = "Luna Maria"
    r = requests.put(f"{url}/api/governo/animais/{micro}", json=payload, headers=h, timeout=3)
    assert r.status_code == 200 and r.json()["status"] == "PROCESSADA"
    assert requests.get(f"{url}/api/governo/animais/{micro}", headers=h, timeout=3).json()["nome"] == "Luna Maria"
    op = requests.get(f"{url}/api/governo/operacoes/{proto}", headers=h, timeout=3).json()
    assert op["tipo"] == "CADASTRO_ANIMAL" and op["status"] == "PROCESSADA"
    assert requests.get(f"{url}/api/governo/operacoes/GOV-INEXISTENTE", headers=h, timeout=3).status_code == 404


def test_T11_atualizar_animal_na_clinica_comunica_a_atualizacao_ao_governo(api, governo):
    a, codigo, _ = animal_com_chip(api)
    r = api.put(f"/api/animais/{a['id']}", {**{k: a[k] for k in ("data_nascimento", "sexo", "cor", "peso_atual",
                                                                  "tutor_id", "especie_id", "raca_id")},
                                            "nome": "Rex Atualizado"})
    assert r.status_code == 200
    up = _corpo(r)["atualizacao_governo"]
    assert up["tipo_operacao"] == "ATUALIZACAO_ANIMAL" and up["situacao"] == "CONFIRMADA" and up["protocolo_externo"]
    assert governo.animal(codigo).json()["nome"] == "Rex Atualizado"
    # mudar só o peso não é dado do governo: nenhuma atualização é enviada
    r = api.put(f"/api/animais/{a['id']}", {**{k: a[k] for k in ("data_nascimento", "sexo", "cor", "tutor_id",
                                                                  "especie_id", "raca_id")},
                                            "nome": "Rex Atualizado", "peso_atual": 13.0})
    assert "atualizacao_governo" not in _corpo(r)


def test_T11_governo_valida_dados_e_exige_chave_de_api(governo):
    url = governo.url
    r = requests.post(url + "/api/governo/animais", json={"microchip": "123", "nome": ""}, headers=governo.headers, timeout=3)
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "VALIDACAO" and r.json()["protocolo"]
    assert {"microchip", "nome", "tutor.cpf"} <= set(r.json()["erro"]["detalhes"])
    assert requests.get(url + "/api/governo/animais/985000000000001", timeout=3).status_code == 401
    assert requests.get(url + "/api/governo/animais/985000000000001", headers={"X-API-Key": "errada"}, timeout=3).status_code == 401
    assert requests.get(url + "/api/governo/health", timeout=3).status_code == 200


# ====================================================================== ANTIRRÁBICA: comunicação obrigatória
def test_T12_envio_obrigatorio_de_vacina_antirrabica(api, governo):
    a, codigo, _ = animal_com_chip(api)
    r = antirrabica(api, a["id"])
    assert r.status_code == 201
    corpo = _corpo(r)
    assert corpo["vacina"]["antirrabica"] is True and corpo["vacina"]["situacao"] == "APLICADA"
    com = corpo["comunicacao_governo"]
    assert com["tipo_operacao"] == "VACINACAO_ANTIRRABICA" and com["situacao"] == "CONFIRMADA"
    assert com["protocolo_externo"].startswith("GOV-") and com["tentativas"] == 1 and com["respondida_em"]
    assert com["chave_idempotencia"] == f"vacina-{corpo['vacina']['id']}-antirrabica"

    enviados = governo.vacinacoes(codigo)                     # o governo realmente recebeu e registrou
    assert len(enviados) == 1
    e = enviados[0]
    assert (e["fabricante"], e["numero_lote"], e["veterinario_crmv"], e["animal_nome"]) == (
        "Lab Exemplo", "L-2026-01", "12345/SP", "Rex")
    assert e["protocolo"] == com["protocolo_externo"] and e["animal_origem_id"] == a["id"]

    detalhe = _corpo(api.get(f"/api/integracoes/{com['id']}"))["payload_enviado"]   # conteúdo mínimo exigido (seção 4)
    assert detalhe["microchip"] == codigo and detalhe["animal"]["id"] == a["id"]
    assert detalhe["data_aplicacao"] and detalhe["vacina"]["nome"] and detalhe["vacina"]["fabricante"]
    assert detalhe["vacina"]["numero_lote"] and detalhe["veterinario"]["crmv"] == "12345/SP"

    est = _corpo(api.get(f"/api/vacinas/{corpo['vacina']['id']}/comunicacao-governo"))
    assert est["registro_local"] == "APLICADA" and est["confirmacao_governo"] == "CONFIRMADA"
    assert est["comunicacao_obrigatoria"] is True


def test_T12_comunicacao_independe_de_o_animal_estar_cadastrado_no_governo(api, governo):
    governo.simular(modo="INDISPONIVEL")                           # o cadastro do animal fica pendente
    a, codigo, vinc = animal_com_chip(api)
    assert vinc["integracao_governo"]["situacao"] == "PENDENTE"
    governo.simular(modo="NORMAL")
    assert governo.animal(codigo).status_code == 404               # animal ainda NÃO existe no governo

    corpo = _corpo(antirrabica(api, a["id"]))
    assert corpo["comunicacao_governo"]["situacao"] == "CONFIRMADA"        # mesmo assim a vacina foi aceita
    assert len(governo.vacinacoes(codigo)) == 1
    assert governo.animal(codigo).status_code == 404


def test_T12_antirrabica_e_identificada_pela_classificacao_e_nao_pelo_nome(api, governo):
    a, codigo, _ = animal_com_chip(api)
    # nome "diferente", mas tipo ANTIRRABICA -> comunica
    r = api.post("/api/vacinas", vacina_payload(a["id"], "ANTIRRABICA", nome_vacina="Imunizante XYZ"))
    assert _corpo(r)["comunicacao_governo"]["situacao"] == "CONFIRMADA"
    # nome "Antirrábica", mas tipo POLIVALENTE -> não comunica
    r = api.post("/api/vacinas", vacina_payload(a["id"], "POLIVALENTE", nome_vacina="Antirrábica (digitado)",
                                                numero_lote="L-OUTRO"))
    assert r.status_code == 201 and _corpo(r)["comunicacao_governo"] is None
    # flag contraditória é recusada
    r = api.post("/api/vacinas", vacina_payload(a["id"], "POLIVALENTE", antirrabica=True))
    assert r.status_code == 422
    assert len(governo.vacinacoes(codigo)) == 1


def test_T12_antirrabica_exige_microchip_vinculado(api, governo):
    a = criar_animal(api)
    r = antirrabica(api, a["id"])
    assert r.status_code == 422 and _erro(r)["codigo"] == "ANIMAL_SEM_MICROCHIP"
    assert api.get(f"/api/animais/{a['id']}/vacinas").get_json() == []          # nada foi gravado pela metade


def test_T13_nao_ha_comunicacao_obrigatoria_para_vacina_nao_antirrabica(api, governo):
    a, codigo, _ = animal_com_chip(api)
    r = api.post("/api/vacinas", vacina_payload(a["id"], "POLIVALENTE", nome_vacina="V10"))
    assert r.status_code == 201
    corpo = _corpo(r)
    assert corpo["comunicacao_governo"] is None and corpo["vacina"]["comunicacao_governo"]["obrigatoria"] is False
    est = _corpo(api.get(f"/api/vacinas/{corpo['vacina']['id']}/comunicacao-governo"))
    assert est["comunicacao_obrigatoria"] is False and est["confirmacao_governo"] == "NAO_APLICAVEL"
    tipos = [i["tipo_operacao"] for i in _corpo(api.get("/api/integracoes"))]
    assert "VACINACAO_ANTIRRABICA" not in tipos
    assert governo.vacinacoes(codigo) == []


def test_T13_antirrabica_agendada_so_comunica_quando_aplicada(api, governo):
    a, codigo, _ = animal_com_chip(api)
    amanha = (date.today() + timedelta(days=1)).isoformat()
    r = api.post("/api/vacinas", vacina_payload(a["id"], "ANTIRRABICA", situacao="AGENDADA", data_aplicacao=amanha,
                                                fabricante=None, numero_lote=None, validade_lote=None,
                                                data_proxima_dose=None))
    assert r.status_code == 201 and _corpo(r)["comunicacao_governo"] is None
    vid = _corpo(r)["vacina"]["id"]
    assert governo.vacinacoes(codigo) == []                                       # agendada não é aplicada: nada enviado
    r = api.post(f"/api/vacinas/{vid}/aplicar", {})                                # falta lote/fabricante/validade
    assert r.status_code == 422
    r = api.post(f"/api/vacinas/{vid}/aplicar", {"data_aplicacao": date.today().isoformat(), "fabricante": "Lab X",
                                                 "numero_lote": "L-77", "validade_lote": (date.today() + timedelta(days=90)).isoformat()})
    assert r.status_code == 200
    assert _corpo(r)["vacina"]["situacao"] == "APLICADA" and _corpo(r)["comunicacao_governo"]["situacao"] == "CONFIRMADA"
    assert len(governo.vacinacoes(codigo)) == 1
    assert api.delete(f"/api/vacinas/{vid}").status_code == 409                   # aplicada não se cancela


# ====================================================================== INDISPONIBILIDADE E REGULARIZAÇÃO
def test_T14_indisponibilidade_do_governo_registra_pendencia(api, governo):
    a, codigo, _ = animal_com_chip(api)
    governo.simular(modo="INDISPONIVEL")
    assert _corpo(api.get("/api/status"))["governo"] == "indisponivel"

    r = antirrabica(api, a["id"])
    assert r.status_code == 201                                       # a vacinação NÃO é perdida
    corpo = _corpo(r)
    assert corpo["vacina"]["situacao"] == "APLICADA"
    com = corpo["comunicacao_governo"]
    assert com["situacao"] == "PENDENTE" and com["tentativas"] == 1 and com["protocolo_externo"] is None
    assert "indispon" in com["mensagem_erro"].lower()

    vid = corpo["vacina"]["id"]
    assert [v["id"] for v in _corpo(api.get(f"/api/animais/{a['id']}/vacinas"))] == [vid]     # segue no histórico local
    est = _corpo(api.get(f"/api/vacinas/{vid}/comunicacao-governo"))
    assert est["registro_local"] == "APLICADA" and est["confirmacao_governo"] == "PENDENTE"   # local != confirmado
    assert _corpo(api.get(f"/api/animais/{a['id']}"))["integracao_governo"]["pendencias"] == 1
    assert _corpo(api.get("/api/resumo"))["integracoes"]["PENDENTE"] == 1
    governo.simular(modo="NORMAL")
    assert governo.vacinacoes(codigo) == []


def test_T14_governo_totalmente_fora_do_ar_conexao_recusada(api, governo):
    a, codigo, _ = animal_com_chip(api)
    governo.derrubar()
    corpo = _corpo(antirrabica(api, a["id"]))
    assert corpo["vacina"]["situacao"] == "APLICADA" and corpo["comunicacao_governo"]["situacao"] == "PENDENTE"
    assert "conectar" in corpo["comunicacao_governo"]["mensagem_erro"].lower()
    # cadastro de novo animal/chip também fica pendente, mas o vínculo local é gravado
    novo = criar_animal(api)
    r, c2 = vincular_chip(api, novo["id"])
    assert r.status_code == 201 and _corpo(r)["integracao_governo"]["situacao"] == "PENDENTE"
    assert _corpo(api.get(f"/api/animais/{novo['id']}"))["microchip_atual"]["codigo"] == c2


def test_T15_reenvio_manual_de_pendencia_e_confirmacao_posterior(api, governo):
    a, codigo, _ = animal_com_chip(api)
    governo.simular(modo="INDISPONIVEL")
    com = _corpo(antirrabica(api, a["id"]))["comunicacao_governo"]
    assert com["situacao"] == "PENDENTE"

    r = api.post(f"/api/integracoes/{com['id']}/reenviar")             # governo ainda fora: continua pendente
    assert _corpo(r)["situacao"] == "PENDENTE" and _corpo(r)["tentativas"] == 2

    governo.simular(modo="NORMAL")
    r = api.post(f"/api/integracoes/{com['id']}/reenviar")
    assert r.status_code == 200
    ok = _corpo(r)
    assert ok["situacao"] == "CONFIRMADA" and ok["protocolo_externo"].startswith("GOV-") and ok["tentativas"] == 3
    assert ok["mensagem_erro"] is None and ok["respondida_em"]
    assert len(governo.vacinacoes(codigo)) == 1
    assert _corpo(api.get(f"/api/animais/{a['id']}"))["integracao_governo"]["pendencias"] == 0


def test_T15_reprocessamento_em_lote_das_pendencias(api, governo):
    governo.simular(modo="INDISPONIVEL")
    ids = []
    for _ in range(2):
        a, codigo, _ = animal_com_chip(api)                           # 2 cadastros pendentes
        ids.append(codigo)
    a2, _c, _ = animal_com_chip(api)
    antirrabica(api, a2["id"])                                        # + 1 vacinação pendente
    pend = _corpo(api.get("/api/integracoes?situacao=PENDENTE"))
    assert len(pend) == 4
    governo.simular(modo="NORMAL")
    r = api.post("/api/integracoes/reprocessar-pendentes")
    assert r.status_code == 200 and _corpo(r) == {"analisadas": 4, "confirmadas": 4, "ainda_pendentes": 0, "falhas": 0}
    assert _corpo(api.get("/api/integracoes?situacao=PENDENTE")) == []
    assert all(governo.animal(c).status_code == 200 for c in ids)


def test_T15_reenvio_automatico_respeita_limite_e_depois_o_manual_regulariza(api, governo, app):
    a, codigo, _ = animal_com_chip(api)
    governo.simular(modo="INDISPONIVEL")
    com = _corpo(antirrabica(api, a["id"]))["comunicacao_governo"]               # tentativa 1 (síncrona)
    with app.app_context(), sessao(app) as conn:
        r1 = integracao.reprocessar(conn, automatico=True)                         # tentativa 2
        r2 = integracao.reprocessar(conn, automatico=True)                         # tentativa 3 = limite configurado
        r3 = integracao.reprocessar(conn, automatico=True)                         # não tenta mais
    assert r1["ainda_pendentes"] == 1 and r2["analisadas"] == 1 and r3["analisadas"] == 0
    final = _corpo(api.get(f"/api/integracoes/{com['id']}"))
    assert final["situacao"] == "FALHA" and final["tentativas"] == 3 and "Limite" in final["mensagem_erro"]

    governo.simular(modo="NORMAL")                                                  # operador intervém
    r = api.post(f"/api/integracoes/{com['id']}/reenviar")
    assert _corpo(r)["situacao"] == "CONFIRMADA" and len(governo.vacinacoes(codigo)) == 1


def test_T15_reenvio_automatico_confirma_quando_o_governo_volta(api, governo, app):
    a, codigo, _ = animal_com_chip(api)
    governo.simular(falhar_proximas=1)                                              # só a 1ª chamada falha
    com = _corpo(antirrabica(api, a["id"]))["comunicacao_governo"]
    assert com["situacao"] == "PENDENTE"
    with app.app_context(), sessao(app) as conn:
        resumo = integracao.reprocessar(conn, automatico=True)
    assert resumo == {"analisadas": 1, "confirmadas": 1, "ainda_pendentes": 0, "falhas": 0}
    assert _corpo(api.get(f"/api/integracoes/{com['id']}"))["situacao"] == "CONFIRMADA"


# ====================================================================== IDEMPOTÊNCIA
def test_T16_repeticao_de_solicitacao_nao_duplica_registro_no_governo(api, governo):
    a, codigo, _ = animal_com_chip(api)
    com = _corpo(antirrabica(api, a["id"]))["comunicacao_governo"]
    assert com["situacao"] == "CONFIRMADA" and com["tentativas"] == 1
    protocolo = com["protocolo_externo"]

    # sem forçar: nada é reenviado
    sem = _corpo(api.post(f"/api/integracoes/{com['id']}/reenviar"))
    assert sem["tentativas"] == 1 and sem["ultima_resposta"] is None
    # forçando: o reenvio chega ao governo, que reconhece a chave e devolve o MESMO protocolo
    r = api.post(f"/api/integracoes/{com['id']}/reenviar?forcar=true")
    assert r.status_code == 200
    forcado = _corpo(r)
    assert forcado["ultima_resposta"]["repeticao_idempotente"] is True
    assert forcado["ultima_resposta"]["corpo"]["protocolo"] == protocolo
    assert forcado["situacao"] == "CONFIRMADA" and forcado["protocolo_externo"] == protocolo and forcado["tentativas"] == 2
    for _ in range(3):
        api.post(f"/api/integracoes/{com['id']}/reenviar?forcar=true")
    assert len(governo.vacinacoes(codigo)) == 1                                     # continua UMA vacinação lá


def test_T16_timeout_com_operacao_ja_processada_nao_duplica_no_reenvio(api, governo):
    """O caso que justifica a idempotência: o governo gravou, mas a resposta não chegou a tempo."""
    a, codigo, _ = animal_com_chip(api)
    governo.simular(modo="RESPOSTA_LENTA", atraso_s=2.5)                           # cliente espera só 1,0 s
    com = _corpo(antirrabica(api, a["id"]))["comunicacao_governo"]
    assert com["situacao"] == "ENVIADA" and "reenvio é seguro" in com["mensagem_erro"].lower()
    assert com["protocolo_externo"] is None                                         # a clínica não sabe de nada...
    lado_governo = governo.vacinacoes(codigo)
    assert len(lado_governo) == 1                                                   # ...mas o governo JÁ gravou

    governo.simular(modo="NORMAL")
    r = api.post(f"/api/integracoes/{com['id']}/reenviar")
    ok = _corpo(r)
    assert ok["situacao"] == "CONFIRMADA" and ok["ultima_resposta"]["repeticao_idempotente"] is True
    assert ok["protocolo_externo"] == lado_governo[0]["protocolo"]                  # regularizou com o protocolo original
    assert len(governo.vacinacoes(codigo)) == 1


def test_T16_governo_aplica_idempotencia_por_chave_e_por_chave_natural(governo):
    h = {**governo.headers, "Idempotency-Key": "chave-A"}
    corpo = {"microchip": "985000000000009", "animal": {"id": 7, "nome": "Teste"}, "data_aplicacao": "2026-10-01",
             "vacina": {"id_aplicacao": 55, "nome": "Antirrábica", "fabricante": "Lab", "numero_lote": "L1"},
             "veterinario": {"nome_completo": "Dra. Teste", "crmv": "1/SP"}}
    url = governo.url + "/api/governo/vacinacoes-antirrabicas"
    r1 = requests.post(url, json=corpo, headers=h, timeout=3)
    r2 = requests.post(url, json=corpo, headers=h, timeout=3)
    assert r1.status_code == 201 and r2.status_code == 200
    assert r2.json()["protocolo"] == r1.json()["protocolo"] and r2.json()["repetida"] is True
    assert r2.headers["Idempotent-Replayed"] == "true"
    assert len(governo.vacinacoes("985000000000009")) == 1
    # outra chave, mesma vacinação: recusa como duplicada em vez de gravar de novo
    r3 = requests.post(url, json=corpo, headers={**governo.headers, "Idempotency-Key": "chave-B"}, timeout=3)
    assert r3.status_code == 409 and r3.json()["erro"]["codigo"] == "VACINACAO_DUPLICADA"
    assert r3.json()["protocolo_original"] == r1.json()["protocolo"]
    assert len(governo.vacinacoes("985000000000009")) == 1
    # sem chave: o governo exige
    r4 = requests.post(url, json=corpo, headers=governo.headers, timeout=3)
    assert r4.status_code == 400 and r4.json()["erro"]["codigo"] == "IDEMPOTENCY_KEY_OBRIGATORIA"
    # uma chave não pode ser reutilizada em outro tipo de operação
    r5 = requests.post(governo.url + "/api/governo/animais", json={}, headers={**governo.headers, "Idempotency-Key": "chave-A"}, timeout=3)
    assert r5.status_code == 422 and r5.json()["erro"]["codigo"] == "CHAVE_REUTILIZADA"
