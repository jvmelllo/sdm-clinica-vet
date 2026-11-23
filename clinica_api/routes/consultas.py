from flask import Blueprint, request

from ..security import login_required
from ..services import consultas as svc
from ._util import corpo, resposta

bp = Blueprint("consultas", __name__, url_prefix="/api/consultas")


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
def cancelar(id_):
    return resposta(svc.cancelar(id_))
