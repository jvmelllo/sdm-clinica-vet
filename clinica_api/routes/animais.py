from flask import Blueprint, request

from ..security import login_required
from ..services import animais as svc
from ..services import consultas, vacinas
from ._util import corpo, resposta

bp = Blueprint("animais", __name__, url_prefix="/api/animais")


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


# --- microchip RFID ------------------------------------------------------------
@bp.post("/<int:id_>/microchip")
@login_required
def vincular_microchip(id_):
    return resposta(svc.vincular_microchip(id_, corpo()), 201)


@bp.get("/<int:id_>/microchips")
@login_required
def historico_microchips(id_):
    return resposta(svc.historico_microchips(id_))


# --- integração governamental -----------------------------------------------------
@bp.get("/<int:id_>/integracao-governo")
@login_required
def integracao_governo(id_):
    return resposta(svc.integracao_governo(id_))


@bp.post("/<int:id_>/sincronizar")
@login_required
def sincronizar(id_):
    return resposta(svc.sincronizar(id_))


# --- históricos -------------------------------------------------------------------
@bp.get("/<int:id_>/consultas")
@login_required
def historico_consultas(id_):
    return resposta(consultas.historico_do_animal(id_, request.args))


@bp.get("/<int:id_>/vacinas")
@login_required
def historico_vacinas(id_):
    return resposta(vacinas.historico_do_animal(id_, request.args))


@bp.get("/<int:id_>/vacinas/proximas-doses")
@login_required
def proximas_doses(id_):
    return resposta(vacinas.proximas_doses(id_))
