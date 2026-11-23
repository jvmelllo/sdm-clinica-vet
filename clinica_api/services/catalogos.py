"""Catálogos de espécies e raças."""
from ..db import get_db
from ..errors import conflito, regra
from ..validators import Campos
from ._comum import garantir_unico, obter_ou_404, paginacao


# ------------------------------------------------------------------------ espécies
def _especie_dados(dados):
    c = Campos(dados)
    c.texto("nome", max_len=60)
    c.texto("descricao", obrigatorio=False, max_len=255)
    return c.ok()


def listar_especies(args):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    if args.get("situacao"):
        filtros.append("situacao = %s")
        params.append(args["situacao"].upper())
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return conn.consultar(f"SELECT * FROM especie {where} ORDER BY nome LIMIT %s OFFSET %s", [*params, limite, offset])


def obter_especie(id_):
    return obter_ou_404(get_db(), "especie", id_, "Espécie")


def criar_especie(dados):
    conn = get_db()
    v = _especie_dados(dados)
    garantir_unico(conn, "especie", "nome", v["nome"], "ESPECIE_DUPLICADA", "Já existe uma espécie com este nome.")
    id_ = conn.inserir("especie", nome=v["nome"], descricao=v["descricao"], situacao="ATIVA")
    conn.commit()
    return obter_especie(id_)


def atualizar_especie(id_, dados):
    conn = get_db()
    obter_ou_404(conn, "especie", id_, "Espécie")
    v = _especie_dados(dados)
    garantir_unico(conn, "especie", "nome", v["nome"], "ESPECIE_DUPLICADA", "Já existe uma espécie com este nome.", id_)
    conn.atualizar("especie", id_, nome=v["nome"], descricao=v["descricao"])
    conn.commit()
    return obter_especie(id_)


def mudar_situacao_especie(id_, nova):
    conn = get_db()
    obter_ou_404(conn, "especie", id_, "Espécie")
    if nova == "INATIVA":
        em_uso = conn.escalar("SELECT COUNT(*) FROM animal WHERE especie_id = %s AND situacao = 'ATIVO'", (id_,))
        if em_uso:
            raise conflito("ESPECIE_EM_USO", f"Existem {em_uso} animal(is) ativo(s) desta espécie.")
        conn.executar("UPDATE raca SET situacao = 'INATIVA' WHERE especie_id = %s", (id_,))
    conn.atualizar("especie", id_, situacao=nova)
    conn.commit()
    return obter_especie(id_)


# --------------------------------------------------------------------------- raças
def _raca_dados(conn, dados):
    c = Campos(dados)
    c.texto("nome", max_len=80)
    c.texto("descricao", obrigatorio=False, max_len=255)
    esp = c.inteiro("especie_id", minimo=1)
    v = c.ok()
    especie = obter_ou_404(conn, "especie", esp, "Espécie")
    if especie["situacao"] != "ATIVA":
        raise regra("ESPECIE_INATIVA", "A espécie informada está inativa.")
    return v


def _raca_com_especie(conn, id_):
    r = conn.um("SELECT r.*, e.nome AS especie_nome FROM raca r JOIN especie e ON e.id = r.especie_id "
                "WHERE r.id = %s", (id_,))
    if not r:
        obter_ou_404(conn, "raca", id_, "Raça")
    return r


def listar_racas(args):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    if args.get("especie_id"):
        filtros.append("r.especie_id = %s")
        params.append(args["especie_id"])
    if args.get("situacao"):
        filtros.append("r.situacao = %s")
        params.append(args["situacao"].upper())
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return conn.consultar(
        f"SELECT r.*, e.nome AS especie_nome FROM raca r JOIN especie e ON e.id = r.especie_id {where} "
        "ORDER BY e.nome, r.nome LIMIT %s OFFSET %s", [*params, limite, offset])


def obter_raca(id_):
    return _raca_com_especie(get_db(), id_)


def _unica_na_especie(conn, nome, especie_id, ignorar=None):
    sql, params = "SELECT id FROM raca WHERE especie_id = %s AND nome = %s", [especie_id, nome]
    if ignorar is not None:
        sql += " AND id <> %s"
        params.append(ignorar)
    if conn.um(sql, params):
        raise conflito("RACA_DUPLICADA", "Já existe uma raça com este nome nesta espécie.")


def criar_raca(dados):
    conn = get_db()
    v = _raca_dados(conn, dados)
    _unica_na_especie(conn, v["nome"], v["especie_id"])
    id_ = conn.inserir("raca", nome=v["nome"], descricao=v["descricao"], especie_id=v["especie_id"], situacao="ATIVA")
    conn.commit()
    return _raca_com_especie(conn, id_)


def atualizar_raca(id_, dados):
    conn = get_db()
    atual = obter_ou_404(conn, "raca", id_, "Raça")
    v = _raca_dados(conn, dados)
    if v["especie_id"] != atual["especie_id"]:
        usada = conn.escalar("SELECT COUNT(*) FROM animal WHERE raca_id = %s", (id_,))
        if usada:
            raise conflito("RACA_EM_USO", "Há animais usando esta raça; não é possível mudar a espécie dela.")
    _unica_na_especie(conn, v["nome"], v["especie_id"], id_)
    conn.atualizar("raca", id_, nome=v["nome"], descricao=v["descricao"], especie_id=v["especie_id"])
    conn.commit()
    return _raca_com_especie(conn, id_)


def mudar_situacao_raca(id_, nova):
    conn = get_db()
    r = obter_ou_404(conn, "raca", id_, "Raça")
    if nova == "ATIVA":
        esp = obter_ou_404(conn, "especie", r["especie_id"], "Espécie")
        if esp["situacao"] != "ATIVA":
            raise regra("ESPECIE_INATIVA", "Reative a espécie antes de reativar a raça.")
    conn.atualizar("raca", id_, situacao=nova)
    conn.commit()
    return _raca_com_especie(conn, id_)
