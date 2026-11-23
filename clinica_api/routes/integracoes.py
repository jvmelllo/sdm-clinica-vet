from flask import Blueprint, request

from ..db import get_db
from ..security import login_required
from ..services import integracao
from ._util import resposta

bp = Blueprint("integracoes", __name__, url_prefix="/api/integracoes")


@bp.get("")
@login_required
def listar():
    return resposta(integracao.listar(get_db(), request.args))


@bp.get("/<int:id_>")
@login_required
def obter(id_):
    return resposta(integracao.obter(get_db(), id_, com_payload=True))


@bp.post("/<int:id_>/reenviar")
@login_required
def reenviar(id_):
    """Reenvio manual. Operação já CONFIRMADA só é reenviada com ?forcar=true (demonstra a idempotência)."""
    forcar = request.args.get("forcar", "").lower() in ("1", "true", "sim")
    return resposta(integracao.enviar(get_db(), id_, automatico=False, forcar=forcar))


@bp.post("/reprocessar-pendentes")
@login_required
def reprocessar():
    return resposta(integracao.reprocessar(get_db(), automatico=False))
