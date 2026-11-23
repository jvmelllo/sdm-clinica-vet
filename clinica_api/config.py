"""Configuração da API privada da clínica. Tudo vem de variáveis de ambiente
(ou do arquivo .env na raiz do projeto), com padrões seguros para desenvolvimento."""
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def carregar_env(caminho=None):
    """Carrega KEY=VALUE do .env sem sobrescrever variáveis já definidas."""
    caminho = caminho or os.path.join(RAIZ, ".env")
    if not os.path.isfile(caminho):
        return
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def _bool(valor):
    return str(valor).strip().lower() in ("1", "true", "sim", "yes", "on")


def config_do_ambiente():
    carregar_env()
    e = os.environ.get
    return {
        "APP_ENV": e("APP_ENV", "dev"),
        # --- banco ---------------------------------------------------------
        "DB_BACKEND": e("DB_BACKEND", "mysql"),           # mysql | sqlite
        "MYSQL_HOST": e("MYSQL_HOST", "127.0.0.1"),
        "MYSQL_PORT": int(e("MYSQL_PORT", "3306")),
        "MYSQL_USER": e("MYSQL_USER", "root"),
        "MYSQL_PASSWORD": e("MYSQL_PASSWORD", ""),
        "DB_NAME": e("CLINICA_DB_NAME", "sdm_clinica"),
        "SQLITE_PATH": e("CLINICA_SQLITE_PATH", os.path.join(RAIZ, "data", "clinica.db")),
        # --- segurança -----------------------------------------------------
        "SECRET_KEY": e("CLINICA_SECRET_KEY", "dev-secret-troque-em-producao-0123456789"),
        "TOKEN_TTL_MIN": int(e("TOKEN_TTL_MIN", "120")),
        "CODIGO_TTL_MIN": int(e("CODIGO_TTL_MIN", "15")),
        "CODIGO_MAX_TENTATIVAS": int(e("CODIGO_MAX_TENTATIVAS", "5")),
        # Simula o envio do e-mail: grava em arquivo e (em dev) devolve o código na resposta.
        "EMAIL_SIMULADO_ARQUIVO": e("EMAIL_SIMULADO_ARQUIVO", os.path.join(RAIZ, "data", "emails_simulados.log")),
        "EXPOR_CODIGO_NA_RESPOSTA": _bool(e("EXPOR_CODIGO_NA_RESPOSTA", "1" if e("APP_ENV", "dev") == "dev" else "0")),
        # --- API pública (ViaCEP) -------------------------------------------
        "VIACEP_URL": e("VIACEP_URL", "https://viacep.com.br/ws"),
        "VIACEP_TIMEOUT_S": float(e("VIACEP_TIMEOUT_S", "3")),
        # --- API governamental simulada ---------------------------------------
        "GOV_URL": e("GOV_URL", "http://127.0.0.1:5001"),
        "GOV_API_KEY": e("GOV_API_KEY", "chave-demo-governo"),
        "GOV_TIMEOUT_S": float(e("GOV_TIMEOUT_S", "3")),
        "GOV_MAX_TENTATIVAS": int(e("GOV_MAX_TENTATIVAS", "5")),
        "AUTO_RETRY": _bool(e("AUTO_RETRY", "1")),
        "DEMO_SIMULACAO": _bool(e("DEMO_SIMULACAO", "1" if e("APP_ENV", "dev") == "dev" else "0")),
        "AUTO_RETRY_INTERVALO_S": float(e("AUTO_RETRY_INTERVALO_S", "30")),
        # --- web -------------------------------------------------------------
        "CORS_ORIGINS": e("CORS_ORIGINS", ""),
        "PORT": int(e("CLINICA_PORT", "5000")),
    }
