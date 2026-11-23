"""Segurança: hash de senha, código de confirmação, token JWT com sessão revogável
e o decorator que protege os endpoints privados."""
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import FMT_DATAHORA, agora, get_db
from .errors import ApiError


# --- senha -------------------------------------------------------------------
def hash_senha(senha):
    """scrypt com salt aleatório (padrão do Werkzeug). Nunca guardamos a senha em texto puro."""
    return generate_password_hash(senha)


def senha_confere(hash_guardado, senha):
    return check_password_hash(hash_guardado, senha)


# Hash fictício usado quando o e-mail não existe: mantém o tempo de resposta
# parecido e evita revelar quais e-mails estão cadastrados.
_HASH_FALSO = generate_password_hash("senha-falsa-para-igualar-tempo")


def gasta_tempo_de_hash(senha):
    check_password_hash(_HASH_FALSO, senha)


# --- código de confirmação (enviado por "e-mail") ----------------------------
def gerar_codigo():
    return f"{secrets.randbelow(10 ** 6):06d}"


def hash_codigo(codigo):
    chave = current_app.config["SDM"]["SECRET_KEY"].encode()
    return hmac.new(chave, codigo.encode(), hashlib.sha256).hexdigest()


# --- token --------------------------------------------------------------------
def emitir_token(conn, vet_id):
    cfg = current_app.config["SDM"]
    emitido = datetime.now()
    expira = emitido + timedelta(minutes=cfg["TOKEN_TTL_MIN"])
    jti = uuid.uuid4().hex
    conn.inserir("sessao_login", jti=jti, veterinario_id=vet_id,
                 criada_em=emitido.strftime(FMT_DATAHORA), expira_em=expira.strftime(FMT_DATAHORA))
    token = jwt.encode({"sub": str(vet_id), "jti": jti, "iat": int(emitido.timestamp()),
                        "exp": int(expira.timestamp())}, cfg["SECRET_KEY"], algorithm="HS256")
    return token, expira.strftime(FMT_DATAHORA)


def _token_da_requisicao():
    cab = request.headers.get("Authorization", "")
    if not cab.lower().startswith("bearer "):
        raise ApiError(401, "NAO_AUTENTICADO", "Autenticação necessária. Envie o cabeçalho Authorization: Bearer <token>.")
    return cab[7:].strip()


def login_required(funcao):
    """Exige token válido, sessão não revogada e veterinário ATIVO com senha confirmada.

    O estado do veterinário é reconsultado a cada requisição: inativar um profissional
    derruba o acesso dele imediatamente, mesmo com token ainda dentro da validade.
    """
    @wraps(funcao)
    def protegido(*args, **kwargs):
        token = _token_da_requisicao()
        try:
            dados = jwt.decode(token, current_app.config["SDM"]["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ApiError(401, "TOKEN_EXPIRADO", "Sessão expirada. Faça login novamente.")
        except jwt.InvalidTokenError:
            raise ApiError(401, "TOKEN_INVALIDO", "Token inválido.")

        conn = get_db()
        sessao = conn.um("SELECT * FROM sessao_login WHERE jti = %s", (dados.get("jti"),))
        if not sessao or sessao["revogada_em"] is not None or sessao["expira_em"] <= agora():
            raise ApiError(401, "SESSAO_ENCERRADA", "Sessão encerrada. Faça login novamente.")

        vet = conn.um("SELECT * FROM veterinario WHERE id = %s", (int(dados["sub"]),))
        if not vet:
            raise ApiError(401, "TOKEN_INVALIDO", "Token inválido.")
        if vet["situacao"] != "ATIVO":
            raise ApiError(403, "VETERINARIO_INATIVO", "Veterinário inativo: acesso bloqueado.")
        if not vet["senha_confirmada"]:
            raise ApiError(403, "SENHA_NAO_CONFIRMADA", "Senha ainda não confirmada: acesso bloqueado.")

        g.vet = vet
        g.jti = dados["jti"]
        return funcao(*args, **kwargs)
    return protegido
