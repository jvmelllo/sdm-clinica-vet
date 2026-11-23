from flask import Blueprint, request

from ..security import login_required
from ..services import veterinarios as svc
from ._util import corpo, resposta

bp = Blueprint("veterinarios", __name__, url_prefix="/api/veterinarios")


@bp.get("")
@login_required
def listar():
    return resposta(svc.listar(request.args))


@bp.post("")
@login_required
def criar():
    return resposta(svc.criar(corpo()), 201)


@bp.get("/<int:id_>")
@login_required
def obter(id_):
    return resposta(svc.obter(id_))


@bp.put("/<int:id_>")
@login_required
def atualizar(id_):
    return resposta(svc.atualizar(id_, corpo()))


@bp.delete("/<int:id_>")
@login_required
def inativar(id_):
    return resposta(svc.mudar_situacao(id_, "INATIVO"))


@bp.post("/<int:id_>/reativar")
@login_required
def reativar(id_):
    return resposta(svc.mudar_situacao(id_, "ATIVO"))
