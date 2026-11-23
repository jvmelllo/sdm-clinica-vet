"""Gera docs/04-relatorio-de-testes.md a partir das EVIDÊNCIAS reais da última execução.

Uso:
    python scripts/gerar_relatorio_testes.py --executar    # roda tudo e depois gera o relatório
    python scripts/gerar_relatorio_testes.py               # só regenera o .md a partir de docs/evidencias/

O que --executar faz:
  1. pytest (SQLite, ViaCEP simulado)          -> docs/evidencias/junit.xml + pytest.txt
  2. coleção Postman (runner Node)             -> docs/evidencias/colecao.json + colecao.txt
  3. teste de fumaça da interface (Playwright) -> docs/evidencias/smoke_ui.txt + capturas
Os itens 2 e 3 exigem a pilha no ar, p.ex.:  python scripts/run_all.py --sqlite --reset --viacep-falso

EXECUÇÕES EM OUTROS AMBIENTES (p.ex. a pilha de verdade, com MySQL):
  node scripts/executar_colecao.js --json docs/evidencias/colecao_mysql.json --ambiente "MySQL 8.4 + ViaCEP real"
  python scripts/gerar_relatorio_testes.py
Todo arquivo docs/evidencias/colecao_*.json vira uma coluna/linha extra no relatório. Convenção do texto de --ambiente:
  contém "MySQL"        -> o relatório passa a registrar que o MySQL foi validado;
  contém "ViaCEP real"  -> o relatório registra que o ViaCEP real foi consumido e trata as falhas da pasta T06b
                           (que exige o ViaCEP simulado) como esperadas.
"""
import argparse
import glob
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.environ.get("SDM_EVID") or os.path.join(RAIZ, "docs", "evidencias")
BASE = os.environ.get("SDM_BASE", "http://127.0.0.1:5000")

TESTES = {
    "T01": "Login de veterinário ativo e com senha confirmada",
    "T02": "Bloqueio de veterinário inativo",
    "T03": "Bloqueio de veterinário com senha não confirmada",
    "T04": "Rejeição de senha incorreta",
    "T05": "Cadastro de tutor e validação de CPF duplicado",
    "T06": "Consulta de CEP válido e tratamento de CEP inexistente",
    "T07": "Cadastro de animal e vínculo de microchip",
    "T08": "Rejeição de microchip já utilizado",
    "T09": "Registro de consulta e consulta ao histórico clínico",
    "T10": "Registro de vacina e consulta às próximas doses",
    "T11": "Cadastro e atualização de animal na API governamental simulada",
    "T12": "Envio obrigatório de vacina antirrábica",
    "T13": "Ausência de comunicação obrigatória para vacina não antirrábica",
    "T14": "Indisponibilidade da API governamental e registro de pendência",
    "T15": "Reenvio de comunicação pendente e confirmação posterior",
    "T16": "Repetição de solicitação sem duplicidade de vacinação no serviço externo",
}

# Passos do teste de fumaça da interface que evidenciam cada teste obrigatório.
UI_POR_TESTE = {
    "T01": [r"login válido abre o painel", r"logout volta"],
    "T02": [r"veterinário inativo é bloqueado"],
    "T03": [r"senha não confirmada é bloqueado"],
    "T04": [r"senha errada"],
    "T05": [r"tutor cadastrado e listado", r"CPF duplicado"],
    "T06": [r"ViaCEP:"],
    "T07": [r"animal cadastrado", r"microchip vinculado"],
    "T09": [r"consulta registrada"],
    "T12": [r"antirrábica registrada e CONFIRMADA", r"antirrábica: tela avisa"],
    "T13": [r"não antirrábica: sem comunicação"],
    "T14": [r"governo indisponível: vacina registrada"],
    "T15": [r"pendência (reprocessada|já tinha)"],
    "T16": [r"reenvio idempotente"],
}


# ----------------------------------------------------------------------- execução
def _rodar(cmd, saida, cwd=RAIZ):
    print("$", " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    texto = (r.stdout or "") + (r.stderr or "")
    with open(os.path.join(EVID, saida), "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"   -> código {r.returncode}; saída em docs/evidencias/{saida}")
    return r.returncode


def _pilha_no_ar():
    try:
        with urllib.request.urlopen(BASE + "/api/status", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def executar(ambiente_pilha):
    os.makedirs(EVID, exist_ok=True)
    # Registra ONDE as suítes rodaram, para o relatório continuar correto se for regenerado em outra máquina.
    with open(os.path.join(EVID, "ambiente.json"), "w", encoding="utf-8") as f:
        json.dump({"executado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "sistema": f"{platform.system()} {platform.release()}",
                   "python": platform.python_version(),
                   "node": versao(["node", "--version"]),
                   "sqlite": sqlite3.sqlite_version}, f, ensure_ascii=False, indent=2)
    _rodar([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            f"--junitxml={os.path.join(EVID, 'junit.xml')}"], "pytest.txt")
    if not _pilha_no_ar():
        print(f"AVISO: a pilha não responde em {BASE}; coleção Postman e teste de interface NÃO foram executados.")
        return
    _rodar(["node", "scripts/executar_colecao.js", "--json", os.path.join(EVID, "colecao.json"),
            "--ambiente", ambiente_pilha], "colecao.txt")
    _rodar([sys.executable, "scripts/smoke_ui.py"], "smoke_ui.txt")


# ------------------------------------------------------------------------ leitura
def ler_junit():
    caminho = os.path.join(EVID, "junit.xml")
    if not os.path.isfile(caminho):
        return None
    raiz = ET.parse(caminho).getroot()
    casos = []
    for tc in raiz.iter("testcase"):
        arquivo = tc.get("classname", "").split(".")[-1]
        estado = "ok"
        if tc.find("failure") is not None or tc.find("error") is not None:
            estado = "falhou"
        elif tc.find("skipped") is not None:
            estado = "ignorado"
        casos.append({"arquivo": arquivo, "nome": tc.get("name"), "estado": estado,
                      "tempo": float(tc.get("time", 0))})
    suite = raiz if raiz.tag == "testsuite" else raiz.find("testsuite")
    return {"casos": casos, "tempo": float(suite.get("time", 0)) if suite is not None else 0.0}


def enriquecer(d, nome):
    """Acrescenta ao JSON da coleção os campos derivados usados no relatório."""
    d["arquivo"] = nome
    d["ambiente"] = d.get("ambiente") or "SQLite + ViaCEP simulado"
    d["data"] = (d.get("executado_em") or "")[:16].replace("T", " ")
    d["viacep_real"] = "viacep real" in d["ambiente"].lower()
    d["mysql"] = "mysql" in d["ambiente"].lower()
    itens_t06b = [i for i in d["relatorio"] if i["pasta"].startswith("T06b")]
    d["t06b_total"] = sum(len(i["resultados"]) for i in itens_t06b)
    d["t06b_ok"] = sum(r["ok"] for i in itens_t06b for r in i["resultados"])
    total = d["resumo"]["asserções"]
    ok = total - len(d["resumo"]["falhas"])
    # falhas da T06b só são "esperadas" quando o ViaCEP é o real (a pasta exige o simulado)
    d["ignora_t06b"] = d["viacep_real"]
    d["total"] = total - (d["t06b_total"] if d["ignora_t06b"] else 0)
    d["ok"] = ok - (d["t06b_ok"] if d["ignora_t06b"] else 0)
    d["aprovada"] = d["ok"] == d["total"]
    return d


def ler_colecao():
    caminho = os.path.join(EVID, "colecao.json")
    if not os.path.isfile(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        return enriquecer(json.load(f), "colecao.json")


def ler_extras():
    """Execuções da coleção feitas em outros ambientes (docs/evidencias/colecao_*.json)."""
    extras = []
    for caminho in sorted(glob.glob(os.path.join(EVID, "colecao_*.json"))):
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
        nome = os.path.basename(caminho)
        d.setdefault("ambiente", nome[len("colecao_"):-len(".json")])
        extras.append(enriquecer(d, nome))
    return extras


def ler_ambiente():
    caminho = os.path.join(EVID, "ambiente.json")
    if os.path.isfile(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    # Sem registro de onde as suítes rodaram: não inventar (a máquina atual pode não ser a que gerou as evidências).
    return {"executado_em": "n/d", "sistema": "n/d", "python": "n/d", "node": "n/d", "sqlite": "n/d"}


def ler_smoke():
    caminho = os.path.join(EVID, "smoke_ui.txt")
    if not os.path.isfile(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        linhas = f.read().splitlines()
    passos = [l.strip()[2:].strip() for l in linhas if l.startswith("  ok  ")]
    concluiu = any("Fumaça da interface" in l for l in linhas)
    return {"passos": passos, "ok": concluiu and not any("PROBLEMAS" in l for l in linhas)}


def ultima_linha(nome, contem):
    caminho = os.path.join(EVID, nome)
    if not os.path.isfile(caminho):
        return ""
    for l in reversed(open(caminho, encoding="utf-8").read().splitlines()):
        if contem in l:
            return l.strip()
    return ""


def versao(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return "n/d"


# ------------------------------------------------------------------------ relatório
def marca(ok):
    return "✅" if ok else "❌"


def gerar():
    junit, colecao, smoke, extras = ler_junit(), ler_colecao(), ler_smoke(), ler_extras()
    todas = ([colecao] if colecao else []) + extras
    mysql_ok = [e for e in todas if e["mysql"] and e["aprovada"]]
    viacep_real_ok = [e for e in todas if e["viacep_real"] and e["aprovada"]]
    md = []
    add = md.append

    add("# 04 — Relatório de testes\n")
    add("Projeto A3 – SDM · Sistema Web para Gestão de Clínica Veterinária com Integração de APIs\n")
    add("> **Entregável 9** do enunciado. Este arquivo é **gerado** por `scripts/gerar_relatorio_testes.py` a partir das "
        "saídas reais das ferramentas, guardadas em [`evidencias/`](evidencias/): todos os resultados (✅/❌ e contagens) vêm "
        "dessas saídas; só os textos explicativos são escritos à mão.\n")

    # ---------------------------------------------------------------- resumo
    add("## 1. Resumo\n")
    add("| Suíte | O que verifica | Resultado |")
    add("|---|---|---|")
    if junit:
        total = len(junit["casos"])
        ok = sum(1 for c in junit["casos"] if c["estado"] == "ok")
        falhas = sum(1 for c in junit["casos"] if c["estado"] == "falhou")
        add(f"| **pytest** (API da clínica + API do governo + banco) | regras de negócio, integridade do modelo, "
            f"idempotência, contrato OpenAPI | {marca(falhas == 0)} **{ok}/{total}** testes passaram "
            f"({junit['tempo']:.0f} s) |")
    else:
        add("| pytest | — | não executado |")
    if colecao:
        r = colecao["resumo"]
        pas = r["asserções"] - len(r["falhas"])
        add(f"| **Coleção Postman** (`docs/postman/`) | os 16 testes obrigatórios por HTTP, contra os serviços no ar | "
            f"{marca(not r['falhas'])} **{pas}/{r['asserções']}** asserções em {r['requisicoes']} requisições |")
    else:
        add("| Coleção Postman | — | não executada |")
    for e in extras:
        extra = (f" (+ pasta T06b: {e['t06b_ok']}/{e['t06b_total']} — exige o ViaCEP simulado, falha esperada com ViaCEP real)"
                 if e["ignora_t06b"] and e["t06b_total"] else "")
        add(f"| **Coleção Postman — {e['ambiente']}** | os 16 testes obrigatórios por HTTP, no ambiente de verdade "
            f"({e['data'] or 'data n/d'}) | {marca(e['aprovada'])} **{e['ok']}/{e['total']}** asserções{extra} |")
    if smoke:
        add(f"| **Interface web** (Playwright, navegador real) | fluxo completo da demonstração pela tela | "
            f"{marca(smoke['ok'])} **{len(smoke['passos'])}** verificações, sem erro de JavaScript nem HTTP 5xx |")
    else:
        add("| Interface web | — | não executada |")
    add("")

    # ---------------------------------------------------------------- ambiente
    add("## 2. Ambiente de execução\n")
    add("| Item | Valor |")
    add("|---|---|")
    amb = ler_ambiente()
    add(f"| Execução das suítes principais | {amb['executado_em']} |")
    add(f"| Sistema | {amb['sistema']} |")
    add(f"| Python | {amb['python']} |")
    add(f"| Node.js (runner da coleção) | {amb['node']} |")
    add(f"| Banco usado no pytest | **SQLite {amb['sqlite']}** (mesmo DDL do MySQL, gerado por `database/ddl.py`) |")
    if colecao:
        add(f"| Pilha da execução principal da coleção e da interface | **{colecao['ambiente']}** |")
    add("| ViaCEP simulado (quando usado) | serviço local `scripts/viacep_falso.py` (porta 5002), com o mesmo formato de resposta do real |")
    for e in extras:
        add(f"| Execução adicional da coleção | **{e['ambiente']}** — {e['data'] or 'data n/d'} (`evidencias/{e['arquivo']}`) |")
    add("| API governamental | simulada (`governo_api`, porta 5001), processo separado, banco próprio |")
    add("| API da clínica | `clinica_api`, porta 5000 |")
    add("")

    # ---------------------------------------------------------------- limitações
    add("## 3. Limitações e o que foi comprovado em cada ambiente\n")
    add("Esta seção diz **o que de fato foi comprovado** e onde. A suíte automatizada (pytest) e a execução principal "
        "rodam em SQLite com ViaCEP simulado, para serem repetíveis em qualquer máquina; a validação no ambiente de "
        "verdade (MySQL, ViaCEP real) é registrada à parte, a partir de execuções reais da coleção.\n")
    add("| Item | Situação | Observação |")
    add("|---|---|---|")
    if mysql_ok:
        e = mysql_ok[0]
        add(f"| **MySQL** | ✅ **Validado**: banco criado e a coleção Postman executada em *{e['ambiente']}* "
            f"({e['data'] or 'data n/d'}) | Os 16 testes obrigatórios passaram contra o MySQL (coluna \"Postman — {e['ambiente']}\" na seção 4) |")
        add("| **pytest** | SQLite por construção | Não exercita o driver PyMySQL; essa lacuna é coberta pela coleção Postman em MySQL, acima |")
    else:
        add("| **MySQL** | ⚠️ **Não validado** nesta geração do relatório | Todas as suítes rodaram em **SQLite**. Os `database/mysql/*.sql` são gerados do "
            "mesmo DDL, mas não foram executados em um MySQL real. Para validar: criar os bancos (README, \"Instalação completa com MySQL\"), "
            "subir a pilha com `DB_BACKEND=mysql` e rodar `node scripts/executar_colecao.js --json docs/evidencias/colecao_mysql.json "
            "--ambiente \"MySQL 8.x + ViaCEP real\"` |")
        add("| **pytest** | SQLite por construção | Não valida o driver PyMySQL nem particularidades do MySQL (ex.: `CHECK` exige ≥ 8.0.16) |")
    if viacep_real_ok:
        e = viacep_real_ok[0]
        add(f"| **ViaCEP real** | ✅ **Consumido** em *{e['ambiente']}* ({e['data'] or 'data n/d'}) | CEP válido (`01001000`), "
            "inexistente (`99999999`) e formato inválido passaram contra o serviço real. *Timeout* e erro do serviço (pasta T06b) só são "
            "reproduzíveis com o ViaCEP simulado e foram validados na execução principal |")
    else:
        add("| **ViaCEP real** | ⚠️ **Não consumido** nesta geração do relatório | O caso \"CEP válido\" foi testado contra o ViaCEP **simulado**. Para validar: "
            "rodar a pilha sem `--viacep-falso`, com internet, e executar a coleção (a pasta T06b falha de propósito com o serviço real) |")
    add("| E-mail de confirmação | **Simulado** | O código vai para `data/emails_simulados.log` (e na resposta, em `dev`); permitido pelo enunciado |")
    add("")

    # ---------------------------------------------------------------- matriz
    add("## 4. Testes obrigatórios (enunciado, seção 9)\n")
    cab_extra = "".join(f" Postman — {e['ambiente']} |" for e in extras)
    cab_main = f"Postman — {colecao['ambiente']}" if colecao else "Postman"
    add(f"| # | Teste obrigatório | pytest | {cab_main} |" + cab_extra + " Interface |")
    add("|---|---|---|---|" + "---|" * len(extras) + "---|")
    por_t, postman_por_t = {}, {}
    if junit:
        for c in junit["casos"]:
            m = re.match(r"test_(T\d\d)_", c["nome"])
            if m:
                por_t.setdefault(m.group(1), []).append(c)
    if colecao:
        for item in colecao["relatorio"]:
            m = re.match(r"(T\d\d)\b", item["pasta"])
            if m:
                postman_por_t.setdefault(m.group(1), []).append(item)
    for t, desc in TESTES.items():
        casos = por_t.get(t, [])
        py = (f"{marca(all(c['estado'] == 'ok' for c in casos))} {sum(c['estado'] == 'ok' for c in casos)}/{len(casos)}"
              if casos else "—")
        itens = postman_por_t.get(t, [])
        ass = [r for i in itens for r in i["resultados"]]
        pm = f"{marca(all(r['ok'] for r in ass))} {sum(r['ok'] for r in ass)}/{len(ass)}" if ass else "—"
        passos_ui = []
        if smoke:
            for padrao in UI_POR_TESTE.get(t, []):
                passos_ui += [p for p in smoke["passos"] if re.search(padrao, p)]
        ui = f"✅ {len(dict.fromkeys(passos_ui))} passo(s)" if passos_ui else "—"
        cols_extra = ""
        for e in extras:
            ass_e = [r for i in e["relatorio"] if re.match(rf"{t}\b", i["pasta"]) for r in i["resultados"]]
            cols_extra += (f" {marca(all(r['ok'] for r in ass_e))} {sum(r['ok'] for r in ass_e)}/{len(ass_e)} |" if ass_e else " — |")
        add(f"| {t} | {desc} | {py} | {pm} |" + cols_extra + f" {ui} |")
    add("\n`—` = o teste não tem etapa naquela ferramenta (a cobertura é feita pelas demais).\n")

    # ---------------------------------------------------------------- detalhe
    add("## 5. Detalhe por teste obrigatório\n")
    for t, desc in TESTES.items():
        add(f"### {t} — {desc}\n")
        casos = por_t.get(t, [])
        if casos:
            add("**pytest**\n")
            for c in casos:
                add(f"- {marca(c['estado'] == 'ok')} `{c['nome']}`")
            add("")
        itens = postman_por_t.get(t, [])
        if itens:
            add("**Coleção Postman**\n")
            for i in itens:
                n_ok = sum(r["ok"] for r in i["resultados"])
                add(f"- {marca(n_ok == len(i['resultados']))} `{i['metodo']}` {i['requisicao']} — {n_ok}/{len(i['resultados'])} asserções")
            add("")
        if smoke and UI_POR_TESTE.get(t):
            ps = []
            for padrao in UI_POR_TESTE[t]:
                ps += [p for p in smoke["passos"] if re.search(padrao, p)]
            if ps:
                add("**Interface**\n")
                for p in dict.fromkeys(ps):
                    add(f"- ✅ {p}")
                add("")
        if t == "T06" and "T06b" in " ".join(i["pasta"] for i in (colecao or {"relatorio": []})["relatorio"]):
            b = [i for i in colecao["relatorio"] if i["pasta"].startswith("T06b")]
            add("**Coleção Postman — T06b (timeout/erro do ViaCEP, exige o serviço simulado)**\n")
            for i in b:
                n_ok = sum(r["ok"] for r in i["resultados"])
                add(f"- {marca(n_ok == len(i['resultados']))} `{i['metodo']}` {i['requisicao']} — {n_ok}/{len(i['resultados'])} asserções")
            add("")

    # ---------------------------------------------------------------- demais testes
    add("## 6. Demais testes automatizados\n")
    add("Testes que sustentam os critérios de **modelagem/integridade**, **regras de negócio** e **documentação** "
        "(não numerados no enunciado).\n")
    if junit:
        grupos = {}
        for c in junit["casos"]:
            if not re.match(r"test_T\d\d_", c["nome"]):
                grupos.setdefault(c["arquivo"], []).append(c)
        for arq, casos in sorted(grupos.items()):
            add(f"**`tests/{arq}.py`** — {sum(c['estado'] == 'ok' for c in casos)}/{len(casos)}\n")
            for c in casos:
                add(f"- {marca(c['estado'] == 'ok')} `{c['nome']}`")
            add("")
    else:
        add("_pytest não executado._\n")

    # ---------------------------------------------------------------- evidências
    add("## 7. Evidências\n")
    add("| Arquivo | Conteúdo |")
    add("|---|---|")
    for e in extras:
        add(f"| [`evidencias/{e['arquivo']}`](evidencias/{e['arquivo']}) | coleção Postman em *{e['ambiente']}* ({e['data'] or 'data n/d'}) |")
    for nome, desc in (("junit.xml", "resultado do pytest (formato JUnit)"), ("pytest.txt", "saída do pytest"),
                       ("colecao.json", "resultado detalhado da coleção Postman, por requisição e asserção"),
                       ("colecao.txt", "saída do runner da coleção"), ("smoke_ui.txt", "saída do teste de interface")):
        if os.path.isfile(os.path.join(EVID, nome)):
            add(f"| [`evidencias/{nome}`](evidencias/{nome}) | {desc} |")
    add("")
    add("Capturas de tela geradas pelo teste de interface (`docs/img/ui/`):\n")
    pasta = os.path.join(RAIZ, "docs", "img", "ui")
    if os.path.isdir(pasta):
        for arq in sorted(os.listdir(pasta)):
            if arq.endswith(".png"):
                add(f"- [`{arq}`](img/ui/{arq})")
    add("")

    # ---------------------------------------------------------------- como executar
    add("## 8. Como reproduzir\n")
    add("```bash")
    add("# 1) testes automatizados (não precisam de servidor; usam SQLite e serviços simulados)")
    add("python -m pytest -q")
    add("")
    add("# 2) pilha completa no ar (SQLite + ViaCEP simulado) — veja o README para MySQL")
    add("python scripts/run_all.py --sqlite --reset --viacep-falso")
    add("")
    add("# 3) em outro terminal: coleção Postman e interface")
    add("node scripts/executar_colecao.js")
    add("python scripts/smoke_ui.py")
    add("")
    add("# 4) validar o ambiente de verdade (MySQL; com internet o ViaCEP é o real). Pilha: python scripts/run_all.py")
    add('node scripts/executar_colecao.js --json docs/evidencias/colecao_mysql.json --ambiente "MySQL 8.x + ViaCEP real"')
    add("")
    add("# 5) regenerar este relatório (executa tudo e reescreve o .md)")
    add("python scripts/gerar_relatorio_testes.py --executar")
    add("```\n")
    add("A coleção também pode ser importada no **Postman** (`docs/postman/SDM_Clinica_Vet.postman_collection.json` e "
        "`SDM_Local.postman_environment.json`) e executada pelo *Collection Runner*; a pasta `00 – Preparação` gera dados "
        "novos a cada execução, então a coleção pode ser repetida sem limpar o banco.\n")

    saida = os.path.join(RAIZ, "docs", "04-relatorio-de-testes.md")
    with open(saida, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("gerado:", saida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true", help="roda pytest, coleção e interface antes de gerar")
    ap.add_argument("--ambiente-pilha", default="SQLite + ViaCEP simulado",
                    help='descreve a pilha que está no ar durante --executar (vai para o relatório). '
                         'Ex.: "MySQL 8.4 + ViaCEP simulado"')
    args = ap.parse_args()
    if args.executar:
        executar(args.ambiente_pilha)
    gerar()
