"""Integração com a API governamental simulada.

Padrões usados (úteis para explicar na apresentação):

* OUTBOX — a solicitação de comunicação (linha PENDENTE em integracao_governo) é gravada
  na MESMA transação do registro local (vacina/microchip). Se o sistema cair logo depois,
  a pendência já existe e será enviada pelo reenvio. O envio vem só depois do commit.
* IDEMPOTÊNCIA — cada operação tem uma chave fixa (coluna chave_idempotencia, UNIQUE) enviada no
  cabeçalho Idempotency-Key. Reenviar a mesma operação nunca duplica o registro no governo.
* MÁQUINA DE ESTADOS —  PENDENTE -> ENVIADA -> CONFIRMADA | FALHA   (ver docs/01-...)
    PENDENTE   ainda não entregue (governo indisponível); será reenviada
    ENVIADA    tentativa feita sem resposta conclusiva (timeout/5xx); reenvio é seguro
    CONFIRMADA governo respondeu 200/201 com protocolo
    FALHA      governo rejeitou (4xx) ou o limite de tentativas automáticas acabou
"""
import json
import logging
import uuid

from flask import current_app

from ..db import agora
from ..errors import nao_encontrado, regra
from . import governo_client

log = logging.getLogger("clinica.integracao")

CADASTRO, ATUALIZACAO, VACINACAO = "CADASTRO_ANIMAL", "ATUALIZACAO_ANIMAL", "VACINACAO_ANTIRRABICA"

_SELECT = ("SELECT i.*, a.nome AS animal_nome, m.codigo_microchip AS microchip "
           "FROM integracao_governo i JOIN animal a ON a.id = i.animal_id "
           "LEFT JOIN vinculo_microchip m ON m.id = i.vinculo_microchip_id ")


# ------------------------------------------------------------------ consulta
def obter(conn, integ_id, com_payload=False):
    linha = conn.um(_SELECT + "WHERE i.id = %s", (integ_id,))
    if not linha:
        raise nao_encontrado("Integração", integ_id)
    return _dto(linha, com_payload)


def _dto(linha, com_payload=False):
    linha = dict(linha)
    payload = linha.pop("payload_enviado", None)
    if com_payload:
        try:
            linha["payload_enviado"] = json.loads(payload) if payload else None
        except ValueError:
            linha["payload_enviado"] = payload
    return linha


def listar(conn, args):
    filtros, params = [], []
    for campo, coluna in (("situacao", "i.situacao"), ("tipo_operacao", "i.tipo_operacao")):
        if args.get(campo):
            filtros.append(f"{coluna} = %s")
            params.append(args[campo].upper())
    if args.get("animal_id"):
        filtros.append("i.animal_id = %s")
        params.append(args["animal_id"])
    where = ("WHERE " + " AND ".join(filtros) + " ") if filtros else ""
    linhas = conn.consultar(_SELECT + where + "ORDER BY i.id DESC LIMIT 300", params)
    return [_dto(l) for l in linhas]


def resumo_do_animal(conn, animal_id):
    """Situação da integração governamental do animal (item 3.7.6 do enunciado)."""
    vinc = conn.um("SELECT * FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (animal_id,))
    pendencias = conn.escalar("SELECT COUNT(*) FROM integracao_governo WHERE animal_id = %s "
                              "AND situacao <> 'CONFIRMADA'", (animal_id,))
    if not vinc:
        return {"situacao_cadastro": "SEM_MICROCHIP", "protocolo_cadastro": None,
                "sincronizado": False, "pendencias": pendencias}
    cad = conn.um("SELECT * FROM integracao_governo WHERE animal_id = %s AND vinculo_microchip_id = %s "
                  "AND tipo_operacao = 'CADASTRO_ANIMAL' ORDER BY id DESC LIMIT 1", (animal_id, vinc["id"]))
    situacao = cad["situacao"] if cad else "NAO_SOLICITADO"
    return {"situacao_cadastro": situacao, "protocolo_cadastro": cad["protocolo_externo"] if cad else None,
            "sincronizado": situacao == "CONFIRMADA" and pendencias == 0, "pendencias": pendencias}


# ------------------------------------------------------------ solicitações (outbox)
def _criar(conn, animal_id, tipo, chave, vinculo_id=None, vacina_id=None):
    return conn.inserir("integracao_governo", animal_id=animal_id, vacina_id=vacina_id,
                        vinculo_microchip_id=vinculo_id, tipo_operacao=tipo, protocolo_externo=None,
                        chave_idempotencia=chave, situacao="PENDENTE", solicitada_em=agora(),
                        respondida_em=None, ultima_tentativa_em=None, tentativas=0, mensagem_erro=None,
                        payload_enviado=None)


def solicitar_cadastro(conn, animal_id, vinculo):
    return _criar(conn, animal_id, CADASTRO, f"animal-{animal_id}-chip-{vinculo['codigo_microchip']}-cadastro",
                  vinculo_id=vinculo["id"])


def solicitar_atualizacao(conn, animal_id, vinculo):
    return _criar(conn, animal_id, ATUALIZACAO, f"animal-{animal_id}-chip-{vinculo['codigo_microchip']}-"
                  f"atualizacao-{uuid.uuid4().hex[:10]}", vinculo_id=vinculo["id"])


def solicitar_vacinacao(conn, vacina):
    """Cria a solicitação obrigatória da vacina antirrábica (1 por aplicação: UNIQUE(vacina_id))."""
    vinc = conn.um("SELECT id FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (vacina["animal_id"],))
    return _criar(conn, vacina["animal_id"], VACINACAO, f"vacina-{vacina['id']}-antirrabica",
                  vinculo_id=vinc["id"] if vinc else None, vacina_id=vacina["id"])


def cancelar_cadastros_pendentes(conn, animal_id, vinculo_id, motivo):
    conn.executar("UPDATE integracao_governo SET situacao = 'FALHA', mensagem_erro = %s "
                  "WHERE animal_id = %s AND vinculo_microchip_id = %s AND tipo_operacao IN (%s, %s) "
                  "AND situacao <> 'CONFIRMADA'", (motivo, animal_id, vinculo_id, CADASTRO, ATUALIZACAO))


# ------------------------------------------------------------------- payloads
def _payload_animal(conn, animal_id, codigo):
    a = conn.um("SELECT a.*, t.nome_completo AS tutor_nome, t.cpf AS tutor_cpf, e.nome AS especie_nome, "
                "r.nome AS raca_nome FROM animal a JOIN tutor t ON t.id = a.tutor_id "
                "JOIN especie e ON e.id = a.especie_id LEFT JOIN raca r ON r.id = a.raca_id WHERE a.id = %s",
                (animal_id,))
    return {"microchip": codigo, "nome": a["nome"], "especie": a["especie_nome"], "raca": a["raca_nome"],
            "sexo": a["sexo"], "data_nascimento": a["data_nascimento"], "situacao": a["situacao"],
            "tutor": {"nome_completo": a["tutor_nome"], "cpf": a["tutor_cpf"]}}


def payload_animal_para_comparacao(conn, animal_id):
    return _payload_animal(conn, animal_id, "")


def _payload_vacinacao(conn, integ, vinc):
    v = conn.um("SELECT va.*, vt.nome_completo AS vet_nome, vt.crmv_numero, vt.crmv_uf, a.nome AS animal_nome "
                "FROM vacina va JOIN veterinario vt ON vt.id = va.veterinario_id "
                "JOIN animal a ON a.id = va.animal_id WHERE va.id = %s", (integ["vacina_id"],))
    return {"microchip": vinc["codigo_microchip"],
            "animal": {"id": v["animal_id"], "nome": v["animal_nome"]},
            "data_aplicacao": v["data_aplicacao"],
            "vacina": {"id_aplicacao": v["id"], "nome": v["nome_vacina"], "fabricante": v["fabricante"],
                       "numero_lote": v["numero_lote"]},
            "veterinario": {"id": v["veterinario_id"], "nome_completo": v["vet_nome"],
                            "crmv": f"{v['crmv_numero']}/{v['crmv_uf']}"}}


def _montar(conn, integ, vinc):
    tipo = integ["tipo_operacao"]
    if tipo == CADASTRO:
        return "POST", "/api/governo/animais", _payload_animal(conn, integ["animal_id"], vinc["codigo_microchip"])
    if tipo == ATUALIZACAO:
        return ("PUT", f"/api/governo/animais/{vinc['codigo_microchip']}",
                _payload_animal(conn, integ["animal_id"], vinc["codigo_microchip"]))
    return "POST", "/api/governo/vacinacoes-antirrabicas", _payload_vacinacao(conn, integ, vinc)


# ---------------------------------------------------------------------- envio
def enviar(conn, integ_id, automatico=False, forcar=False):
    """Tenta entregar uma operação ao governo e registra o resultado.

    forcar=True reenvia mesmo uma operação já CONFIRMADA (usado para demonstrar que a repetição
    não duplica nada no governo): a situação/protocolo originais não são alterados.
    """
    cfg = current_app.config["SDM"]
    bruta = conn.um("SELECT * FROM integracao_governo WHERE id = %s", (integ_id,))
    if not bruta:
        raise nao_encontrado("Integração", integ_id)
    ja_confirmada = bruta["situacao"] == "CONFIRMADA"
    if ja_confirmada and not forcar:
        return {**obter(conn, integ_id), "ultima_resposta": None}

    vinc = conn.um("SELECT * FROM vinculo_microchip WHERE id = %s", (bruta["vinculo_microchip_id"],))
    if vinc is None:
        raise regra("SEM_MICROCHIP", "A operação não tem microchip associado; vincule um microchip ao animal.")
    if bruta["tipo_operacao"] != VACINACAO and vinc["situacao"] != "ATIVO":
        conn.atualizar("integracao_governo", integ_id, situacao="FALHA", respondida_em=agora(),
                       mensagem_erro="Microchip substituído; operação descartada.")
        conn.commit()
        return {**obter(conn, integ_id), "ultima_resposta": None}

    metodo, caminho, payload = _montar(conn, bruta, vinc)
    if ja_confirmada:  # reenvio forçado: só conta a tentativa
        conn.atualizar("integracao_governo", integ_id, tentativas=bruta["tentativas"] + 1, ultima_tentativa_em=agora())
    else:
        conn.atualizar("integracao_governo", integ_id, situacao="ENVIADA", tentativas=bruta["tentativas"] + 1,
                       ultima_tentativa_em=agora(), payload_enviado=json.dumps(payload, ensure_ascii=False),
                       mensagem_erro=None)
    conn.commit()  # a tentativa fica registrada ANTES de chamar a rede (se cair, sobra 'ENVIADA')

    res = governo_client.chamar(metodo, caminho, payload, bruta["chave_idempotencia"])
    log.info("integracao %s (%s) -> %s %s", integ_id, bruta["tipo_operacao"], res.categoria, res.status or "")
    tentativas = bruta["tentativas"] + 1

    if not ja_confirmada:
        campos = _aplicar_resultado(res, tentativas, automatico, cfg["GOV_MAX_TENTATIVAS"])
        conn.atualizar("integracao_governo", integ_id, **campos)
        conn.commit()
    return {**obter(conn, integ_id),
            "ultima_resposta": {"categoria": res.categoria, "status_http": res.status, "corpo": res.corpo,
                                "repeticao_idempotente": bool(res.corpo.get("repetida"))}}


def _aplicar_resultado(res, tentativas, automatico, maximo):
    agora_s = agora()
    if res.categoria == "OK":
        return {"situacao": "CONFIRMADA", "protocolo_externo": res.corpo.get("protocolo"),
                "respondida_em": agora_s, "mensagem_erro": None}
    if res.categoria == "REJEITADO":
        return {"situacao": "FALHA", "protocolo_externo": res.corpo.get("protocolo"),
                "respondida_em": agora_s, "mensagem_erro": res.mensagem[:500]}
    # transitórios: INDISPONIVEL (não processou) ou INCERTO (pode ter processado)
    if automatico and tentativas >= maximo:
        return {"situacao": "FALHA", "mensagem_erro":
                f"Limite de {maximo} tentativas automáticas atingido. Último erro: {res.mensagem}"[:500]}
    if res.categoria == "INCERTO":
        return {"situacao": "ENVIADA",
                "mensagem_erro": (res.mensagem + " O reenvio é seguro (idempotente).")[:500]}
    return {"situacao": "PENDENTE", "mensagem_erro": res.mensagem[:500]}


def reprocessar(conn, automatico=True):
    """Reenvia operações PENDENTE/ENVIADA. No modo automático respeita o limite de tentativas."""
    sql = "SELECT id FROM integracao_governo WHERE situacao IN ('PENDENTE','ENVIADA')"
    params = []
    if automatico:
        sql += " AND tentativas < %s"
        params.append(current_app.config["SDM"]["GOV_MAX_TENTATIVAS"])
    ids = [r["id"] for r in conn.consultar(sql + " ORDER BY id", params)]
    resumo = {"analisadas": len(ids), "confirmadas": 0, "ainda_pendentes": 0, "falhas": 0}
    for i in ids:
        r = enviar(conn, i, automatico=automatico)
        if r["situacao"] == "CONFIRMADA":
            resumo["confirmadas"] += 1
        elif r["situacao"] == "FALHA":
            resumo["falhas"] += 1
        else:
            resumo["ainda_pendentes"] += 1
        if r["ultima_resposta"] and r["ultima_resposta"]["categoria"] == "INDISPONIVEL":
            resumo["ainda_pendentes"] += len(ids) - ids.index(i) - 1  # governo fora do ar: não insiste nas demais
            break
    return resumo
