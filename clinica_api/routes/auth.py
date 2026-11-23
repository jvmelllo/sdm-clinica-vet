"""Autenticação: login, logout, confirmação de senha."""
from flask import Blueprint, g

from ..security import login_required
from ..services import veterinarios
from ._util import corpo, resposta

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    d = corpo()
    return resposta(veterinarios.login(d.get("email"), d.get("senha")))


@bp.post("/logout")
@login_required
def logout():
    return resposta(veterinarios.logout())


@bp.get("/me")
@login_required
def me():
    return resposta(veterinarios.publico(g.vet))


@bp.post("/confirmar-senha")
def confirmar_senha():
    d = corpo()
    return resposta(veterinarios.confirmar_senha(d.get("email"), d.get("codigo")))


@bp.post("/reenviar-codigo")
def reenviar_codigo():
    return resposta(veterinarios.reenviar_codigo(corpo().get("email")), 202)
