"""Endereços (de tutores e, se necessário, da clínica)."""
from ..db import get_db
from ..validators import Campos, so_digitos
from ._comum import obter_ou_404


def validar(dados):
    c = Campos(dados)
    c.cep()
    c.texto("logradouro", max_len=150)
    c.texto("numero", max_len=10)
    c.texto("complemento", obrigatorio=False, max_len=80)
    c.texto("bairro", max_len=80)
    c.texto("cidade", max_len=80)
    c.uf()
    ibge = c.texto("codigo_ibge", obrigatorio=False, max_len=7)
    if ibge and (not so_digitos(ibge) == ibge or len(ibge) != 7):
        c.erro("codigo_ibge", "O código IBGE do município tem 7 dígitos.")
    return c.ok()


def inserir(conn, v):
    return conn.inserir("endereco", cep=v["cep"], logradouro=v["logradouro"], numero=v["numero"],
                        complemento=v["complemento"], bairro=v["bairro"], cidade=v["cidade"], uf=v["uf"],
                        codigo_ibge=v["codigo_ibge"])


def alterar(conn, id_, v):
    conn.atualizar("endereco", id_, cep=v["cep"], logradouro=v["logradouro"], numero=v["numero"],
                   complemento=v["complemento"], bairro=v["bairro"], cidade=v["cidade"], uf=v["uf"],
                   codigo_ibge=v["codigo_ibge"])


def criar(dados):
    conn = get_db()
    id_ = inserir(conn, validar(dados))
    conn.commit()
    return obter(id_)


def obter(id_):
    return obter_ou_404(get_db(), "endereco", id_, "Endereço")


def atualizar(id_, dados):
    conn = get_db()
    obter_ou_404(conn, "endereco", id_, "Endereço")
    alterar(conn, id_, validar(dados))
    conn.commit()
    return obter(id_)
