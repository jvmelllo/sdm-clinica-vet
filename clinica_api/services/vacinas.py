"""Registro de vacinas e comunicação obrigatória da antirrábica ao governo.

Ponto central do projeto: a comunicação ocorre DEPOIS do registro local (que já está
commitado junto com a solicitação PENDENTE) e o resultado dela é guardado à parte, em
integracao_governo. Assim "vacina aplicada" (local) e "governo confirmou" são fatos distintos.
"""
from datetime import date

from flask import g

from ..db import get_db, hoje
from ..errors import conflito, regra, validacao
from ..validators import Campos
from . import integracao
from ._comum import em_bool, obter_ou_404

TIPOS = {"ANTIRRABICA", "POLIVALENTE", "TRIPLICE_FELINA", "GRIPE_CANINA", "GIARDIA", "LEISHMANIOSE", "OUTRA"}
VIAS = {"SUBCUTANEA", "INTRAMUSCULAR", "INTRANASAL", "ORAL"}

SELECT = ("SELECT va.*, a.nome AS animal_nome, v.nome_completo AS veterinario_nome, "
          "ig.id AS integracao_id, ig.situacao AS gov_situacao, ig.protocolo_externo AS gov_protocolo, "
          "ig.tentativas AS gov_tentativas "
          "FROM vacina va JOIN animal a ON a.id = va.animal_id "
          "JOIN veterinario v ON v.id = va.veterinario_id "
          "LEFT JOIN integracao_governo ig ON ig.vacina_id = va.id ")


def _dto(linha):
    linha = dict(linha)
    linha["antirrabica"] = em_bool(linha["antirrabica"])
    gov = {"obrigatoria": linha["antirrabica"] and linha["situacao"] == "APLICADA",
           "integracao_id": linha.pop("integracao_id"), "situacao": linha.pop("gov_situacao"),
           "protocolo": linha.pop("gov_protocolo"), "tentativas": linha.pop("gov_tentativas")}
    linha["comunicacao_governo"] = gov
    return linha


def obter(conn, vacina_id):
    linha = conn.um(SELECT + "WHERE va.id = %s", (vacina_id,))
    if not linha:
        obter_ou_404(conn, "vacina", vacina_id, "Vacina")
    return _dto(linha)


def obter_publico(vacina_id):
    return obter(get_db(), vacina_id)


# ------------------------------------------------------------------ validação
def _validar(conn, dados, animal_id=None, situacao_forcada=None, padrao_data=None):
    c = Campos(dados)
    if animal_id is None:
        animal_id = c.inteiro("animal_id", minimo=1)
    vet_id = c.inteiro("veterinario_id", obrigatorio=False, minimo=1) or g.vet["id"]
    c.texto("nome_vacina", max_len=100)
    tipo = c.opcao("tipo_vacina", TIPOS)
    informado = c.booleano("antirrabica")
    c.texto("fabricante", obrigatorio=False, max_len=100)
    c.texto("numero_lote", obrigatorio=False, max_len=50)
    if padrao_data and not dados.get("data_aplicacao"):
        dados = {**dados, "data_aplicacao": padrao_data}
        c.d = dados
    c.data("data_aplicacao")
    c.texto("dose", max_len=40)
    c.opcao("via_aplicacao", VIAS)
    c.data("data_proxima_dose", obrigatorio=False)
    c.data("validade_lote", obrigatorio=False)
    c.texto("observacoes", obrigatorio=False, max_len=5000)
    c.opcao("situacao", {"AGENDADA", "APLICADA"}, obrigatorio=False, padrao=situacao_forcada or "APLICADA")
    v = c.ok()
    if situacao_forcada:
        v["situacao"] = situacao_forcada

    # A antirrábica é definida pela CLASSIFICAÇÃO (tipo_vacina), nunca pelo texto do nome.
    v["antirrabica"] = (tipo == "ANTIRRABICA")
    if informado is not None and informado != v["antirrabica"]:
        raise validacao({"antirrabica": "Inconsistente com tipo_vacina (antirrábica = tipo ANTIRRABICA)."},
                        "Classificação da vacina inconsistente.")
    v["animal_id"], v["veterinario_id"] = animal_id, vet_id

    erros = {}
    if v["data_proxima_dose"] and v["data_proxima_dose"] <= v["data_aplicacao"]:
        erros["data_proxima_dose"] = "Deve ser posterior à data de aplicação."
    if v["situacao"] == "APLICADA":
        for campo in ("fabricante", "numero_lote", "validade_lote"):
            if not v[campo]:
                erros[campo] = "Obrigatório para vacina aplicada."
        if v["data_aplicacao"] > hoje():
            erros["data_aplicacao"] = "Vacina aplicada não pode ter data futura."
    elif v["data_aplicacao"] < hoje():
        erros["data_aplicacao"] = "Vacina agendada deve ter data de hoje ou futura."
    if erros:
        raise validacao(erros)
    if v["situacao"] == "APLICADA" and v["validade_lote"] < v["data_aplicacao"]:
        raise regra("LOTE_VENCIDO", "O lote estava vencido na data da aplicação.",
                    {"validade_lote": v["validade_lote"], "data_aplicacao": v["data_aplicacao"]})

    animal = obter_ou_404(conn, "animal", animal_id, "Animal")
    if animal["situacao"] != "ATIVO":
        raise regra("ANIMAL_INATIVO", "Não é possível registrar vacina para animal inativo.")
    vet = obter_ou_404(conn, "veterinario", vet_id, "Veterinário")
    if vet["situacao"] != "ATIVO":
        raise regra("VETERINARIO_INATIVO", "O veterinário responsável está inativo.")
    return v


def _exige_microchip_se_antirrabica(conn, v):
    if v["antirrabica"] and v["situacao"] == "APLICADA":
        if not conn.um("SELECT id FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (v["animal_id"],)):
            raise regra("ANIMAL_SEM_MICROCHIP",
                        "A vacina antirrábica exige comunicação ao governo identificada pelo microchip. "
                        "Vincule o microchip ao animal antes de registrar a aplicação.")


_COLUNAS = ("veterinario_id", "nome_vacina", "tipo_vacina", "antirrabica", "fabricante", "numero_lote",
            "data_aplicacao", "dose", "via_aplicacao", "data_proxima_dose", "validade_lote", "observacoes",
            "situacao")


def _resposta(conn, vacina_id):
    """Registro local + estado da comunicação com o governo (que pode estar pendente)."""
    vacina = obter(conn, vacina_id)
    resposta = {"vacina": vacina}
    if vacina["comunicacao_governo"]["obrigatoria"] and vacina["comunicacao_governo"]["integracao_id"]:
        resposta["comunicacao_governo"] = integracao.obter(conn, vacina["comunicacao_governo"]["integracao_id"])
    else:
        resposta["comunicacao_governo"] = None  # vacina não antirrábica: sem comunicação obrigatória
    return resposta


def _gravar_e_comunicar(conn, vacina_id):
    vacina = conn.um("SELECT * FROM vacina WHERE id = %s", (vacina_id,))
    integ_id = None
    if vacina["antirrabica"] and vacina["situacao"] == "APLICADA":
        integ_id = integracao.solicitar_vacinacao(conn, vacina)
    conn.commit()                       # 1) registro local + solicitação pendente, juntos
    if integ_id:
        integracao.enviar(conn, integ_id)   # 2) só então tenta o governo (falha não desfaz o passo 1)
    return _resposta(conn, vacina_id)


# ------------------------------------------------------------------ operações
def criar(dados):
    conn = get_db()
    v = _validar(conn, dados)
    _exige_microchip_se_antirrabica(conn, v)
    id_ = conn.inserir("vacina", animal_id=v["animal_id"], **{c: v[c] for c in _COLUNAS})
    return _gravar_e_comunicar(conn, id_)


def aplicar(vacina_id, dados):
    """Converte uma vacina AGENDADA em APLICADA (informando lote/validade) e comunica se antirrábica."""
    conn = get_db()
    atual = obter_ou_404(conn, "vacina", vacina_id, "Vacina")
    if atual["situacao"] != "AGENDADA":
        raise conflito("VACINA_NAO_AGENDADA", "Somente vacinas agendadas podem ser aplicadas.")
    base = {"nome_vacina": atual["nome_vacina"], "tipo_vacina": atual["tipo_vacina"], "dose": atual["dose"],
            "via_aplicacao": atual["via_aplicacao"], "veterinario_id": atual["veterinario_id"],
            "data_proxima_dose": atual["data_proxima_dose"], "observacoes": atual["observacoes"]}
    base.update({k: val for k, val in dados.items() if k in (
        "fabricante", "numero_lote", "validade_lote", "data_aplicacao", "data_proxima_dose", "observacoes",
        "dose", "via_aplicacao", "veterinario_id")})
    v = _validar(conn, base, animal_id=atual["animal_id"], situacao_forcada="APLICADA", padrao_data=hoje())
    _exige_microchip_se_antirrabica(conn, v)
    conn.atualizar("vacina", vacina_id, **{c: v[c] for c in _COLUNAS})
    return _gravar_e_comunicar(conn, vacina_id)


def cancelar(vacina_id):
    conn = get_db()
    atual = obter_ou_404(conn, "vacina", vacina_id, "Vacina")
    if atual["situacao"] == "APLICADA":
        raise conflito("VACINA_APLICADA", "Vacina já aplicada faz parte do histórico e não pode ser cancelada.")
    conn.atualizar("vacina", vacina_id, situacao="CANCELADA")
    conn.commit()
    return obter(conn, vacina_id)


def historico_do_animal(animal_id, args):
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    filtros, params = ["va.animal_id = %s"], [animal_id]
    if args.get("situacao"):
        filtros.append("va.situacao = %s")
        params.append(args["situacao"].upper())
    linhas = conn.consultar(SELECT + "WHERE " + " AND ".join(filtros) +
                            " ORDER BY va.data_aplicacao DESC, va.id DESC", params)
    return [_dto(l) for l in linhas]


def proximas_doses(animal_id):
    """Próximas doses previstas: reforços informados nas aplicações + vacinas agendadas.

    Um reforço deixa de aparecer quando já existe aplicação posterior da mesma vacina."""
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    reforcos = conn.consultar(
        "SELECT v.id, v.nome_vacina, v.tipo_vacina, v.dose, v.data_proxima_dose AS data_prevista "
        "FROM vacina v WHERE v.animal_id = %s AND v.situacao = 'APLICADA' AND v.data_proxima_dose IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM vacina v2 WHERE v2.animal_id = v.animal_id AND v2.nome_vacina = v.nome_vacina "
        "AND v2.situacao = 'APLICADA' AND v2.data_aplicacao > v.data_aplicacao)", (animal_id,))
    agendadas = conn.consultar(
        "SELECT v.id, v.nome_vacina, v.tipo_vacina, v.dose, v.data_aplicacao AS data_prevista "
        "FROM vacina v WHERE v.animal_id = %s AND v.situacao = 'AGENDADA'", (animal_id,))
    hoje_d = date.today()
    itens = []
    for origem, lista in (("REFORCO_PREVISTO", reforcos), ("AGENDADA", agendadas)):
        for r in lista:
            dias = (date.fromisoformat(r["data_prevista"]) - hoje_d).days
            itens.append({"vacina_id": r["id"], "nome_vacina": r["nome_vacina"], "tipo_vacina": r["tipo_vacina"],
                          "dose_anterior" if origem == "REFORCO_PREVISTO" else "dose": r["dose"],
                          "data_prevista": r["data_prevista"], "origem": origem, "dias_para_a_data": dias,
                          "situacao_prazo": "ATRASADA" if dias < 0 else ("HOJE" if dias == 0 else "NO_PRAZO")})
    return sorted(itens, key=lambda i: i["data_prevista"])


def comunicacao(vacina_id):
    """Estado da comunicação ao governo, separando registro local e confirmação externa."""
    conn = get_db()
    vacina = obter(conn, vacina_id)
    gov = vacina["comunicacao_governo"]
    base = {"vacina_id": vacina_id, "antirrabica": vacina["antirrabica"],
            "registro_local": vacina["situacao"], "comunicacao_obrigatoria": gov["obrigatoria"]}
    if not gov["obrigatoria"]:
        motivo = ("vacina não antirrábica" if not vacina["antirrabica"] else f"vacina {vacina['situacao'].lower()}")
        return {**base, "confirmacao_governo": "NAO_APLICAVEL", "observacao": f"Sem comunicação obrigatória ({motivo}).",
                "integracao": None}
    integ = integracao.obter(conn, gov["integracao_id"], com_payload=True) if gov["integracao_id"] else None
    return {**base, "confirmacao_governo": integ["situacao"] if integ else "NAO_SOLICITADA", "integracao": integ}
