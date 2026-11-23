from flask import Blueprint

from ..security import login_required
from ..services import enderecos as svc
from ..services import viacep
from ._util import corpo, resposta

bp = Blueprint("enderecos", __name__, url_prefix="/api")


@bp.get("/cep/<cep>")
@login_required
def consultar_cep(cep):
    """Consulta o ViaCEP (API pública). Falhas viram 404/503/504 tratáveis pelo frontend."""
    return resposta(viacep.consultar(cep))


@bp.post("/enderecos")
@login_required
def criar():
    return resposta(svc.criar(corpo()), 201)


@bp.get("/enderecos/<int:id_>")
@login_required
def obter(id_):
    return resposta(svc.obter(id_))


@bp.put("/enderecos/<int:id_>")
@login_required
def atualizar(id_):
    return resposta(svc.atualizar(id_, corpo()))
