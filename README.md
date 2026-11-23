# Clínica Veterinária — Sistema Web com Integração de APIs

**A3 – Projeto Integrador · Sistemas Distribuídos e Mobile (SDM)** · entrega/apresentação: **26/11/2026**

Sistema web para gestão de uma clínica veterinária (tutores, animais, veterinários, consultas e vacinas), composto por:

| Componente | Tecnologia | Porta |
|---|---|---|
| **Frontend** (interface web responsiva) | HTML + CSS + JavaScript puro | servido em `5000` |
| **API privada da clínica** (regras de negócio, autenticação, persistência) | Python + Flask | `5000` |
| **API governamental simulada** (registro de animais por microchip e de vacinações antirrábicas) | Python + Flask, banco próprio | `5001` |
| **Banco de dados** | MySQL 8 (`sdm_clinica` e `sdm_governo`) | `3306` |
| **API pública** consumida | [ViaCEP](https://viacep.com.br/) | — |

Regra central: **toda vacina antirrábica aplicada é comunicada ao governo**; se ele estiver fora do ar, a vacina continua
registrada, a comunicação fica **PENDENTE** e é regularizada depois **sem duplicar** o registro externo.

> ⚠️ A "API governamental" é uma **simulação acadêmica**. Não é integração oficial com nenhum sistema governamental real.
> Todos os dados são **fictícios**.

---

## Início rápido (sem instalar MySQL)

Requisitos: **Python 3.10+**.

```bash
# 1) ambiente virtual e dependências
python -m venv .venv
source .venv/bin/activate            # Windows (PowerShell):  .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) sobe tudo (cria data/*.db com dados fictícios) — ViaCEP real, precisa de internet
python scripts/run_all.py --sqlite --reset
#    sem internet? use o ViaCEP simulado local:
python scripts/run_all.py --sqlite --reset --viacep-falso
```

Abra **<http://localhost:5000>** e entre com `ana.souza@clinicavet.example` / `Senha@123`.
`Ctrl+C` encerra tudo.

| Endereço | O que é |
|---|---|
| <http://localhost:5000> | Sistema (frontend + API privada) |
| <http://localhost:5000/docs> | Swagger da API da clínica |
| <http://localhost:5001/docs> | Swagger da API governamental simulada |

*(O Swagger UI carrega seus arquivos de um CDN: precisa de internet. Os arquivos `docs/openapi/*.yaml` abrem em
qualquer editor OpenAPI ou podem ser importados no Postman.)*

### Contas de demonstração (senha de todas: `Senha@123`)

| E-mail | Situação | Serve para |
|---|---|---|
| `ana.souza@clinicavet.example` | ativa, senha confirmada | uso normal |
| `bruno.lima@clinicavet.example` | **inativo** | provar o bloqueio |
| `carla.mendes@clinicavet.example` | **senha não confirmada** | provar o bloqueio e o fluxo de confirmação |

O e-mail de confirmação é **simulado**: o código aparece na tela (modo `dev`) e é gravado em `data/emails_simulados.log`.

---

## Instalação completa com MySQL

### 1. Pré-requisitos

* Python 3.10+ · MySQL **8.0.16 ou superior** (versões anteriores ignoram as restrições `CHECK`).
* Conferir a versão: `mysql -u root -p -e "SELECT VERSION();"`

### 2. Dependências

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configuração

Copie `.env.example` para `.env` e ajuste pelo menos `MYSQL_USER` e `MYSQL_PASSWORD` (mantenha `DB_BACKEND=mysql`).
Os comentários do `.env` devem ficar em linhas próprias. Lista completa das variáveis: [`.env.example`](.env.example).

### 4. Criação e inicialização dos bancos (escolha **uma** opção)

**Opção A — scripts SQL** (entregável 6; funcionam em qualquer cliente MySQL):

```bash
mysql -u root -p < database/mysql/01_clinica_schema.sql    # cria sdm_clinica + tabelas
mysql -u root -p < database/mysql/02_clinica_seed.sql      # dados fictícios (opcional, recomendado)
mysql -u root -p < database/mysql/03_governo_schema.sql    # cria sdm_governo + tabelas
```

**Opção B — Python** (cria os bancos, as tabelas e os dados fictícios):

```bash
python scripts/init_db.py --reset --seed
```

Verificação: `mysql -u root -p -e "USE sdm_clinica; SHOW TABLES;"` deve listar 12 tabelas
(e `sdm_governo`, 3 tabelas). Os arquivos `.sql` são **gerados** de `database/ddl.py` por
`python scripts/gerar_sql.py`; não os edite à mão.

### 5. Executar

```bash
python scripts/run_all.py                 # usa o .env (MySQL); adicione --reset para recriar os dados
```

ou cada serviço em seu terminal:

```bash
python -m governo_api                     # API governamental simulada  -> :5001
python -m clinica_api                     # API privada + frontend       -> :5000
```

Conferir: <http://localhost:5000/api/status> deve mostrar API, banco e governo como `ok`.

---

## Testes

```bash
pip install -r requirements-dev.txt

# 1) automatizados (pytest) — não precisam de servidor nem de MySQL (usam SQLite e serviços simulados)
python -m pytest

# 2) com a pilha no ar (python scripts/run_all.py --sqlite --reset --viacep-falso):
node scripts/executar_colecao.js          # coleção Postman: os 16 testes obrigatórios por HTTP (Node 18+)
python -m playwright install chromium     # uma vez
python scripts/smoke_ui.py                # fluxo completo na interface, em navegador real

# 3) regenerar o relatório (executa tudo e reescreve docs/04-relatorio-de-testes.md)
python scripts/gerar_relatorio_testes.py --executar
```

A coleção também pode ser importada no **Postman** (`docs/postman/SDM_Clinica_Vet.postman_collection.json` +
`SDM_Local.postman_environment.json`) e executada no *Collection Runner*.

> **Importante — o que foi e o que não foi validado:** os testes automatizados rodam em **SQLite**, e o CEP "válido" é
> testado contra um **ViaCEP simulado**. Antes da entrega, repita a **coleção Postman** e o **teste de interface**
> contra a pilha com **MySQL** (e, com internet, sem `--viacep-falso`) para validar o ambiente final.
> Detalhes e justificativa em [`docs/04-relatorio-de-testes.md`](docs/04-relatorio-de-testes.md), seção 3.

---

## Documentação (entregáveis)

| # | Entregável | Arquivo |
|---|---|---|
| 1 | Requisitos e arquitetura | [`docs/01-requisitos-e-arquitetura.md`](docs/01-requisitos-e-arquitetura.md) |
| 2 | ER e modelo relacional | [`docs/02-modelo-de-dados.md`](docs/02-modelo-de-dados.md) · imagens `docs/er-*.png` |
| 3 | Código do frontend | [`frontend/`](frontend/) |
| 4 | Código da API privada | [`clinica_api/`](clinica_api/) |
| 5 | Código da API governamental simulada | [`governo_api/`](governo_api/) |
| 6 | Criação/inicialização dos bancos | [`database/mysql/`](database/mysql/) · `scripts/init_db.py` |
| 7 | Documentação dos endpoints | [`docs/03-endpoints.md`](docs/03-endpoints.md) · [`docs/openapi/`](docs/openapi/) · `/docs` |
| 8 | Coleção de testes | [`docs/postman/`](docs/postman/) · [`tests/`](tests/) |
| 9 | Relatório de testes | [`docs/04-relatorio-de-testes.md`](docs/04-relatorio-de-testes.md) |
| 10 | Instalação e execução | este arquivo |
| 11 | Apresentação do fluxo completo | [`docs/05-roteiro-de-apresentacao.md`](docs/05-roteiro-de-apresentacao.md) |

---

## Estrutura do projeto

```
clinica_api/            API privada (Flask): routes/ · services/ (regras de negócio) · validators · security · db
governo_api/            API governamental SIMULADA (Flask), com banco próprio
frontend/               HTML, CSS e JS puro (módulos ES): api.js · ui.js · validacao.js · views/
database/               ddl.py (fonte única do DDL) · seed.py (dados fictícios) · mysql/*.sql (gerados)
docs/                   documentação, diagramas, OpenAPI, coleção Postman, evidências e capturas de tela
scripts/                run_all.py · init_db.py · geradores (sql, openapi, postman, relatório) · smoke_ui.py · viacep_falso.py
tests/                  pytest: cenários T01–T16, modelo de dados, regras adicionais, contrato OpenAPI
data/                   (gerado) bancos SQLite e log do e-mail simulado
```

## Regenerar artefatos derivados

| Quando você mudar… | Rode |
|---|---|
| `database/ddl.py` ou `seed.py` | `python scripts/gerar_sql.py` e `python scripts/gerar_doc_modelo.py` |
| rotas/endpoints | atualizar `scripts/gerar_openapi.py` e rodar `python scripts/gerar_openapi.py` (o teste `test_openapi.py` falha se esquecer) |
| cenários da coleção | `python scripts/gerar_postman.py` |
| qualquer código | `python scripts/gerar_relatorio_testes.py --executar` |

## Problemas comuns

| Sintoma | Causa provável / solução |
|---|---|
| `Access denied` / erro de autenticação no MySQL | Ajuste `MYSQL_USER`/`MYSQL_PASSWORD` no `.env`; garanta que `cryptography` está instalado (`pip install -r requirements.txt`) |
| Restrições `CHECK` não são aplicadas | MySQL anterior a 8.0.16 — atualize |
| `Address already in use` | Já há algo nas portas 5000/5001/5002; encerre o processo anterior ou mude `CLINICA_PORT`/`GOVERNO_PORT` |
| O CEP demora/dá erro | Sem internet ou ViaCEP fora do ar: use `--viacep-falso` ou preencha o endereço manualmente (a interface permite) |
| Valores do `.env` ignorados | Comentário na mesma linha do valor, ou variável já definida no terminal (tem prioridade) |
| Governo "indisponível" depois de testar falhas | Painel → **Normal**, ou reinicie a API do governo (o modo de falha vive em memória) |
| Comunicação virou **FALHA** | Esgotou as tentativas **automáticas**; o **Reenviar** manual sempre funciona |
