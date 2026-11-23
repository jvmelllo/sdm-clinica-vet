"""API GOVERNAMENTAL SIMULADA — registro de animais por microchip e de vacinações antirrábicas.

AVISO: serviço fictício, criado só para fins acadêmicos. NÃO é integração oficial com nenhum
sistema governamental real.

Recursos para a demonstração de falhas (todos controlados por /api/governo/simulacao):
  modo=INDISPONIVEL     responde 503 a tudo, sem processar nada
  modo=RESPOSTA_LENTA   PROCESSA e grava, mas demora `atraso_s` para responder (o cliente pode
                        dar timeout mesmo com a operação já gravada: caso clássico de idempotência)
  falhar_proximas=N     as próximas N requisições recebem 503 e depois volta ao normal
"""
import json
import logging
import threading
import time
import uuid
from datetime import date, datetime

from flask import Flask, Response, g, jsonify, request
from werkzeug.exceptions import HTTPException

from . import db
from .config import config_do_ambiente

log = logging.getLogger("governo")

CADASTRO, ATUALIZACAO, VACINACAO = "CADASTRO_ANIMAL", "ATUALIZACAO_ANIMAL", "VACINACAO_ANTIRRABICA"
ABERTAS = ("/api/governo/health", "/docs", "/openapi.yaml", "/")


class ApiError(Exception):
    def __init__(self, status, codigo, mensagem, detalhes=None, extra=None):
        self.status, self.codigo, self.mensagem, self.detalhes, self.extra = status, codigo, mensagem, detalhes, extra


def cpf_valido(cpf):
    n = "".join(c for c in str(cpf or "") if c.isdigit())
    if len(n) != 11 or n == n[0] * 11:
        return False
    for tam in (9, 10):
        soma = sum(int(d) * p for d, p in zip(n[:tam], range(tam + 1, 1, -1)))
        if (soma * 10) % 11 % 10 != int(n[tam]):
            return False
    return True


def _data(valor, nome, erros, obrigatoria=True):
    if valor in (None, ""):
        if obrigatoria:
            erros[nome] = "Campo obrigatório."
        return None
    try:
        d = datetime.strptime(str(valor), "%Y-%m-%d").date()
    except ValueError:
        erros[nome] = "Use o formato AAAA-MM-DD."
        return None
    if d > date.today():
        erros[nome] = "A data não pode estar no futuro."
    return d.strftime("%Y-%m-%d")


def _texto(valor, nome, erros, obrigatorio=True, max_len=150):
    if valor is None or str(valor).strip() == "":
        if obrigatorio:
            erros[nome] = "Campo obrigatório."
        return None
    s = str(valor).strip()
    if len(s) > max_len:
        erros[nome] = f"Máximo de {max_len} caracteres."
    return s


def _microchip(valor, erros):
    s = str(valor or "").strip()
    if not (len(s) == 15 and s.isdigit()):
        erros["microchip"] = "O microchip deve ter 15 dígitos numéricos."
    return s


def validar_animal(d):
    erros = {}
    if not isinstance(d, dict):
        raise ApiError(400, "JSON_INVALIDO", "O corpo deve ser um objeto JSON.")
    tutor = d.get("tutor") if isinstance(d.get("tutor"), dict) else {}
    v = {
        "nome": _texto(d.get("nome"), "nome", erros, max_len=80),
        "especie": _texto(d.get("especie"), "especie", erros, max_len=60),
        "raca": _texto(d.get("raca"), "raca", erros, obrigatorio=False, max_len=80),
        "data_nascimento": _data(d.get("data_nascimento"), "data_nascimento", erros, obrigatoria=False),
        "tutor_nome": _texto(tutor.get("nome_completo"), "tutor.nome_completo", erros),
    }
    sexo = str(d.get("sexo") or "").upper()
    if sexo not in ("MACHO", "FEMEA"):
        erros["sexo"] = "Use MACHO ou FEMEA."
    v["sexo"] = sexo
    situacao = str(d.get("situacao") or "ATIVO").upper()
    if situacao not in ("ATIVO", "INATIVO", "OBITO"):
        erros["situacao"] = "Use ATIVO, INATIVO ou OBITO."
    v["situacao"] = situacao
    if not cpf_valido(tutor.get("cpf")):
        erros["tutor.cpf"] = "CPF do tutor inválido."
    v["tutor_cpf"] = "".join(c for c in str(tutor.get("cpf") or "") if c.isdigit())
    return v, erros


def validar_vacinacao(d):
    erros = {}
    if not isinstance(d, dict):
        raise ApiError(400, "JSON_INVALIDO", "O corpo deve ser um objeto JSON.")
    animal = d.get("animal") if isinstance(d.get("animal"), dict) else {}
    vacina = d.get("vacina") if isinstance(d.get("vacina"), dict) else {}
    vet = d.get("veterinario") if isinstance(d.get("veterinario"), dict) else {}
    v = {"microchip": _microchip(d.get("microchip"), erros)}
    try:
        v["animal_origem_id"] = int(animal.get("id"))
    except (TypeError, ValueError):
        erros["animal.id"] = "Identificação do animal obrigatória (inteiro)."
    v["animal_nome"] = _texto(animal.get("nome"), "animal.nome", erros, max_len=80)
    v["data_aplicacao"] = _data(d.get("data_aplicacao"), "data_aplicacao", erros)
    try:
        v["id_aplicacao_origem"] = int(vacina.get("id_aplicacao"))
    except (TypeError, ValueError):
        erros["vacina.id_aplicacao"] = "Identificação da aplicação obrigatória (inteiro)."
    v["vacina"] = _texto(vacina.get("nome"), "vacina.nome", erros, max_len=100)
    v["fabricante"] = _texto(vacina.get("fabricante"), "vacina.fabricante", erros, max_len=100)
    v["numero_lote"] = _texto(vacina.get("numero_lote"), "vacina.numero_lote", erros, max_len=50)
    v["veterinario_nome"] = _texto(vet.get("nome_completo"), "veterinario.nome_completo", erros)
    v["veterinario_crmv"] = _texto(vet.get("crmv"), "veterinario.crmv", erros, max_len=20)
    return v, erros


# --------------------------------------------------------------------------- operações
def _protocolo():
    return f"GOV-{date.today():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _registrar_operacao(conn, tipo, chave, microchip, status, http, corpo):
    protocolo = _protocolo()
    corpo = {"protocolo": protocolo, "status": status, "tipo": tipo, **corpo}
    conn.inserir("gov_operacao", protocolo=protocolo, tipo=tipo, chave_idempotencia=chave,
                 microchip=microchip, status=status, codigo_http=http,
                 resposta=json.dumps(corpo, ensure_ascii=False), criada_em=db.agora())
    return protocolo, corpo


def _rejeitar(conn, tipo, microchip, http, codigo, mensagem, detalhes=None, extra=None):
    """Registra a operação REJEITADA (também recebe protocolo) e devolve o erro ao cliente."""
    erro = {"codigo": codigo, "mensagem": mensagem}
    if detalhes:
        erro["detalhes"] = detalhes
    protocolo, corpo = _registrar_operacao(conn, tipo, None, microchip, "REJEITADA", http, {"erro": erro, **(extra or {})})
    conn.commit()
    return jsonify(corpo), http


def _repeticao(conn, tipo):
    """Se a Idempotency-Key já gerou uma operação PROCESSADA, devolve a mesma resposta (sem reprocessar)."""
    chave = request.headers.get("Idempotency-Key")
    if not chave:
        return None
    op = conn.um("SELECT * FROM gov_operacao WHERE chave_idempotencia = %s", (chave,))
    if not op:
        return None
    if op["tipo"] != tipo:
        raise ApiError(422, "CHAVE_REUTILIZADA", "Esta Idempotency-Key já foi usada em outro tipo de operação.")
    corpo = json.loads(op["resposta"])
    corpo["repetida"] = True
    resp = jsonify(corpo)
    resp.status_code = 200
    resp.headers["Idempotent-Replayed"] = "true"
    g.processou = True
    return resp


def _executar_idempotente(conn, tipo, trabalho):
    """Roda `trabalho()`; se outra requisição com a mesma chave vencer a corrida (UNIQUE), repete a resposta dela."""
    try:
        return trabalho()
    except db.erros_de_integridade():
        conn.rollback()
        repetida = _repeticao(conn, tipo)
        if repetida is not None:
            return repetida
        raise


def criar_app(overrides=None):
    app = Flask(__name__)
    cfg = config_do_ambiente()
    cfg.update(overrides or {})
    app.config["SDM"] = cfg
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    app.teardown_appcontext(db.fechar_db)

    sim = {"modo": "NORMAL", "atraso_s": 0.0, "falhar_proximas": 0}
    trava = threading.Lock()
    app.extensions["simulacao"] = sim

    # ------------------------------------------------------------- middlewares
    @app.before_request
    def _autenticacao_e_falhas():
        g.processou = False
        caminho = request.path
        if caminho in ABERTAS or not caminho.startswith("/api/governo/"):
            return None
        if request.headers.get("X-API-Key") != app.config["SDM"]["API_KEY"]:
            raise ApiError(401, "NAO_AUTORIZADO", "X-API-Key ausente ou inválida.")
        if caminho == "/api/governo/simulacao":
            return None
        with trava:
            if sim["modo"] == "INDISPONIVEL" or sim["falhar_proximas"] > 0:
                if sim["falhar_proximas"] > 0:
                    sim["falhar_proximas"] -= 1
                log.warning("Simulando indisponibilidade em %s %s", request.method, caminho)
                raise ApiError(503, "SERVICO_INDISPONIVEL", "Serviço temporariamente indisponível (simulado).")
        return None

    @app.after_request
    def _resposta_lenta(resp):
        if g.get("processou") and sim["modo"] == "RESPOSTA_LENTA" and sim["atraso_s"] > 0:
            time.sleep(sim["atraso_s"])  # a operação JÁ foi gravada; só a resposta atrasa
        return resp

    @app.errorhandler(ApiError)
    def _erro(e):
        corpo = {"erro": {"codigo": e.codigo, "mensagem": e.mensagem}}
        if e.detalhes:
            corpo["erro"]["detalhes"] = e.detalhes
        corpo.update(e.extra or {})
        return jsonify(corpo), e.status

    @app.errorhandler(HTTPException)
    def _http(e):
        return jsonify({"erro": {"codigo": f"HTTP_{e.code}", "mensagem": e.description}}), e.code

    @app.errorhandler(Exception)
    def _inesperado(e):
        log.exception("Erro não tratado")
        return jsonify({"erro": {"codigo": "ERRO_INTERNO", "mensagem": "Erro interno do servidor."}}), 500

    # ------------------------------------------------------------------ rotas
    @app.get("/api/governo/health")
    def health():
        # Serviço "fora do ar" não responde ok nem no health (o painel da clínica usa isto).
        if sim["modo"] == "INDISPONIVEL":
            return jsonify({"servico": "governo-simulado", "status": "indisponivel", "modo": sim["modo"]}), 503
        return jsonify({"servico": "governo-simulado", "status": "ok", "modo": sim["modo"]})

    @app.get("/api/governo/simulacao")
    def ver_simulacao():
        return jsonify(sim)

    @app.put("/api/governo/simulacao")
    def definir_simulacao():
        d = request.get_json(silent=True) or {}
        modo = str(d.get("modo", sim["modo"])).upper()
        if modo not in ("NORMAL", "INDISPONIVEL", "RESPOSTA_LENTA"):
            raise ApiError(422, "VALIDACAO", "modo deve ser NORMAL, INDISPONIVEL ou RESPOSTA_LENTA.")
        try:
            atraso = float(d.get("atraso_s", sim["atraso_s"]))
            falhas = int(d.get("falhar_proximas", 0))
        except (TypeError, ValueError):
            raise ApiError(422, "VALIDACAO", "atraso_s e falhar_proximas devem ser numéricos.")
        with trava:
            sim.update(modo=modo, atraso_s=max(atraso, 0.0), falhar_proximas=max(falhas, 0))
        return jsonify(sim)

    @app.post("/api/governo/animais")
    def cadastrar_animal():
        conn = db.get_db()
        r = _repeticao(conn, CADASTRO)
        if r is not None:
            return r
        d = request.get_json(silent=True)
        v, erros = validar_animal(d)
        v["microchip"] = _microchip(d.get("microchip"), erros)
        if erros:
            return _rejeitar(conn, CADASTRO, v["microchip"] or None, 422, "VALIDACAO", "Dados inválidos.", erros)
        if conn.um("SELECT id FROM gov_animal WHERE microchip = %s", (v["microchip"],)):
            return _rejeitar(conn, CADASTRO, v["microchip"], 409, "ANIMAL_JA_CADASTRADO",
                             "Já existe animal cadastrado com este microchip.", {"microchip": v["microchip"]})

        def trabalho():
            agora = db.agora()
            conn.inserir("gov_animal", microchip=v["microchip"], nome=v["nome"], especie=v["especie"], raca=v["raca"],
                         sexo=v["sexo"], data_nascimento=v["data_nascimento"], tutor_nome=v["tutor_nome"],
                         tutor_cpf=v["tutor_cpf"], situacao=v["situacao"], criado_em=agora, atualizado_em=agora)
            _, corpo = _registrar_operacao(conn, CADASTRO, request.headers.get("Idempotency-Key"), v["microchip"],
                                           "PROCESSADA", 201, {"microchip": v["microchip"],
                                                               "mensagem": "Animal cadastrado com sucesso."})
            conn.commit()
            g.processou = True
            return jsonify(corpo), 201
        return _executar_idempotente(conn, CADASTRO, trabalho)

    @app.get("/api/governo/animais/<microchip>")
    def consultar_animal(microchip):
        conn = db.get_db()
        a = conn.um("SELECT * FROM gov_animal WHERE microchip = %s", (microchip,))
        if not a:
            raise ApiError(404, "ANIMAL_NAO_ENCONTRADO", "Nenhum animal cadastrado com este microchip.")
        a["vacinacoes_antirrabicas"] = conn.consultar(
            "SELECT protocolo, data_aplicacao, vacina, fabricante, numero_lote, veterinario_nome, veterinario_crmv "
            "FROM gov_vacinacao_antirrabica WHERE microchip = %s ORDER BY data_aplicacao", (microchip,))
        return jsonify(a)

    @app.put("/api/governo/animais/<microchip>")
    def atualizar_animal(microchip):
        conn = db.get_db()
        r = _repeticao(conn, ATUALIZACAO)
        if r is not None:
            return r
        d = request.get_json(silent=True)
        v, erros = validar_animal(d)
        if isinstance(d, dict) and d.get("microchip") not in (None, "", microchip):
            erros["microchip"] = "O microchip do corpo difere do informado na URL."
        if erros:
            return _rejeitar(conn, ATUALIZACAO, microchip, 422, "VALIDACAO", "Dados inválidos.", erros)
        if not conn.um("SELECT id FROM gov_animal WHERE microchip = %s", (microchip,)):
            return _rejeitar(conn, ATUALIZACAO, microchip, 404, "ANIMAL_NAO_ENCONTRADO",
                             "Nenhum animal cadastrado com este microchip.")

        def trabalho():
            conn.executar("UPDATE gov_animal SET nome=%s, especie=%s, raca=%s, sexo=%s, data_nascimento=%s, "
                          "tutor_nome=%s, tutor_cpf=%s, situacao=%s, atualizado_em=%s WHERE microchip=%s",
                          (v["nome"], v["especie"], v["raca"], v["sexo"], v["data_nascimento"], v["tutor_nome"],
                           v["tutor_cpf"], v["situacao"], db.agora(), microchip))
            _, corpo = _registrar_operacao(conn, ATUALIZACAO, request.headers.get("Idempotency-Key"), microchip,
                                           "PROCESSADA", 200, {"microchip": microchip,
                                                               "mensagem": "Cadastro atualizado com sucesso."})
            conn.commit()
            g.processou = True
            return jsonify(corpo), 200
        return _executar_idempotente(conn, ATUALIZACAO, trabalho)

    @app.post("/api/governo/vacinacoes-antirrabicas")
    def receber_vacinacao():
        conn = db.get_db()
        if not request.headers.get("Idempotency-Key"):
            raise ApiError(400, "IDEMPOTENCY_KEY_OBRIGATORIA", "Envie o cabeçalho Idempotency-Key.")
        r = _repeticao(conn, VACINACAO)
        if r is not None:
            return r
        v, erros = validar_vacinacao(request.get_json(silent=True))
        if erros:
            return _rejeitar(conn, VACINACAO, v.get("microchip") or None, 422, "VALIDACAO", "Dados inválidos.", erros)

        existente = conn.um(
            "SELECT protocolo FROM gov_vacinacao_antirrabica WHERE (microchip = %s AND id_aplicacao_origem = %s) "
            "OR (microchip = %s AND data_aplicacao = %s AND numero_lote = %s)",
            (v["microchip"], v["id_aplicacao_origem"], v["microchip"], v["data_aplicacao"], v["numero_lote"]))
        if existente:  # mesma vacinação enviada com outra chave: não duplica
            return _rejeitar(conn, VACINACAO, v["microchip"], 409, "VACINACAO_DUPLICADA",
                             "Esta vacinação já foi registrada.", extra={"protocolo_original": existente["protocolo"]})

        def trabalho():
            cadastrado = conn.um("SELECT id FROM gov_animal WHERE microchip = %s", (v["microchip"],)) is not None
            protocolo, corpo = _registrar_operacao(
                conn, VACINACAO, request.headers["Idempotency-Key"], v["microchip"], "PROCESSADA", 201,
                {"microchip": v["microchip"], "animal_cadastrado_no_governo": cadastrado,
                 "mensagem": "Vacinação antirrábica registrada."})
            conn.inserir("gov_vacinacao_antirrabica", protocolo=protocolo, microchip=v["microchip"],
                         id_aplicacao_origem=v["id_aplicacao_origem"], animal_origem_id=v["animal_origem_id"],
                         animal_nome=v["animal_nome"], data_aplicacao=v["data_aplicacao"], vacina=v["vacina"],
                         fabricante=v["fabricante"], numero_lote=v["numero_lote"],
                         veterinario_nome=v["veterinario_nome"], veterinario_crmv=v["veterinario_crmv"],
                         criada_em=db.agora())
            conn.commit()
            g.processou = True
            return jsonify(corpo), 201
        return _executar_idempotente(conn, VACINACAO, trabalho)

    @app.get("/api/governo/vacinacoes-antirrabicas")
    def listar_vacinacoes():
        conn = db.get_db()
        filtro, params = "", []
        if request.args.get("microchip"):
            filtro, params = "WHERE microchip = %s ", [request.args["microchip"]]
        return jsonify(conn.consultar("SELECT * FROM gov_vacinacao_antirrabica " + filtro + "ORDER BY id", params))

    @app.get("/api/governo/operacoes/<protocolo>")
    def consultar_operacao(protocolo):
        op = db.get_db().um("SELECT * FROM gov_operacao WHERE protocolo = %s", (protocolo,))
        if not op:
            raise ApiError(404, "PROTOCOLO_NAO_ENCONTRADO", "Protocolo inexistente.")
        corpo = json.loads(op["resposta"])
        return jsonify({"protocolo": op["protocolo"], "tipo": op["tipo"], "status": op["status"],
                        "microchip": op["microchip"], "codigo_http": op["codigo_http"],
                        "criada_em": op["criada_em"], "resposta": corpo})

    import os
    from .config import RAIZ

    @app.get("/openapi.yaml")
    def openapi():
        caminho = os.path.join(RAIZ, "docs", "openapi", "governo.yaml")
        if not os.path.isfile(caminho):
            raise ApiError(404, "NAO_ENCONTRADO", "OpenAPI ainda não gerado.")
        with open(caminho, encoding="utf-8") as f:
            return Response(f.read(), mimetype="application/yaml")

    @app.get("/docs")
    def docs():
        return Response(
            '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>API Governamental Simulada</title>'
            '<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head><body>'
            '<div id="ui"></div><script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>'
            '<script>SwaggerUIBundle({url:"/openapi.yaml",dom_id:"#ui"});</script></body></html>', mimetype="text/html")

    @app.get("/")
    def raiz():
        return jsonify({"servico": "API governamental SIMULADA (projeto acadêmico, não oficial)",
                        "documentacao": "/docs", "saude": "/api/governo/health"})

    return app
