"""Erros de domínio da API. Toda falha sai no mesmo formato JSON:

    {"erro": {"codigo": "CPF_DUPLICADO", "mensagem": "...", "detalhes": {...}}}
"""


class ApiError(Exception):
    def __init__(self, status, codigo, mensagem, detalhes=None):
        super().__init__(mensagem)
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes

    def to_dict(self):
        corpo = {"codigo": self.codigo, "mensagem": self.mensagem}
        if self.detalhes:
            corpo["detalhes"] = self.detalhes
        return {"erro": corpo}


def nao_encontrado(entidade, id_=None):
    quem = f" (id {id_})" if id_ is not None else ""
    return ApiError(404, "NAO_ENCONTRADO", f"{entidade} não encontrado(a){quem}.")


def validacao(detalhes, mensagem="Dados inválidos."):
    return ApiError(422, "VALIDACAO", mensagem, detalhes)


def conflito(codigo, mensagem, detalhes=None):
    return ApiError(409, codigo, mensagem, detalhes)


def regra(codigo, mensagem, detalhes=None):
    """Violação de regra de negócio (dados válidos, mas operação não permitida)."""
    return ApiError(422, codigo, mensagem, detalhes)
