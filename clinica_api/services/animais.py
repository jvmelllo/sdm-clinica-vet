"""Animais e vínculo de microchip RFID."""
from flask import g

from ..db import agora, erros_de_integridade, get_db
from ..errors import conflito, nao_encontrado, regra, validacao
from ..validators import Campos
from . import integracao
from ._comum import obter_ou_404, paginacao

SELECT = ("SELECT a.*, t.nome_completo AS tutor_nome, e.nome AS especie_nome, r.nome AS raca_nome "
          "FROM animal a JOIN tutor t ON t.id = a.tutor_id JOIN especie e ON e.id = a.especie_id "
          "LEFT JOIN raca r ON r.id = a.raca_id ")


# ------------------------------------------------------------------- consulta
def microchip_atual(conn, animal_id):
    return conn.um("SELECT m.id, m.codigo_microchip AS codigo, m.data_vinculo, m.veterinario_id, "
                   "v.nome_completo AS veterinario_nome FROM vinculo_microchip m "
                   "JOIN veterinario v ON v.id = m.veterinario_id "
                   "WHERE m.animal_id = %s AND m.vigente = 1", (animal_id,))


def _dto(conn, animal_id, detalhado=True):
    a = conn.um(SELECT + "WHERE a.id = %s", (animal_id,))
    if not a:
        raise nao_encontrado("Animal", animal_id)
    a["sem_raca_definida"] = a["raca_id"] is None
    a["microchip_atual"] = microchip_atual(conn, animal_id)
    if detalhado:
        a["integracao_governo"] = integracao.resumo_do_animal(conn, animal_id)
    return a


def obter(animal_id):
    return _dto(get_db(), animal_id)


def listar(args):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    for campo, coluna in (("tutor_id", "a.tutor_id"), ("especie_id", "a.especie_id")):
        if args.get(campo):
            filtros.append(f"{coluna} = %s")
            params.append(args[campo])
    if args.get("situacao"):
        filtros.append("a.situacao = %s")
        params.append(args["situacao"].upper())
    if args.get("q"):
        filtros.append("(a.nome LIKE %s OR t.nome_completo LIKE %s)")
        params += [f"%{args['q']}%"] * 2
    if args.get("microchip"):
        filtros.append("EXISTS (SELECT 1 FROM vinculo_microchip m WHERE m.animal_id = a.id AND m.codigo_microchip = %s)")
        params.append(args["microchip"])
    where = ("WHERE " + " AND ".join(filtros) + " ") if filtros else ""
    linhas = conn.consultar(
        SELECT.replace("r.nome AS raca_nome ", "r.nome AS raca_nome, (SELECT m.codigo_microchip FROM vinculo_microchip m "
                       "WHERE m.animal_id = a.id AND m.vigente = 1) AS microchip ")
        + where + "ORDER BY a.nome LIMIT %s OFFSET %s", [*params, limite, offset])
    return linhas


# ----------------------------------------------------------------- escrita
def _validar(conn, dados):
    c = Campos(dados)
    c.texto("nome", max_len=80)
    nasc = c.data("data_nascimento", obrigatorio=False, futura=False)
    idade = c.inteiro("idade_estimada_meses", obrigatorio=False, minimo=0, maximo=600)
    if nasc is None and idade is None:
        c.erro("data_nascimento", "Informe a data de nascimento ou a idade estimada (em meses).")
    c.opcao("sexo", {"MACHO", "FEMEA"})
    c.texto("cor", max_len=50)
    c.decimal("peso_atual", minimo=0.01, maximo=2000)
    tutor_id = c.inteiro("tutor_id", minimo=1)
    esp_id = c.inteiro("especie_id", minimo=1)
    raca_id = c.inteiro("raca_id", obrigatorio=False, minimo=1)
    c.opcao("situacao", {"ATIVO", "INATIVO", "OBITO"}, obrigatorio=False, padrao="ATIVO")
    v = c.ok()

    tutor = obter_ou_404(conn, "tutor", tutor_id, "Tutor")
    if tutor["situacao"] != "ATIVO":
        raise regra("TUTOR_INATIVO", "O tutor informado está inativo.")
    especie = obter_ou_404(conn, "especie", esp_id, "Espécie")
    if especie["situacao"] != "ATIVA":
        raise regra("ESPECIE_INATIVA", "A espécie informada está inativa.")
    if raca_id is not None:
        raca = obter_ou_404(conn, "raca", raca_id, "Raça")
        if raca["especie_id"] != esp_id:
            raise regra("RACA_INCOMPATIVEL", "A raça selecionada não pertence à espécie informada.",
                        {"raca_id": raca_id, "especie_id": esp_id})
        if raca["situacao"] != "ATIVA":
            raise regra("RACA_INATIVA", "A raça informada está inativa.")
    return v


def criar(dados):
    conn = get_db()
    v = _validar(conn, dados)
    id_ = conn.inserir("animal", nome=v["nome"], data_nascimento=v["data_nascimento"],
                       idade_estimada_meses=v["idade_estimada_meses"], sexo=v["sexo"], cor=v["cor"],
                       peso_atual=v["peso_atual"], tutor_id=v["tutor_id"], especie_id=v["especie_id"],
                       raca_id=v["raca_id"], situacao=v["situacao"], data_cadastro=agora())
    conn.commit()
    return _dto(conn, id_)


def atualizar(animal_id, dados):
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    v = _validar(conn, dados)
    antes = integracao.payload_animal_para_comparacao(conn, animal_id)
    conn.atualizar("animal", animal_id, nome=v["nome"], data_nascimento=v["data_nascimento"],
                   idade_estimada_meses=v["idade_estimada_meses"], sexo=v["sexo"], cor=v["cor"],
                   peso_atual=v["peso_atual"], tutor_id=v["tutor_id"], especie_id=v["especie_id"],
                   raca_id=v["raca_id"], situacao=v["situacao"])
    return _fechar_atualizacao(conn, animal_id, antes)


def mudar_situacao(animal_id, nova):
    conn = get_db()
    atual = obter_ou_404(conn, "animal", animal_id, "Animal")
    if nova == "ATIVO":
        tutor = obter_ou_404(conn, "tutor", atual["tutor_id"], "Tutor")
        if tutor["situacao"] != "ATIVO":
            raise regra("TUTOR_INATIVO", "Reative o tutor antes de reativar o animal.")
    antes = integracao.payload_animal_para_comparacao(conn, animal_id)
    conn.atualizar("animal", animal_id, situacao=nova)
    return _fechar_atualizacao(conn, animal_id, antes)


def _fechar_atualizacao(conn, animal_id, antes):
    """Se mudou algo que o governo guarda e o cadastro lá já foi confirmado, comunica a atualização.
    (Se o cadastro ainda está pendente, o reenvio dele já leva os dados atuais.)"""
    depois = integracao.payload_animal_para_comparacao(conn, animal_id)
    vinc = conn.um("SELECT * FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (animal_id,))
    integ_id = None
    if vinc and antes != depois:
        cad = conn.um("SELECT situacao FROM integracao_governo WHERE vinculo_microchip_id = %s "
                      "AND tipo_operacao = 'CADASTRO_ANIMAL' ORDER BY id DESC LIMIT 1", (vinc["id"],))
        if cad and cad["situacao"] == "CONFIRMADA":
            integ_id = integracao.solicitar_atualizacao(conn, animal_id, vinc)
    conn.commit()
    resposta = _dto(conn, animal_id)
    if integ_id:
        resposta["atualizacao_governo"] = integracao.enviar(conn, integ_id)
        resposta["integracao_governo"] = integracao.resumo_do_animal(conn, animal_id)
    return resposta


# ------------------------------------------------------------------ microchip
def vincular_microchip(animal_id, dados):
    conn = get_db()
    vet = g.vet  # já validado como ATIVO e com senha confirmada por @login_required
    animal = obter_ou_404(conn, "animal", animal_id, "Animal")
    c = Campos(dados)
    codigo = c.microchip("codigo")
    substituir = c.booleano("substituir", padrao=False)
    motivo = c.texto("motivo_substituicao", obrigatorio=False, max_len=255)
    c.ok()

    if animal["situacao"] != "ATIVO":
        raise regra("ANIMAL_INATIVO", "Não é possível vincular microchip a um animal inativo.")
    existente = conn.um("SELECT animal_id FROM vinculo_microchip WHERE codigo_microchip = %s", (codigo,))
    if existente:
        raise conflito("MICROCHIP_JA_UTILIZADO", "Este microchip já está vinculado a um animal e não pode ser reutilizado.",
                       {"animal_id": existente["animal_id"]})
    atual = conn.um("SELECT * FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (animal_id,))
    if atual and not substituir:
        raise conflito("ANIMAL_JA_POSSUI_MICROCHIP",
                       "O animal já possui um microchip. Para trocá-lo envie substituir=true e o motivo.",
                       {"microchip_atual": atual["codigo_microchip"]})
    if atual and not motivo:
        raise validacao({"motivo_substituicao": "Informe o motivo da substituição do microchip."})

    try:
        if atual:  # preserva o histórico: o vínculo antigo continua gravado, só deixa de ser vigente
            conn.atualizar("vinculo_microchip", atual["id"], situacao="SUBSTITUIDO", vigente=None,
                           data_substituicao=agora(), motivo_substituicao=motivo)
            integracao.cancelar_cadastros_pendentes(conn, animal_id, atual["id"],
                                                    "Microchip substituído antes da confirmação.")
        vinculo_id = conn.inserir("vinculo_microchip", animal_id=animal_id, codigo_microchip=codigo,
                                  veterinario_id=vet["id"], data_vinculo=agora(), situacao="ATIVO", vigente=1,
                                  data_substituicao=None, motivo_substituicao=None)
        vinculo = conn.um("SELECT * FROM vinculo_microchip WHERE id = %s", (vinculo_id,))
        integ_id = integracao.solicitar_cadastro(conn, animal_id, vinculo)
        conn.commit()
    except erros_de_integridade():
        conn.rollback()
        raise conflito("MICROCHIP_JA_UTILIZADO", "Este microchip já está em uso.")

    envio = integracao.enviar(conn, integ_id)
    return {"vinculo": historico_item(conn, vinculo_id), "animal": _dto(conn, animal_id),
            "integracao_governo": envio}


def historico_item(conn, vinculo_id):
    return conn.um("SELECT m.id, m.animal_id, m.codigo_microchip, m.data_vinculo, m.situacao, "
                   "m.data_substituicao, m.motivo_substituicao, m.veterinario_id, "
                   "v.nome_completo AS veterinario_nome, v.crmv_numero, v.crmv_uf "
                   "FROM vinculo_microchip m JOIN veterinario v ON v.id = m.veterinario_id WHERE m.id = %s",
                   (vinculo_id,))


def historico_microchips(animal_id):
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    return conn.consultar("SELECT m.id, m.animal_id, m.codigo_microchip, m.data_vinculo, m.situacao, "
                          "m.data_substituicao, m.motivo_substituicao, m.veterinario_id, "
                          "v.nome_completo AS veterinario_nome, v.crmv_numero, v.crmv_uf "
                          "FROM vinculo_microchip m JOIN veterinario v ON v.id = m.veterinario_id "
                          "WHERE m.animal_id = %s ORDER BY m.id DESC", (animal_id,))


# ------------------------------------------------------- integração governamental
def integracao_governo(animal_id):
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    return {**integracao.resumo_do_animal(conn, animal_id),
            "operacoes": integracao.listar(conn, {"animal_id": animal_id})}


def sincronizar(animal_id):
    """Sincronização manual: (re)envia o cadastro pendente ou comunica a atualização dos dados."""
    conn = get_db()
    obter_ou_404(conn, "animal", animal_id, "Animal")
    vinc = conn.um("SELECT * FROM vinculo_microchip WHERE animal_id = %s AND vigente = 1", (animal_id,))
    if not vinc:
        raise regra("SEM_MICROCHIP", "O animal não possui microchip vinculado; não há o que sincronizar.")
    cad = conn.um("SELECT * FROM integracao_governo WHERE vinculo_microchip_id = %s "
                  "AND tipo_operacao = 'CADASTRO_ANIMAL' ORDER BY id DESC LIMIT 1", (vinc["id"],))
    if cad is None:
        integ_id = integracao.solicitar_cadastro(conn, animal_id, vinc)
    elif cad["situacao"] != "CONFIRMADA":
        integ_id = cad["id"]
    else:
        integ_id = integracao.solicitar_atualizacao(conn, animal_id, vinc)
    conn.commit()
    return {"operacao": integracao.enviar(conn, integ_id),
            "integracao_governo": integracao.resumo_do_animal(conn, animal_id)}
