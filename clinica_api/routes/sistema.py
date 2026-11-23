"""Rotas de apoio: saúde, resumo do painel, documentação Swagger e arquivos do frontend."""
import os

from flask import Blueprint, Response, abort, send_from_directory

from ..config import RAIZ
from ..db import get_db, hoje
from ..errors import ApiError
from ..security import login_required
from ..services import governo_client
from ._util import resposta

bp = Blueprint("sistema", __name__)
FRONTEND = os.path.join(RAIZ, "frontend")
OPENAPI = os.path.join(RAIZ, "docs", "openapi", "clinica.yaml")

_SWAGGER = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>API da Clínica - Swagger</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"></head>
<body><div id="ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url:"/openapi.yaml",dom_id:"#ui",persistAuthorization:true});</script>
</body></html>"""


@bp.get("/api/status")
def status():
    """Público: usado pelo frontend e pelo roteiro de demonstração."""
    banco = True
    try:
        get_db().escalar("SELECT 1")
    except Exception:  # noqa: BLE001 - qualquer falha de banco = indisponível
        banco = False
    return resposta({"api": "ok", "banco": "ok" if banco else "indisponivel",
                     "governo": "ok" if governo_client.verificar_saude() else "indisponivel"})


@bp.get("/api/resumo")
@login_required
def resumo():
    conn = get_db()
    h = hoje()
    por_situacao = {r["situacao"]: r["total"] for r in conn.consultar(
        "SELECT situacao, COUNT(*) AS total FROM integracao_governo GROUP BY situacao")}
    atrasadas = conn.escalar(
        "SELECT COUNT(*) FROM vacina v WHERE v.situacao = 'APLICADA' AND v.data_proxima_dose IS NOT NULL "
        "AND v.data_proxima_dose < %s AND NOT EXISTS (SELECT 1 FROM vacina v2 WHERE v2.animal_id = v.animal_id "
        "AND v2.nome_vacina = v.nome_vacina AND v2.situacao = 'APLICADA' AND v2.data_aplicacao > v.data_aplicacao)", (h,))
    return resposta({
        "tutores_ativos": conn.escalar("SELECT COUNT(*) FROM tutor WHERE situacao = 'ATIVO'"),
        "animais_ativos": conn.escalar("SELECT COUNT(*) FROM animal WHERE situacao = 'ATIVO'"),
        "consultas_hoje": conn.escalar("SELECT COUNT(*) FROM consulta WHERE data_hora >= %s AND data_hora <= %s "
                                       "AND situacao <> 'CANCELADA'", (h + " 00:00:00", h + " 23:59:59")),
        "consultas_agendadas": conn.escalar("SELECT COUNT(*) FROM consulta WHERE situacao = 'AGENDADA'"),
        "vacinas_com_reforco_atrasado": atrasadas,
        "integracoes": {s: por_situacao.get(s, 0) for s in ("PENDENTE", "ENVIADA", "CONFIRMADA", "FALHA")},
        "governo_disponivel": governo_client.verificar_saude(),
    })


@bp.get("/openapi.yaml")
def openapi():
    if not os.path.isfile(OPENAPI):
        abort(404)
    with open(OPENAPI, encoding="utf-8") as f:
        return Response(f.read(), mimetype="application/yaml")


@bp.get("/docs")
def docs():
    return Response(_SWAGGER, mimetype="text/html")


@bp.get("/", defaults={"caminho": "index.html"})
@bp.get("/<path:caminho>")
def frontend(caminho):
    """Serve o frontend estático (HTML/CSS/JS). Caminhos /api/* inexistentes dão 404 JSON."""
    if caminho.startswith("api/"):
        raise ApiError(404, "ROTA_NAO_ENCONTRADA", "Endpoint inexistente.")
    destino = os.path.join(FRONTEND, caminho)
    if not os.path.isfile(destino):
        caminho = "index.html"
    return send_from_directory(FRONTEND, caminho, max_age=0)
