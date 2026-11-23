"""Cadastro de tutores (incluir, consultar, alterar e inativar)."""
from ..db import agora, get_db
from ..errors import conflito, validacao
from ..validators import Campos, so_digitos
from . import enderecos
from ._comum import garantir_unico, obter_ou_404, paginacao


def _com_endereco(conn, t):
    t = dict(t)
    t["endereco"] = conn.um("SELECT * FROM endereco WHERE id = %s", (t["endereco_id"],))
    return t


def _validar(dados):
    c = Campos(dados)
    c.texto("nome_completo", max_len=150, min_len=5)
    c.cpf()
    c.data("data_nascimento", futura=False)
    c.email()
    c.telefone()
    base = c.ok()
    return base


def _endereco_da_requisicao(conn, dados, atual_id=None):
    """Aceita 'endereco' (objeto) ou 'endereco_id' (existente)."""
    if isinstance(dados.get("endereco"), dict):
        return ("objeto", enderecos.validar(dados["endereco"]))
    if dados.get("endereco_id") not in (None, ""):
        try:
            eid = int(dados["endereco_id"])
        except (TypeError, ValueError):
            raise validacao({"endereco_id": "Deve ser um número inteiro."})
        obter_ou_404(conn, "endereco", eid, "Endereço")
        return ("id", eid)
    if atual_id is not None:
        return ("manter", atual_id)
    raise validacao({"endereco": "Informe o endereço do tutor (objeto 'endereco' ou 'endereco_id')."})


def criar(dados):
    conn = get_db()
    v = _validar(dados)
    tipo, end = _endereco_da_requisicao(conn, dados)
    garantir_unico(conn, "tutor", "cpf", v["cpf"], "CPF_DUPLICADO", "Já existe um tutor cadastrado com este CPF.")
    endereco_id = enderecos.inserir(conn, end) if tipo == "objeto" else end
    tutor_id = conn.inserir("tutor", nome_completo=v["nome_completo"], cpf=v["cpf"],
                            data_nascimento=v["data_nascimento"], email=v["email"], telefone=v["telefone"],
                            endereco_id=endereco_id, data_cadastro=agora(), situacao="ATIVO")
    conn.commit()
    return obter(tutor_id)


def obter(tutor_id):
    conn = get_db()
    return _com_endereco(conn, obter_ou_404(conn, "tutor", tutor_id, "Tutor"))


def listar(args):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    if args.get("situacao"):
        filtros.append("t.situacao = %s")
        params.append(args["situacao"].upper())
    if args.get("q"):
        q = args["q"].strip()
        filtros.append("(t.nome_completo LIKE %s OR t.cpf LIKE %s OR t.email LIKE %s)")
        params += [f"%{q}%", f"%{so_digitos(q) or q}%", f"%{q}%"]
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    return conn.consultar(
        "SELECT t.*, e.cidade, e.uf, "
        "(SELECT COUNT(*) FROM animal a WHERE a.tutor_id = t.id AND a.situacao = 'ATIVO') AS total_animais "
        f"FROM tutor t JOIN endereco e ON e.id = t.endereco_id {where} "
        "ORDER BY t.nome_completo LIMIT %s OFFSET %s", [*params, limite, offset])


def atualizar(tutor_id, dados):
    conn = get_db()
    atual = obter_ou_404(conn, "tutor", tutor_id, "Tutor")
    v = _validar(dados)
    tipo, end = _endereco_da_requisicao(conn, dados, atual["endereco_id"])
    garantir_unico(conn, "tutor", "cpf", v["cpf"], "CPF_DUPLICADO", "Já existe um tutor cadastrado com este CPF.", tutor_id)
    endereco_id = atual["endereco_id"]
    if tipo == "objeto":
        enderecos.alterar(conn, endereco_id, end)
    elif tipo == "id":
        endereco_id = end
    conn.atualizar("tutor", tutor_id, nome_completo=v["nome_completo"], cpf=v["cpf"],
                   data_nascimento=v["data_nascimento"], email=v["email"], telefone=v["telefone"],
                   endereco_id=endereco_id)
    conn.commit()
    return obter(tutor_id)


def mudar_situacao(tutor_id, nova):
    conn = get_db()
    obter_ou_404(conn, "tutor", tutor_id, "Tutor")
    if nova == "INATIVO":
        ativos = conn.escalar("SELECT COUNT(*) FROM animal WHERE tutor_id = %s AND situacao = 'ATIVO'", (tutor_id,))
        if ativos:
            raise conflito("TUTOR_COM_ANIMAIS_ATIVOS",
                           f"O tutor possui {ativos} animal(is) ativo(s). Inative-os ou transfira a tutoria antes.")
    conn.atualizar("tutor", tutor_id, situacao=nova)
    conn.commit()
    return obter(tutor_id)
