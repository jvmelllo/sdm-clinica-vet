"""Gera a coleção Postman com os 16 cenários de teste obrigatórios (T01–T16) e o ambiente.

Saídas (importar no Postman: File > Import):
    docs/postman/SDM_Clinica_Vet.postman_collection.json
    docs/postman/SDM_Local.postman_environment.json

Uso:  python scripts/gerar_postman.py
Execução sem Postman (mini-runtime que roda os scripts da coleção contra a pilha no ar):
      node scripts/executar_colecao.js

Pré-requisito para executar: pilha no ar (python scripts/run_all.py --sqlite --reset --viacep-falso) ou MySQL + ViaCEP real.
Todos os dados usados (CPFs, microchips, lotes) são gerados a cada execução, então a coleção pode rodar várias vezes seguidas.
"""
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "docs", "postman")

ANA = "ana.souza@clinicavet.example"
SENHA = "Senha@123"

# ---------------------------------------------------------------------------- geração de JS a partir de checagens


def _js(v):
    return json.dumps(v, ensure_ascii=False)


def _acessor(caminho):
    out = "j"
    for p in [x for x in caminho.split(".") if x != ""]:
        if p.isdigit():
            out += f"[{p}]"
        elif re.match(r"^[A-Za-z_]\w*$", p):
            out += f".{p}"
        else:
            out += f"[{_js(p)}]"
    return out


def _linha_check(caminho, op, valor=None, texto=None):
    a = _acessor(caminho)
    desc = texto or f"{caminho or 'corpo'} {op} {'' if valor is None else _js(valor)}".strip()
    corpos = {
        "eq": f"pm.expect({a}).to.eql({_js(valor)});",
        "in": f"pm.expect({a}).to.be.oneOf({_js(valor)});",
        "inclui": f"pm.expect(String({a})).to.include({_js(valor)});",
        "str": f"pm.expect({a}).to.be.a(\"string\");",
        "maior": f"pm.expect({a}).to.be.above({_js(valor)});",
        "tam": f"pm.expect({a}).to.have.lengthOf({_js(valor)});",
        "nulo": f"pm.expect({a}).to.be.null;",
        "naonulo": f"pm.expect({a}).to.not.be.null;",
        "verdadeiro": f"pm.expect({a}).to.be.true;",
        "eqvar": f"pm.expect({a}).to.eql(pm.collectionVariables.get({_js(valor)}));",
    }
    return f"pm.test({_js(desc)}, function () {{ {corpos[op]} }});"


# ---------------------------------------------------------------------------- DSL das requisições
def R(nome, metodo, url, *, corpo=None, auth=True, chave_gov=False, headers=None, status=200, checks=(), salvar=None,
      descricao="", prereq=None):
    return dict(nome=nome, metodo=metodo, url=url, corpo=corpo, auth=auth, chave_gov=chave_gov, headers=headers or {},
                status=status, checks=list(checks), salvar=salvar or {}, descricao=descricao, prereq=prereq)


def montar_item(r):
    headers = [{"key": "Accept", "value": "application/json"}]
    if r["corpo"] is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})
    if r["auth"]:
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
    if r["chave_gov"]:
        headers.append({"key": "X-API-Key", "value": "{{govKey}}"})
    headers += [{"key": k, "value": v} for k, v in r["headers"].items()]

    bruto, _, consulta = r["url"].partition("?")
    host, _, caminho = bruto.partition("}}")
    url = {"raw": r["url"], "host": [host + "}}"], "path": [p for p in caminho.split("/") if p]}
    if consulta:
        url["query"] = [{"key": k, "value": v} for k, _, v in (par.partition("=") for par in consulta.split("&"))]

    req = {"method": r["metodo"], "header": headers, "url": url}
    if r["corpo"] is not None:
        bruto_json = json.dumps(r["corpo"], ensure_ascii=False, indent=2)
        # ids numéricos entram SEM aspas (padrão Postman): "{{tutorId}}" -> {{tutorId}}
        bruto_json = re.sub(r'"\{\{(tutorId|animalId|animalId2)\}\}"', r"{{\1}}", bruto_json)
        req["body"] = {"mode": "raw", "raw": bruto_json, "options": {"raw": {"language": "json"}}}
    if r["descricao"]:
        req["description"] = r["descricao"]

    js = [f"pm.test(\"Status {r['status']}\", function () {{ pm.response.to.have.status({r['status']}); }});",
          "var j = {}; try { j = pm.response.json(); } catch (e) { j = {}; }"]
    js += [_linha_check(*c) for c in r["checks"]]
    for var, caminho in r["salvar"].items():
        js.append(f"pm.collectionVariables.set({_js(var)}, {_acessor(caminho)});")
    eventos = [{"listen": "test", "script": {"type": "text/javascript", "exec": js}}]
    if r["prereq"]:
        eventos.insert(0, {"listen": "prerequest", "script": {"type": "text/javascript", "exec": r["prereq"].strip().split("\n")}})
    return {"name": r["nome"], "event": eventos, "request": req}


# ---------------------------------------------------------------------------- script de preparação (dados novos a cada execução)
PREPARAR = """
function dv(d){var s=0,i;for(i=0;i<d.length;i++){s+=d[i]*(d.length+1-i);}return ((s*10)%11)%10;}
function cpf(){var b=[],i;for(i=0;i<9;i++){b.push(Math.floor(Math.random()*10));}
  if(b.every(function(x){return x===b[0];})){b[0]=(b[0]+1)%10;} b.push(dv(b)); b.push(dv(b)); return b.join('');}
function chip(){var s='900',i;for(i=0;i<12;i++){s+=Math.floor(Math.random()*10);}return s;}
function iso(ms){return new Date(Date.now()+ms).toISOString().slice(0,10);}
var n=String(Date.now()).slice(-8);
var v=pm.collectionVariables;
v.set('suf',n); v.set('cpf1',cpf()); v.set('cpf2',cpf()); v.set('cpfGov',cpf());
v.set('chipA',chip()); v.set('chipB',chip()); v.set('chipGov',chip());
v.set('ontem',iso(-86400000)); v.set('proximaDose',iso(365*86400000)); v.set('validade',iso(400*86400000));
v.set('loteA','LA'+n); v.set('loteB','LB'+n); v.set('loteV','LV'+n);
v.set('token','');
"""


def tutor(cpf_var, nome):
    return {"nome_completo": nome, "cpf": "{{" + cpf_var + "}}", "data_nascimento": "1990-05-10",
            "email": nome.split()[0].lower() + "{{suf}}@example.com", "telefone": "11912345678",
            "endereco": {"cep": "01001000", "logradouro": "Praça da Sé", "numero": "100", "bairro": "Sé",
                         "cidade": "São Paulo", "uf": "SP"}}


def animal(nome, tutor_var="tutorId"):
    return {"nome": nome, "data_nascimento": "2022-03-01", "sexo": "MACHO", "cor": "Caramelo", "peso_atual": 12.5,
            "tutor_id": "{{" + tutor_var + "}}", "especie_id": 1, "raca_id": 1}


def vacina_antirrabica(lote_var):
    return {"animal_id": "{{animalId}}", "nome_vacina": "Antirrábica anual", "tipo_vacina": "ANTIRRABICA", "dose": "Dose única",
            "via_aplicacao": "SUBCUTANEA", "data_aplicacao": "{{ontem}}", "fabricante": "Zoetis", "numero_lote": "{{" + lote_var + "}}",
            "validade_lote": "{{validade}}", "data_proxima_dose": "{{proximaDose}}"}


def animal_gov(chip_var, nome, cpf_var, **mudar):
    d = {"microchip": "{{" + chip_var + "}}", "nome": nome, "especie": "Cão", "raca": "Labrador", "sexo": "MACHO",
         "data_nascimento": "2022-03-01", "situacao": "ATIVO", "tutor": {"nome_completo": "Maria Oliveira", "cpf": "{{" + cpf_var + "}}"}}
    d.update(mudar)
    return d


def login(email, senha, **kw):
    return R(kw.pop("nome"), "POST", "{{base}}/api/auth/login", corpo={"email": email, "senha": senha}, auth=False, **kw)


PASTAS = [
    ("00 – Preparação (dados novos a cada execução)",
     "Gera CPFs, microchips, lotes e datas novos e confirma que a API, o banco e o governo simulado estão no ar.", [
         R("Verificar saúde e gerar dados", "GET", "{{base}}/api/status", auth=False, prereq=PREPARAR,
           checks=[("api", "eq", "ok"), ("banco", "eq", "ok"), ("governo", "eq", "ok")]),
         R("Governo simulado em modo NORMAL", "PUT", "{{gov}}/api/governo/simulacao", corpo={"modo": "NORMAL", "falhar_proximas": 0},
           auth=False, chave_gov=True, checks=[("modo", "eq", "NORMAL")]),
     ]),
    ("T01 – Login de veterinário ativo e confirmado", "Autenticação com hash + JWT; rotas privadas exigem token.", [
        login(ANA, SENHA, nome="Login válido", checks=[("token", "str"), ("veterinario.situacao", "eq", "ATIVO"),
                                                         ("veterinario.senha_confirmada", "verdadeiro")], salvar={"token": "token"}),
        R("Dados do usuário autenticado", "GET", "{{base}}/api/auth/me", checks=[("email", "eq", ANA)]),
        R("Rota privada sem token é recusada", "GET", "{{base}}/api/tutores", auth=False, status=401, checks=[("erro.codigo", "naonulo")]),
    ]),
    ("T02 – Bloqueio de veterinário inativo", "Acesso negado a veterinário INATIVO, mesmo com a senha correta.", [
        login("bruno.lima@clinicavet.example", SENHA, nome="Login de veterinário inativo", status=403,
              checks=[("erro.codigo", "eq", "VETERINARIO_INATIVO")]),
    ]),
    ("T03 – Bloqueio de veterinário com senha não confirmada", "Acesso negado até confirmar a senha com o código.", [
        login("carla.mendes@clinicavet.example", SENHA, nome="Login sem senha confirmada", status=403,
              checks=[("erro.codigo", "eq", "SENHA_NAO_CONFIRMADA")]),
    ]),
    ("T04 – Rejeição de senha incorreta", "Mesma resposta para senha errada e e-mail inexistente (não revela cadastros).", [
        login(ANA, "senha-errada", nome="Senha incorreta", status=401, checks=[("erro.codigo", "eq", "CREDENCIAIS_INVALIDAS")]),
        login("ninguem@clinicavet.example", SENHA, nome="E-mail inexistente (mesma resposta)", status=401,
              checks=[("erro.codigo", "eq", "CREDENCIAIS_INVALIDAS")]),
    ]),
    ("T05 – Cadastro de tutor e CPF duplicado", "Valida CPF, grava endereço e impede CPF repetido.", [
        R("Cadastrar tutor", "POST", "{{base}}/api/tutores", corpo=tutor("cpf1", "Maria Oliveira"), status=201,
          checks=[("cpf", "eqvar", "cpf1"), ("endereco.cidade", "eq", "São Paulo"), ("situacao", "eq", "ATIVO")], salvar={"tutorId": "id"}),
        R("Cadastrar o MESMO CPF novamente (409)", "POST", "{{base}}/api/tutores", corpo=tutor("cpf1", "Outra Pessoa"), status=409,
          checks=[("erro.codigo", "eq", "CPF_DUPLICADO")]),
        R("CPF inválido (422)", "POST", "{{base}}/api/tutores", corpo={**tutor("cpf1", "Joao Teste"), "cpf": "11111111111"}, status=422,
          checks=[("erro.codigo", "eq", "VALIDACAO"), ("erro.detalhes.cpf", "naonulo")]),
    ]),
    ("T06 – Consulta de CEP (ViaCEP)", "Consome o ViaCEP e trata CEP inexistente.", [
        R("CEP válido", "GET", "{{base}}/api/cep/01001000", checks=[("logradouro", "eq", "Praça da Sé"), ("uf", "eq", "SP"), ("fonte", "eq", "ViaCEP")]),
        R("CEP inexistente (404)", "GET", "{{base}}/api/cep/99999999", status=404, checks=[("erro.codigo", "eq", "CEP_NAO_ENCONTRADO")]),
        R("CEP com formato inválido (422)", "GET", "{{base}}/api/cep/123", status=422, checks=[("erro.codigo", "eq", "VALIDACAO")]),
    ]),
    ("T06b – (opcional) CEP com timeout/erro — exige scripts/viacep_falso.py",
     "Só funciona com VIACEP_URL apontando para o ViaCEP falso (python scripts/run_all.py --viacep-falso). Com o ViaCEP real, ignore esta pasta.", [
         R("CEP que demora (timeout → 504)", "GET", "{{base}}/api/cep/11111111", status=504, checks=[("erro.codigo", "eq", "CEP_TIMEOUT")]),
         R("CEP com serviço em erro (503)", "GET", "{{base}}/api/cep/22222222", status=503, checks=[("erro.codigo", "eq", "CEP_INDISPONIVEL")]),
     ]),
    ("T07 – Cadastro de animal e vínculo de microchip", "O animal nasce sem microchip; o vínculo é comunicado ao governo.", [
        R("Cadastrar animal", "POST", "{{base}}/api/animais", corpo=animal("Thor"), status=201,
          checks=[("microchip_atual", "nulo"), ("integracao_governo.situacao_cadastro", "eq", "SEM_MICROCHIP")], salvar={"animalId": "id"}),
        R("Vincular microchip (15 dígitos)", "POST", "{{base}}/api/animais/{{animalId}}/microchip", corpo={"codigo": "{{chipA}}"}, status=201,
          checks=[("vinculo.codigo_microchip", "eqvar", "chipA"), ("vinculo.situacao", "eq", "ATIVO"),
                  ("integracao_governo.situacao", "eq", "CONFIRMADA")]),
    ]),
    ("T08 – Rejeição de microchip já utilizado", "O código é único e nunca reutilizável.", [
        R("Cadastrar segundo animal", "POST", "{{base}}/api/animais", corpo=animal("Mia"), status=201, salvar={"animalId2": "id"}),
        R("Vincular o MESMO microchip ao segundo animal (409)", "POST", "{{base}}/api/animais/{{animalId2}}/microchip",
          corpo={"codigo": "{{chipA}}"}, status=409, checks=[("erro.codigo", "eq", "MICROCHIP_JA_UTILIZADO")]),
        R("Microchip com formato inválido (422)", "POST", "{{base}}/api/animais/{{animalId2}}/microchip", corpo={"codigo": "123"}, status=422,
          checks=[("erro.codigo", "eq", "VALIDACAO")]),
    ]),
    ("T09 – Consulta e histórico clínico", "Registra consulta (atualiza o peso) e consulta o histórico do animal.", [
        R("Registrar consulta realizada", "POST", "{{base}}/api/consultas", status=201,
          corpo={"animal_id": "{{animalId}}", "data_hora": "{{ontem}} 10:00", "motivo": "Check-up de rotina", "diagnostico": "Saudável",
                 "peso_kg": 13.1, "situacao": "REALIZADA"}, checks=[("situacao", "eq", "REALIZADA")]),
        R("Histórico de consultas do animal", "GET", "{{base}}/api/animais/{{animalId}}/consultas",
          checks=[("", "tam", 1), ("0.motivo", "eq", "Check-up de rotina")]),
        R("Peso do animal foi atualizado pela consulta", "GET", "{{base}}/api/animais/{{animalId}}", checks=[("peso_atual", "eq", 13.1)]),
    ]),
    ("T10 – Registro de vacina e próximas doses", "Vacina com reforço aparece nas próximas doses.", [
        R("Registrar vacina polivalente (com reforço)", "POST", "{{base}}/api/vacinas", status=201,
          corpo={"animal_id": "{{animalId}}", "nome_vacina": "V10", "tipo_vacina": "POLIVALENTE", "dose": "Reforço anual",
                 "via_aplicacao": "SUBCUTANEA", "data_aplicacao": "{{ontem}}", "fabricante": "MSD", "numero_lote": "{{loteV}}",
                 "validade_lote": "{{validade}}", "data_proxima_dose": "{{proximaDose}}"},
          checks=[("vacina.situacao", "eq", "APLICADA"), ("vacina.antirrabica", "eq", False)], salvar={"vacinaPoliId": "vacina.id"}),
        R("Histórico de vacinação", "GET", "{{base}}/api/animais/{{animalId}}/vacinas", checks=[("0.nome_vacina", "eq", "V10")]),
        R("Próximas doses", "GET", "{{base}}/api/animais/{{animalId}}/vacinas/proximas-doses",
          checks=[("0.nome_vacina", "eq", "V10"), ("0.situacao_prazo", "eq", "NO_PRAZO")]),
    ]),
    ("T11 – API governamental: cadastro e atualização de animal", "Chamadas diretas ao serviço governamental simulado (chave X-API-Key).", [
        R("Cadastrar animal no governo", "POST", "{{gov}}/api/governo/animais", auth=False, chave_gov=True, status=201,
          headers={"Idempotency-Key": "{{chipGov}}-cad"}, corpo=animal_gov("chipGov", "Bolt", "cpfGov"),
          checks=[("status", "eq", "PROCESSADA"), ("protocolo", "inclui", "GOV-")]),
        R("Consultar animal por microchip", "GET", "{{gov}}/api/governo/animais/{{chipGov}}", auth=False, chave_gov=True,
          checks=[("nome", "eq", "Bolt"), ("especie", "eq", "Cão")]),
        R("Atualizar o cadastro", "PUT", "{{gov}}/api/governo/animais/{{chipGov}}", auth=False, chave_gov=True,
          headers={"Idempotency-Key": "{{chipGov}}-upd"}, corpo=animal_gov("chipGov", "Bolt Atualizado", "cpfGov"),
          checks=[("status", "eq", "PROCESSADA")]),
        R("Conferir a atualização", "GET", "{{gov}}/api/governo/animais/{{chipGov}}", auth=False, chave_gov=True, checks=[("nome", "eq", "Bolt Atualizado")]),
        R("Erro de validação simulado (CPF inválido → 422)", "POST", "{{gov}}/api/governo/animais", auth=False, chave_gov=True, status=422,
          corpo=animal_gov("chipB", "Invalido", "cpfGov", tutor={"nome_completo": "X Y", "cpf": "11111111111"}),
          checks=[("status", "eq", "REJEITADA"), ("erro.codigo", "eq", "VALIDACAO"), ("protocolo", "naonulo")]),
        R("Sem chave de API (401)", "GET", "{{gov}}/api/governo/animais/{{chipGov}}", auth=False, status=401, checks=[("erro.codigo", "eq", "NAO_AUTORIZADO")]),
    ]),
    ("T12 – Envio obrigatório da vacina antirrábica", "Aplicar a antirrábica comunica o governo e guarda o protocolo.", [
        R("Registrar vacina antirrábica", "POST", "{{base}}/api/vacinas", corpo=vacina_antirrabica("loteA"), status=201,
          checks=[("vacina.antirrabica", "verdadeiro"), ("comunicacao_governo.situacao", "eq", "CONFIRMADA"),
                  ("comunicacao_governo.protocolo_externo", "inclui", "GOV-")],
          salvar={"vacinaA": "vacina.id", "protocoloA": "comunicacao_governo.protocolo_externo"}),
        R("Governo recebeu a vacinação", "GET", "{{gov}}/api/governo/vacinacoes-antirrabicas?microchip={{chipA}}", auth=False, chave_gov=True,
          checks=[("", "tam", 1), ("0.numero_lote", "eqvar", "loteA"), ("0.protocolo", "eqvar", "protocoloA")]),
        R("Estado da comunicação (local x governo)", "GET", "{{base}}/api/vacinas/{{vacinaA}}/comunicacao-governo",
          checks=[("registro_local", "eq", "APLICADA"), ("confirmacao_governo", "eq", "CONFIRMADA")]),
    ]),
    ("T13 – Sem envio para vacina não antirrábica", "Outros tipos de vacina não geram comunicação ao governo.", [
        R("Comunicação da vacina polivalente", "GET", "{{base}}/api/vacinas/{{vacinaPoliId}}/comunicacao-governo",
          checks=[("comunicacao_obrigatoria", "eq", False), ("confirmacao_governo", "eq", "NAO_APLICAVEL")]),
        R("Governo continua com apenas 1 vacinação do animal", "GET", "{{gov}}/api/governo/vacinacoes-antirrabicas?microchip={{chipA}}",
          auth=False, chave_gov=True, checks=[("", "tam", 1)]),
    ]),
    ("T14 – Governo indisponível: vacina registrada e comunicação PENDENTE", "A indisponibilidade não impede o registro local.", [
        R("Derrubar o governo simulado (503)", "PUT", "{{gov}}/api/governo/simulacao", corpo={"modo": "INDISPONIVEL"}, auth=False, chave_gov=True,
          checks=[("modo", "eq", "INDISPONIVEL")]),
        R("Registrar antirrábica com o governo fora do ar", "POST", "{{base}}/api/vacinas", corpo=vacina_antirrabica("loteB"), status=201,
          checks=[("vacina.situacao", "eq", "APLICADA"), ("comunicacao_governo.situacao", "eq", "PENDENTE"),
                  ("comunicacao_governo.protocolo_externo", "nulo")],
          salvar={"vacinaB": "vacina.id", "integracaoB": "comunicacao_governo.id"}),
        R("A vacina continua registrada na clínica", "GET", "{{base}}/api/vacinas/{{vacinaB}}", checks=[("situacao", "eq", "APLICADA"),
                                                                                                     ("comunicacao_governo.situacao", "eq", "PENDENTE")]),
        R("Governo realmente está fora do ar (503)", "GET", "{{gov}}/api/governo/vacinacoes-antirrabicas", auth=False, chave_gov=True, status=503,
          checks=[("erro.codigo", "eq", "SERVICO_INDISPONIVEL")]),
    ]),
    ("T15 – Reenvio de pendência e confirmação posterior", "Com o governo de volta, o reenvio confirma a pendência.", [
        R("Governo volta ao normal", "PUT", "{{gov}}/api/governo/simulacao", corpo={"modo": "NORMAL", "falhar_proximas": 0}, auth=False, chave_gov=True,
          checks=[("modo", "eq", "NORMAL")]),
        R("Reenviar a pendência", "POST", "{{base}}/api/integracoes/{{integracaoB}}/reenviar", corpo={},
          checks=[("situacao", "eq", "CONFIRMADA"), ("protocolo_externo", "inclui", "GOV-")], salvar={"protocoloB": "protocolo_externo"}),
        R("Comunicação agora CONFIRMADA", "GET", "{{base}}/api/vacinas/{{vacinaB}}/comunicacao-governo", checks=[("confirmacao_governo", "eq", "CONFIRMADA")]),
    ]),
    ("T16 – Repetição de solicitação sem duplicar registro", "Idempotency-Key: o governo reconhece a repetição e devolve o mesmo protocolo.", [
        R("Reenvio forçado de operação já confirmada", "POST", "{{base}}/api/integracoes/{{integracaoB}}/reenviar?forcar=true", corpo={},
          checks=[("situacao", "eq", "CONFIRMADA"), ("protocolo_externo", "eqvar", "protocoloB"),
                  ("ultima_resposta.repeticao_idempotente", "verdadeiro")]),
        R("Governo tem apenas 2 vacinações (A e B), sem duplicata", "GET", "{{gov}}/api/governo/vacinacoes-antirrabicas?microchip={{chipA}}",
          auth=False, chave_gov=True, checks=[("", "tam", 2)]),
        R("Mesma Idempotency-Key direto no governo devolve a mesma resposta", "POST", "{{gov}}/api/governo/animais", auth=False, chave_gov=True,
          headers={"Idempotency-Key": "{{chipGov}}-cad"}, corpo=animal_gov("chipGov", "Bolt", "cpfGov"), status=200,
          checks=[("repetida", "verdadeiro")]),
    ]),
]


def montar_colecao():
    itens = [{"name": nome, "description": desc, "item": [montar_item(r) for r in reqs]} for nome, desc, reqs in PASTAS]
    return {
        "info": {"name": "SDM – Clínica Veterinária (A3) – Testes T01 a T16",
                 "description": ("Coleção dos 16 cenários de teste obrigatórios do projeto A3.\n\n"
                                 "1. Suba a pilha (`python scripts/run_all.py --sqlite --reset --viacep-falso`) e importe também o ambiente `SDM_Local`.\n"
                                 "2. Execute com **Collection Runner**, na ordem. Os cenários dependem uns dos outros (ids e tokens ficam em variáveis).\n"
                                 "3. A pasta 00 gera dados novos a cada execução; a pasta T06b só funciona com o ViaCEP falso."),
                 "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "variable": [{"key": "base", "value": "http://localhost:5000"}, {"key": "gov", "value": "http://localhost:5001"},
                     {"key": "govKey", "value": "chave-demo-governo"}, {"key": "token", "value": ""}],
        "item": itens,
    }


def montar_ambiente():
    return {"id": "sdm-local", "name": "SDM Local", "_postman_variable_scope": "environment",
            "values": [{"key": "base", "value": "http://localhost:5000", "enabled": True},
                       {"key": "gov", "value": "http://localhost:5001", "enabled": True},
                       {"key": "govKey", "value": "chave-demo-governo", "enabled": True}]}


def contar(colecao):
    reqs = sum(len(p["item"]) for p in colecao["item"])
    testes = sum(sum(1 for e in r["event"] if e["listen"] == "test" for linha in e["script"]["exec"] if linha.startswith("pm.test("))
                 for p in colecao["item"] for r in p["item"])
    return reqs, testes


if __name__ == "__main__":
    os.makedirs(SAIDA, exist_ok=True)
    col = montar_colecao()
    with open(os.path.join(SAIDA, "SDM_Clinica_Vet.postman_collection.json"), "w", encoding="utf-8") as f:
        json.dump(col, f, ensure_ascii=False, indent=2)
    with open(os.path.join(SAIDA, "SDM_Local.postman_environment.json"), "w", encoding="utf-8") as f:
        json.dump(montar_ambiente(), f, ensure_ascii=False, indent=2)
    reqs, testes = contar(col)
    print(f"coleção gerada: {len(col['item'])} pastas, {reqs} requisições, {testes} asserções -> {SAIDA}")
