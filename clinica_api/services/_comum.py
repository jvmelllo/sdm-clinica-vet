"""Funções reutilizadas pelos serviços."""
from ..errors import conflito, nao_encontrado, validacao


def obter_ou_404(conn, tabela, id_, entidade):
    linha = conn.um(f"SELECT * FROM {tabela} WHERE id = %s", (id_,))
    if not linha:
        raise nao_encontrado(entidade, id_)
    return linha


def garantir_unico(conn, tabela, coluna, valor, codigo, mensagem, ignorar_id=None):
    sql = f"SELECT id FROM {tabela} WHERE {coluna} = %s"
    params = [valor]
    if ignorar_id is not None:
        sql += " AND id <> %s"
        params.append(ignorar_id)
    if conn.um(sql, params):
        raise conflito(codigo, mensagem)


def paginacao(args, padrao=100, maximo=500):
    try:
        limite = min(int(args.get("limite", padrao)), maximo)
        offset = max(int(args.get("offset", 0)), 0)
    except ValueError:
        raise validacao({"limite/offset": "Devem ser números inteiros."})
    return max(limite, 1), offset


def em_bool(v):
    return None if v is None else bool(v)
