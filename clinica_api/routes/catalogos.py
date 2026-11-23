from flask import Blueprint, request

from ..security import login_required
from ..services import catalogos as svc
from ._util import corpo, resposta

bp = Blueprint("catalogos", __name__, url_prefix="/api")


# --- espécies ----------------------------------------------------------------
@bp.get("/especies")
@login_required
def listar_especies():
    return resposta(svc.listar_especies(request.args))


@bp.post("/especies")
@login_required
def criar_especie():
    return resposta(svc.criar_especie(corpo()), 201)


@bp.get("/especies/<int:id_>")
@login_required
def obter_especie(id_):
    return resposta(svc.obter_especie(id_))


@bp.put("/especies/<int:id_>")
@login_required
def atualizar_especie(id_):
    return resposta(svc.atualizar_especie(id_, corpo()))


@bp.delete("/especies/<int:id_>")
@login_required
def inativar_especie(id_):
    return resposta(svc.mudar_situacao_especie(id_, "INATIVA"))


@bp.post("/especies/<int:id_>/reativar")
@login_required
def reativar_especie(id_):
    return resposta(svc.mudar_situacao_especie(id_, "ATIVA"))


# --- raças -------------------------------------------------------------------
@bp.get("/racas")
@login_required
def listar_racas():
    return resposta(svc.listar_racas(request.args))


@bp.post("/racas")
@login_required
def criar_raca():
    return resposta(svc.criar_raca(corpo()), 201)


@bp.get("/racas/<int:id_>")
@login_required
def obter_raca(id_):
    return resposta(svc.obter_raca(id_))


@bp.put("/racas/<int:id_>")
@login_required
def atualizar_raca(id_):
    return resposta(svc.atualizar_raca(id_, corpo()))


@bp.delete("/racas/<int:id_>")
@login_required
def inativar_raca(id_):
    return resposta(svc.mudar_situacao_raca(id_, "INATIVA"))


@bp.post("/racas/<int:id_>/reativar")
@login_required
def reativar_raca(id_):
    return resposta(svc.mudar_situacao_raca(id_, "ATIVA"))
