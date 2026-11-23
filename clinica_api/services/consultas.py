"""Registro de consultas (histórico clínico dos animais)."""
from datetime import datetime, timedelta

from flask import g

from ..db import get_db
from ..errors import conflito, regra
from ..validators import Campos, parse_datahora
from ._comum import obter_ou_404, paginacao

SITUACOES = {"AGENDADA", "REALIZADA", "CANCELADA", "NAO_COMPARECEU"}
SELECT = ("SELECT c.*, a.nome AS animal_nome, v.nome_completo AS veterinario_nome "
          "FROM consulta c JOIN animal a ON a.id = c.animal_id "
          "JOIN veterinario v ON v.id = c.veterinario_id ")
CAMPOS_TEXTO = ("anamnese", "sintomas", "diagnostico", "tratamento", "prescricao_medicamentos", "observacoes")


def _validar(conn, dados, animal_id=None):
    c = Campos(dados)
    if animal_id is None:
        animal_id = c.inteiro("animal_id", minimo=1)
    vet_id = c.inteiro("veterinario_id", obrigatorio=False, minimo=1) or g.vet["id"]
    c.datahora("data_hora")
    c.texto("motivo", max_len=255)
    for campo in CAMPOS_TEXTO:
        c.texto(campo, obrigatorio=False, max_len=5000)
    c.decimal("peso_kg", obrigatorio=False, minimo=0.01, maximo=2000)
    c.decimal("temperatura_c", obrigatorio=False, minimo=30, maximo=45, casas=1)
    c.opcao("situacao", SITUACOES, obrigatorio=False, padrao="AGENDADA")
    v = c.ok()
    v["animal_id"], v["veterinario_id"] = animal_id, vet_id

    animal = obter_ou_404(conn, "animal", animal_id, "Animal")
    if animal["situacao"] != "ATIVO":
        raise regra("ANIMAL_INATIVO", "Não é possível registrar consulta para animal inativo.")
    vet = obter_ou_404(conn, "veterinario", vet_id, "Veterinário")
    if vet["situacao"] != "ATIVO":
        raise regra("VETERINARIO_INATIVO", "O veterinário responsável está inativo.")
    if v["situacao"] == "REALIZADA" and parse_datahora(v["data_hora"]) > datetime.now() + timedelta(minutes=5):
        raise regra("CONSULTA_FUTURA", "Uma consulta realizada não pode ter data/hora no futuro.")
    return v


def _gravar_campos(v):
    return dict(veterinario_id=v["veterinario_id"], data_hora=v["data_hora"], motivo=v["motivo"],
                peso_kg=v["peso_kg"], temperatura_c=v["temperatura_c"], situacao=v["situacao"],
                **{c: v[c] for c in CAMPOS_TEXTO})


def _atualiza_peso_do_animal(conn, v, consulta_id=0):
    """O peso atual do animal acompanha a consulta REALIZADA mais recente que tem peso.

    Registrar ou corrigir uma consulta antiga (data anterior a outra já realizada com peso)
    não pode sobrescrever o peso mais novo.
    """
    if v["situacao"] != "REALIZADA" or not v["peso_kg"]:
        return
    mais_nova = conn.um("SELECT id FROM consulta WHERE animal_id = %s AND situacao = 'REALIZADA' "
                        "AND peso_kg IS NOT NULL AND data_hora > %s AND id <> %s LIMIT 1",
                        (v["animal_id"], v["data_hora"], consulta_id))
    if not mais_nova:
        conn.atualizar("animal", v["animal_id"], peso_atual=v["peso_kg"])


def obter(consulta_id):
    conn = get_db()
    linha = conn.um(SELECT + "WHERE c.id = %s", (consulta_id,))
    if not linha:
        obter_ou_404(conn, "consulta", consulta_id, "Consulta")
    return linha


def criar(dados):
    conn = get_db()
    v = _validar(conn, dados)
    id_ = conn.inserir("consulta", animal_id=v["animal_id"], **_gravar_campos(v))
    _atualiza_peso_do_animal(conn, v, id_)
    conn.commit()
    return obter(id_)


def atualizar(consulta_id, dados):
    conn = get_db()
    atual = obter_ou_404(conn, "consulta", consulta_id, "Consulta")
    if atual["situacao"] == "CANCELADA":
        raise conflito("CONSULTA_CANCELADA", "Consulta cancelada não pode ser alterada.")
    v = _validar(conn, dados, animal_id=atual["animal_id"])
    conn.atualizar("consulta", consulta_id, **_gravar_campos(v))
    _atualiza_peso_do_animal(conn, v, consulta_id)
    conn.commit()
    return obter(consulta_id)


def cancelar(consulta_id):
    conn = get_db()
    atual = obter_ou_404(conn, "consulta", consulta_id, "Consulta")
    if atual["situacao"] == "REALIZADA":
        raise conflito("CONSULTA_REALIZADA", "Consulta realizada faz parte do histórico clínico e não pode ser cancelada.")
    conn.atualizar("consulta", consulta_id, situacao="CANCELADA")
    conn.commit()
    return obter(consulta_id)


def listar(args, animal_id=None):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    animal_id = animal_id or args.get("animal_id")
    if animal_id:
        filtros.append("c.animal_id = %s")
        params.append(animal_id)
    if args.get("situacao"):
        filtros.append("c.situacao = %s")
        params.append(args["situacao"].upper())
    where = ("WHERE " + " AND ".join(filtros) + " ") if filtros else ""
    return conn.consultar(SELECT + where + "ORDER BY c.data_hora DESC, c.id DESC LIMIT %s OFFSET %s",
                          [*params, limite, offset])


def historico_do_animal(animal_id, args):
    obter_ou_404(get_db(), "animal", animal_id, "Animal")
    return listar(args, animal_id=animal_id)
