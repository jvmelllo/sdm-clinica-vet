from flask import Blueprint

from ..security import login_required
from ..services import vacinas as svc
from ._util import corpo, resposta

bp = Blueprint("vacinas", __name__, url_prefix="/api/vacinas")


@bp.post("")
@login_required
def criar():
    return resposta(svc.criar(corpo()), 201)


@bp.get("/<int:id_>")
@login_required
def obter(id_):
    return resposta(svc.obter_publico(id_))


@bp.post("/<int:id_>/aplicar")
@login_required
def aplicar(id_):
    return resposta(svc.aplicar(id_, corpo()))


@bp.delete("/<int:id_>")
@login_required
def cancelar(id_):
    return resposta(svc.cancelar(id_))


@bp.get("/<int:id_>/comunicacao-governo")
@login_required
def comunicacao(id_):
    return resposta(svc.comunicacao(id_))
