"""Veterinários e fluxo de autenticação (login, confirmação de senha, logout)."""
import hmac
from datetime import datetime, timedelta

from flask import current_app, g

from .. import security
from ..db import FMT_DATAHORA, agora, get_db
from ..errors import ApiError, conflito, regra, validacao
from ..validators import Campos, so_digitos, validar_senha
from . import email_simulado
from ._comum import em_bool, garantir_unico, obter_ou_404, paginacao


def publico(v):
    """Representação segura: nunca expõe o hash da senha."""
    return {
        "id": v["id"], "nome_completo": v["nome_completo"], "cpf": v["cpf"],
        "crmv_numero": v["crmv_numero"], "crmv_uf": v["crmv_uf"], "email": v["email"],
        "telefone": v["telefone"], "senha_confirmada": em_bool(v["senha_confirmada"]),
        "senha_confirmada_em": v["senha_confirmada_em"], "data_cadastro": v["data_cadastro"],
        "situacao": v["situacao"], "ultimo_acesso_em": v["ultimo_acesso_em"],
    }


# --------------------------------------------------------------------------- CRUD
def _validar(dados, com_senha):
    c = Campos(dados)
    c.texto("nome_completo", max_len=150, min_len=5)
    c.cpf()
    crmv = c.texto("crmv_numero", max_len=10)
    if crmv and not so_digitos(crmv) == crmv:
        c.erro("crmv_numero", "O número do CRMV deve conter apenas dígitos.")
    c.uf("crmv_uf")
    c.email()
    c.telefone()
    if com_senha:
        msg = validar_senha(dados.get("senha"))
        if msg:
            c.erro("senha", msg)
    return c


def _unicos(conn, v, ignorar_id=None):
    garantir_unico(conn, "veterinario", "cpf", v["cpf"], "CPF_DUPLICADO", "Já existe veterinário com este CPF.", ignorar_id)
    garantir_unico(conn, "veterinario", "email", v["email"], "EMAIL_DUPLICADO", "Já existe veterinário com este e-mail.", ignorar_id)
    sql = "SELECT id FROM veterinario WHERE crmv_numero = %s AND crmv_uf = %s"
    params = [v["crmv_numero"], v["crmv_uf"]]
    if ignorar_id is not None:
        sql += " AND id <> %s"
        params.append(ignorar_id)
    if conn.um(sql, params):
        raise conflito("CRMV_DUPLICADO", "Já existe veterinário com este CRMV/UF.")


def criar(dados):
    conn = get_db()
    c = _validar(dados, com_senha=True)
    v = c.ok()
    _unicos(conn, v)
    vet_id = conn.inserir(
        "veterinario", nome_completo=v["nome_completo"], cpf=v["cpf"], crmv_numero=v["crmv_numero"],
        crmv_uf=v["crmv_uf"], email=v["email"], telefone=v["telefone"],
        senha_hash=security.hash_senha(dados["senha"]), senha_confirmada=0, senha_confirmada_em=None,
        data_cadastro=agora(), situacao="ATIVO", ultimo_acesso_em=None)
    codigo = _emitir_codigo(conn, vet_id, v["email"])
    conn.commit()
    resp = publico(obter_ou_404(conn, "veterinario", vet_id, "Veterinário"))
    if current_app.config["SDM"]["EXPOR_CODIGO_NA_RESPOSTA"]:
        resp["codigo_simulado"] = codigo
    return resp


def listar(args):
    conn = get_db()
    limite, offset = paginacao(args)
    filtros, params = [], []
    if args.get("situacao"):
        filtros.append("situacao = %s")
        params.append(args["situacao"].upper())
    if args.get("q"):
        filtros.append("(nome_completo LIKE %s OR email LIKE %s)")
        params += [f"%{args['q']}%"] * 2
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    linhas = conn.consultar(f"SELECT * FROM veterinario {where} ORDER BY nome_completo LIMIT %s OFFSET %s",
                            [*params, limite, offset])
    return [publico(v) for v in linhas]


def obter(vet_id):
    return publico(obter_ou_404(get_db(), "veterinario", vet_id, "Veterinário"))


def atualizar(vet_id, dados):
    conn = get_db()
    obter_ou_404(conn, "veterinario", vet_id, "Veterinário")
    v = _validar(dados, com_senha=False).ok()
    _unicos(conn, v, vet_id)
    conn.atualizar("veterinario", vet_id, nome_completo=v["nome_completo"], cpf=v["cpf"],
                   crmv_numero=v["crmv_numero"], crmv_uf=v["crmv_uf"], email=v["email"], telefone=v["telefone"])
    conn.commit()
    return obter(vet_id)


def mudar_situacao(vet_id, nova):
    conn = get_db()
    obter_ou_404(conn, "veterinario", vet_id, "Veterinário")
    if nova == "INATIVO" and vet_id == g.vet["id"]:
        raise regra("AUTOINATIVACAO", "Você não pode inativar o próprio acesso.")
    conn.atualizar("veterinario", vet_id, situacao=nova)
    if nova == "INATIVO":  # derruba as sessões abertas
        conn.executar("UPDATE sessao_login SET revogada_em = %s WHERE veterinario_id = %s AND revogada_em IS NULL",
                      (agora(), vet_id))
    conn.commit()
    return obter(vet_id)


# --------------------------------------------------------------- confirmação de senha
def _emitir_codigo(conn, vet_id, email):
    """Gera código de 6 dígitos (guardado só como HMAC) e 'envia' por e-mail simulado."""
    agora_s = agora()
    conn.executar("UPDATE codigo_confirmacao SET utilizado_em = %s WHERE veterinario_id = %s AND utilizado_em IS NULL",
                  (agora_s, vet_id))
    cfg = current_app.config["SDM"]
    codigo = security.gerar_codigo()
    expira = datetime.now() + timedelta(minutes=cfg["CODIGO_TTL_MIN"])
    conn.inserir("codigo_confirmacao", veterinario_id=vet_id, codigo_hash=security.hash_codigo(codigo),
                 criado_em=agora_s, expira_em=expira.strftime(FMT_DATAHORA), utilizado_em=None, tentativas=0)
    email_simulado.enviar(email, "Confirme sua senha - Clínica Veterinária",
                          f"Seu código de confirmação é {codigo} (válido por {cfg['CODIGO_TTL_MIN']} min).")
    return codigo


def reenviar_codigo(email):
    """Resposta sempre igual, exista ou não o e-mail (não revela cadastros)."""
    conn = get_db()
    c = Campos({"email": email})
    c.email()
    c.ok()
    vet = conn.um("SELECT * FROM veterinario WHERE email = %s", (c.v["email"],))
    resposta = {"mensagem": "Se o e-mail estiver cadastrado e pendente de confirmação, um novo código foi enviado."}
    if vet and vet["situacao"] == "ATIVO" and not vet["senha_confirmada"]:
        codigo = _emitir_codigo(conn, vet["id"], vet["email"])
        conn.commit()
        if current_app.config["SDM"]["EXPOR_CODIGO_NA_RESPOSTA"]:
            resposta["codigo_simulado"] = codigo
    return resposta


def confirmar_senha(email, codigo):
    conn = get_db()
    c = Campos({"email": email, "codigo": codigo})
    c.email()
    c.texto("codigo", max_len=6, min_len=6)
    c.ok()
    cfg = current_app.config["SDM"]
    invalido = ApiError(400, "CODIGO_INVALIDO", "Código inválido ou expirado.")

    vet = conn.um("SELECT * FROM veterinario WHERE email = %s", (c.v["email"],))
    if not vet:
        raise invalido
    if vet["senha_confirmada"]:
        return {"mensagem": "Senha já confirmada.", "veterinario": publico(vet)}

    linha = conn.um("SELECT * FROM codigo_confirmacao WHERE veterinario_id = %s AND utilizado_em IS NULL "
                    "ORDER BY id DESC LIMIT 1", (vet["id"],))
    if not linha or linha["expira_em"] <= agora():
        raise invalido
    if linha["tentativas"] >= cfg["CODIGO_MAX_TENTATIVAS"]:
        raise ApiError(429, "CODIGO_BLOQUEADO", "Muitas tentativas. Solicite um novo código.")

    if not hmac.compare_digest(linha["codigo_hash"], security.hash_codigo(c.v["codigo"])):
        conn.atualizar("codigo_confirmacao", linha["id"], tentativas=linha["tentativas"] + 1)
        conn.commit()  # a tentativa errada precisa ficar registrada mesmo com o erro
        raise invalido

    agora_s = agora()
    conn.atualizar("codigo_confirmacao", linha["id"], utilizado_em=agora_s)
    conn.atualizar("veterinario", vet["id"], senha_confirmada=1, senha_confirmada_em=agora_s)
    conn.commit()
    return {"mensagem": "Senha confirmada com sucesso. Você já pode fazer login.",
            "veterinario": publico(obter_ou_404(conn, "veterinario", vet["id"], "Veterinário"))}


# ----------------------------------------------------------------------- login/logout
def login(email, senha):
    conn = get_db()
    c = Campos({"email": email})
    c.email()
    if c.erros or not isinstance(senha, str) or not senha:
        raise validacao({"email": "Informe e-mail e senha válidos."}, "E-mail e senha são obrigatórios.")
    invalidas = ApiError(401, "CREDENCIAIS_INVALIDAS", "E-mail ou senha inválidos.")

    vet = conn.um("SELECT * FROM veterinario WHERE email = %s", (c.v["email"],))
    if not vet:
        security.gasta_tempo_de_hash(senha)
        raise invalidas
    if not security.senha_confere(vet["senha_hash"], senha):
        raise invalidas
    # Só quem sabe a senha descobre o motivo do bloqueio.
    if vet["situacao"] != "ATIVO":
        raise ApiError(403, "VETERINARIO_INATIVO", "Veterinário inativo: acesso bloqueado.")
    if not vet["senha_confirmada"]:
        raise ApiError(403, "SENHA_NAO_CONFIRMADA",
                       "Senha ainda não confirmada. Use o código enviado ao seu e-mail.")

    conn.atualizar("veterinario", vet["id"], ultimo_acesso_em=agora())
    token, expira_em = security.emitir_token(conn, vet["id"])
    conn.commit()
    return {"token": token, "tipo": "Bearer", "expira_em": expira_em,
            "veterinario": publico(obter_ou_404(conn, "veterinario", vet["id"], "Veterinário"))}


def logout():
    conn = get_db()
    conn.executar("UPDATE sessao_login SET revogada_em = %s WHERE jti = %s AND revogada_em IS NULL",
                  (agora(), g.jti))
    conn.commit()
    return {"mensagem": "Sessão encerrada."}
