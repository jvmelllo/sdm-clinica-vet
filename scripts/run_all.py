"""Sobe a pilha completa de uma vez: API governamental (5001) + API/Frontend da clínica (5000).

Uso (a partir da raiz do projeto):
  python scripts/run_all.py                       # usa o que estiver no .env / variáveis de ambiente (MySQL)
  python scripts/run_all.py --sqlite --reset      # sem MySQL: cria data/*.db com dados fictícios
  python scripts/run_all.py --viacep-falso        # demonstração offline (ViaCEP simulado na porta 5002)

Ctrl+C encerra os três processos.
"""
import argparse
import os
import subprocess
import sys
import time

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def aguardar(url, nome, limite_s=20):
    fim = time.time() + limite_s
    while time.time() < fim:
        try:
            requests.get(url, timeout=1)
            return True
        except requests.RequestException:
            time.sleep(0.3)
    print(f"[erro] {nome} não respondeu em {limite_s}s ({url})")
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sqlite", action="store_true", help="usa SQLite em vez de MySQL (DB_BACKEND=sqlite)")
    ap.add_argument("--reset", action="store_true", help="recria os bancos e carrega os dados fictícios antes de subir")
    ap.add_argument("--viacep-falso", action="store_true", help="usa o ViaCEP simulado local (porta 5002)")
    args = ap.parse_args()

    env = dict(os.environ)
    if args.sqlite:
        env["DB_BACKEND"] = "sqlite"
    env.setdefault("GOV_URL", "http://127.0.0.1:5001")
    if args.viacep_falso:
        env["VIACEP_URL"] = "http://127.0.0.1:5002/ws"

    if args.reset:
        print("[1/3] recriando bancos e carregando dados fictícios...")
        r = subprocess.run([sys.executable, "scripts/init_db.py", "--reset", "--seed"], cwd=RAIZ, env=env)
        if r.returncode:
            sys.exit("Falha ao preparar o banco (veja a mensagem acima).")

    comandos = [("governo", [sys.executable, "-m", "governo_api"], "http://127.0.0.1:5001/api/governo/health"),
                ("clinica", [sys.executable, "-m", "clinica_api"], "http://127.0.0.1:5000/api/status")]
    if args.viacep_falso:
        comandos.insert(0, ("viacep-falso", [sys.executable, "scripts/viacep_falso.py", "5002"], "http://127.0.0.1:5002/ws/01001000/json/"))

    filhos = []
    try:
        for nome, cmd, sonda in comandos:
            print(f"[subindo] {nome}...")
            filhos.append((nome, subprocess.Popen(cmd, cwd=RAIZ, env=env)))
            if not aguardar(sonda, nome):
                sys.exit(1)
        print("\n  Tudo no ar:\n    Sistema (frontend + API privada): http://localhost:5000\n"
              "    Swagger da clínica:               http://localhost:5000/docs\n"
              "    API governamental simulada:       http://localhost:5001/docs\n"
              "  Ctrl+C para encerrar.\n")
        while True:
            for nome, p in filhos:
                if p.poll() is not None:
                    sys.exit(f"O processo '{nome}' terminou inesperadamente (código {p.returncode}).")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        for _, p in filhos:
            if p.poll() is None:
                p.terminate()
        for _, p in filhos:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
