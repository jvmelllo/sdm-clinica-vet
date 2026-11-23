# 04 — Relatório de testes

Projeto A3 – SDM · Sistema Web para Gestão de Clínica Veterinária com Integração de APIs

> **Entregável 9** do enunciado. Este arquivo é **gerado** por `scripts/gerar_relatorio_testes.py` a partir das saídas reais das ferramentas, guardadas em [`evidencias/`](evidencias/): todos os resultados (✅/❌ e contagens) vêm dessas saídas; só os textos explicativos são escritos à mão.

## 1. Resumo

| Suíte | O que verifica | Resultado |
|---|---|---|
| **pytest** (API da clínica + API do governo + banco) | regras de negócio, integridade do modelo, idempotência, contrato OpenAPI | ✅ **66/66** testes passaram (36 s) |
| **Coleção Postman** (`docs/postman/`) | os 16 testes obrigatórios por HTTP, contra os serviços no ar | ✅ **128/128** asserções em 49 requisições |
| **Interface web** (Playwright, navegador real) | fluxo completo da demonstração pela tela | ✅ **26** verificações, sem erro de JavaScript nem HTTP 5xx |

## 2. Ambiente de execução

| Item | Valor |
|---|---|
| Execução das suítes principais | 2026-11-11 10:38 |
| Sistema | Linux 6.18.44-fc-v378 |
| Python | 3.13.18 |
| Node.js (runner da coleção) | v22.23.4 |
| Banco usado no pytest | **SQLite 3.53.1** (mesmo DDL do MySQL, gerado por `database/ddl.py`) |
| Pilha da execução principal da coleção e da interface | **SQLite + ViaCEP simulado** |
| ViaCEP simulado (quando usado) | serviço local `scripts/viacep_falso.py` (porta 5002), com o mesmo formato de resposta do real |
| API governamental | simulada (`governo_api`, porta 5001), processo separado, banco próprio |
| API da clínica | `clinica_api`, porta 5000 |

## 3. Limitações e o que foi comprovado em cada ambiente

Esta seção diz **o que de fato foi comprovado** e onde. A suíte automatizada (pytest) e a execução principal rodam em SQLite com ViaCEP simulado, para serem repetíveis em qualquer máquina; a validação no ambiente de verdade (MySQL, ViaCEP real) é registrada à parte, a partir de execuções reais da coleção.

| Item | Situação | Observação |
|---|---|---|
| **MySQL** | ⚠️ **Não validado** nesta geração do relatório | Todas as suítes rodaram em **SQLite**. Os `database/mysql/*.sql` são gerados do mesmo DDL, mas não foram executados em um MySQL real. Para validar: criar os bancos (README, "Instalação completa com MySQL"), subir a pilha com `DB_BACKEND=mysql` e rodar `node scripts/executar_colecao.js --json docs/evidencias/colecao_mysql.json --ambiente "MySQL 8.x + ViaCEP real"` |
| **pytest** | SQLite por construção | Não valida o driver PyMySQL nem particularidades do MySQL (ex.: `CHECK` exige ≥ 8.0.16) |
| **ViaCEP real** | ⚠️ **Não consumido** nesta geração do relatório | O caso "CEP válido" foi testado contra o ViaCEP **simulado**. Para validar: rodar a pilha sem `--viacep-falso`, com internet, e executar a coleção (a pasta T06b falha de propósito com o serviço real) |
| E-mail de confirmação | **Simulado** | O código vai para `data/emails_simulados.log` (e na resposta, em `dev`); permitido pelo enunciado |

## 4. Testes obrigatórios (enunciado, seção 9)

| # | Teste obrigatório | pytest | Postman — SQLite + ViaCEP simulado | Interface |
|---|---|---|---|---|
| T01 | Login de veterinário ativo e com senha confirmada | ✅ 3/3 | ✅ 8/8 | ✅ 2 passo(s) |
| T02 | Bloqueio de veterinário inativo | ✅ 2/2 | ✅ 2/2 | ✅ 1 passo(s) |
| T03 | Bloqueio de veterinário com senha não confirmada | ✅ 3/3 | ✅ 2/2 | ✅ 1 passo(s) |
| T04 | Rejeição de senha incorreta | ✅ 2/2 | ✅ 4/4 | ✅ 1 passo(s) |
| T05 | Cadastro de tutor e validação de CPF duplicado | ✅ 3/3 | ✅ 9/9 | ✅ 2 passo(s) |
| T06 | Consulta de CEP válido e tratamento de CEP inexistente | ✅ 4/4 | ✅ 8/8 | ✅ 3 passo(s) |
| T07 | Cadastro de animal e vínculo de microchip | ✅ 2/2 | ✅ 7/7 | ✅ 2 passo(s) |
| T08 | Rejeição de microchip já utilizado | ✅ 3/3 | ✅ 5/5 | — |
| T09 | Registro de consulta e consulta ao histórico clínico | ✅ 2/2 | ✅ 7/7 | ✅ 1 passo(s) |
| T10 | Registro de vacina e consulta às próximas doses | ✅ 2/2 | ✅ 8/8 | — |
| T11 | Cadastro e atualização de animal na API governamental simulada | ✅ 3/3 | ✅ 16/16 | — |
| T12 | Envio obrigatório de vacina antirrábica | ✅ 4/4 | ✅ 11/11 | ✅ 2 passo(s) |
| T13 | Ausência de comunicação obrigatória para vacina não antirrábica | ✅ 2/2 | ✅ 5/5 | ✅ 1 passo(s) |
| T14 | Indisponibilidade da API governamental e registro de pendência | ✅ 2/2 | ✅ 11/11 | ✅ 1 passo(s) |
| T15 | Reenvio de comunicação pendente e confirmação posterior | ✅ 4/4 | ✅ 7/7 | ✅ 1 passo(s) |
| T16 | Repetição de solicitação sem duplicidade de vacinação no serviço externo | ✅ 3/3 | ✅ 8/8 | ✅ 1 passo(s) |

`—` = o teste não tem etapa naquela ferramenta (a cobertura é feita pelas demais).

## 5. Detalhe por teste obrigatório

### T01 — Login de veterinário ativo e com senha confirmada

**pytest**

- ✅ `test_T01_login_de_veterinario_ativo_com_senha_confirmada`
- ✅ `test_T01_logout_encerra_a_sessao`
- ✅ `test_T01_endpoints_privados_exigem_autenticacao`

**Coleção Postman**

- ✅ `POST` Login válido — 4/4 asserções
- ✅ `GET` Dados do usuário autenticado — 2/2 asserções
- ✅ `GET` Rota privada sem token é recusada — 2/2 asserções

**Interface**

- ✅ login válido abre o painel
- ✅ logout volta para o login

### T02 — Bloqueio de veterinário inativo

**pytest**

- ✅ `test_T02_bloqueio_de_veterinario_inativo`
- ✅ `test_T02_inativar_derruba_o_acesso_imediatamente`

**Coleção Postman**

- ✅ `POST` Login de veterinário inativo — 2/2 asserções

**Interface**

- ✅ veterinário inativo é bloqueado

### T03 — Bloqueio de veterinário com senha não confirmada

**pytest**

- ✅ `test_T03_bloqueio_de_veterinario_com_senha_nao_confirmada`
- ✅ `test_T03_confirmacao_por_codigo_libera_o_acesso`
- ✅ `test_T03_codigo_bloqueado_apos_muitas_tentativas`

**Coleção Postman**

- ✅ `POST` Login sem senha confirmada — 2/2 asserções

**Interface**

- ✅ veterinário com senha não confirmada é bloqueado e levado à confirmação por código

### T04 — Rejeição de senha incorreta

**pytest**

- ✅ `test_T04_rejeicao_de_senha_incorreta`
- ✅ `test_T04_senha_nunca_e_guardada_em_texto_puro`

**Coleção Postman**

- ✅ `POST` Senha incorreta — 2/2 asserções
- ✅ `POST` E-mail inexistente (mesma resposta) — 2/2 asserções

**Interface**

- ✅ login com senha errada mostra erro genérico

### T05 — Cadastro de tutor e validação de CPF duplicado

**pytest**

- ✅ `test_T05_cadastro_de_tutor_e_cpf_duplicado`
- ✅ `test_T05_cpf_invalido_e_demais_validacoes`
- ✅ `test_T05_alterar_e_inativar_tutor`

**Coleção Postman**

- ✅ `POST` Cadastrar tutor — 4/4 asserções
- ✅ `POST` Cadastrar o MESMO CPF novamente (409) — 2/2 asserções
- ✅ `POST` CPF inválido (422) — 3/3 asserções

**Interface**

- ✅ tutor cadastrado e listado
- ✅ CPF duplicado é recusado

### T06 — Consulta de CEP válido e tratamento de CEP inexistente

**pytest**

- ✅ `test_T06_consulta_de_cep_valido`
- ✅ `test_T06_cep_inexistente_e_formato_invalido`
- ✅ `test_T06_timeout_e_indisponibilidade_do_servico_de_cep`
- ✅ `test_T06_endereco_pode_ser_completado_manualmente_quando_o_cep_falha`

**Coleção Postman**

- ✅ `GET` CEP válido — 4/4 asserções
- ✅ `GET` CEP inexistente (404) — 2/2 asserções
- ✅ `GET` CEP com formato inválido (422) — 2/2 asserções

**Interface**

- ✅ ViaCEP: CEP inexistente tratado com mensagem
- ✅ ViaCEP: timeout tratado, com opção de preencher manualmente
- ✅ ViaCEP: CEP válido preenche o endereço

**Coleção Postman — T06b (timeout/erro do ViaCEP, exige o serviço simulado)**

- ✅ `GET` CEP que demora (timeout → 504) — 2/2 asserções
- ✅ `GET` CEP com serviço em erro (503) — 2/2 asserções

### T07 — Cadastro de animal e vínculo de microchip

**pytest**

- ✅ `test_T07_cadastro_de_animal_e_vinculo_de_microchip`
- ✅ `test_T07_animal_exige_tutor_e_raca_compativel_com_a_especie`

**Coleção Postman**

- ✅ `POST` Cadastrar animal — 3/3 asserções
- ✅ `POST` Vincular microchip (15 dígitos) — 4/4 asserções

**Interface**

- ✅ animal cadastrado (sem microchip) e ficha aberta automaticamente
- ✅ microchip vinculado e cadastro CONFIRMADO no governo

### T08 — Rejeição de microchip já utilizado

**pytest**

- ✅ `test_T08_rejeicao_de_microchip_ja_utilizado`
- ✅ `test_T08_formato_do_microchip_e_um_chip_por_animal`
- ✅ `test_T08_substituicao_de_microchip_preserva_o_historico`

**Coleção Postman**

- ✅ `POST` Cadastrar segundo animal — 1/1 asserções
- ✅ `POST` Vincular o MESMO microchip ao segundo animal (409) — 2/2 asserções
- ✅ `POST` Microchip com formato inválido (422) — 2/2 asserções

### T09 — Registro de consulta e consulta ao histórico clínico

**pytest**

- ✅ `test_T09_registro_de_consulta_e_historico_clinico`
- ✅ `test_T09_regras_da_consulta`

**Coleção Postman**

- ✅ `POST` Registrar consulta realizada — 2/2 asserções
- ✅ `GET` Histórico de consultas do animal — 3/3 asserções
- ✅ `GET` Peso do animal foi atualizado pela consulta — 2/2 asserções

**Interface**

- ✅ consulta registrada e exibida no histórico

### T10 — Registro de vacina e consulta às próximas doses

**pytest**

- ✅ `test_T10_registro_de_vacina_e_proximas_doses`
- ✅ `test_T10_validacoes_da_vacina`

**Coleção Postman**

- ✅ `POST` Registrar vacina polivalente (com reforço) — 3/3 asserções
- ✅ `GET` Histórico de vacinação — 2/2 asserções
- ✅ `GET` Próximas doses — 3/3 asserções

### T11 — Cadastro e atualização de animal na API governamental simulada

**pytest**

- ✅ `test_T11_cadastro_e_atualizacao_de_animal_na_api_governamental`
- ✅ `test_T11_atualizar_animal_na_clinica_comunica_a_atualizacao_ao_governo`
- ✅ `test_T11_governo_valida_dados_e_exige_chave_de_api`

**Coleção Postman**

- ✅ `POST` Cadastrar animal no governo — 3/3 asserções
- ✅ `GET` Consultar animal por microchip — 3/3 asserções
- ✅ `PUT` Atualizar o cadastro — 2/2 asserções
- ✅ `GET` Conferir a atualização — 2/2 asserções
- ✅ `POST` Erro de validação simulado (CPF inválido → 422) — 4/4 asserções
- ✅ `GET` Sem chave de API (401) — 2/2 asserções

### T12 — Envio obrigatório de vacina antirrábica

**pytest**

- ✅ `test_T12_envio_obrigatorio_de_vacina_antirrabica`
- ✅ `test_T12_comunicacao_independe_de_o_animal_estar_cadastrado_no_governo`
- ✅ `test_T12_antirrabica_e_identificada_pela_classificacao_e_nao_pelo_nome`
- ✅ `test_T12_antirrabica_exige_microchip_vinculado`

**Coleção Postman**

- ✅ `POST` Registrar vacina antirrábica — 4/4 asserções
- ✅ `GET` Governo recebeu a vacinação — 4/4 asserções
- ✅ `GET` Estado da comunicação (local x governo) — 3/3 asserções

**Interface**

- ✅ antirrábica registrada e CONFIRMADA pelo governo (com protocolo)
- ✅ antirrábica: tela avisa que falta microchip

### T13 — Ausência de comunicação obrigatória para vacina não antirrábica

**pytest**

- ✅ `test_T13_nao_ha_comunicacao_obrigatoria_para_vacina_nao_antirrabica`
- ✅ `test_T13_antirrabica_agendada_so_comunica_quando_aplicada`

**Coleção Postman**

- ✅ `GET` Comunicação da vacina polivalente — 3/3 asserções
- ✅ `GET` Governo continua com apenas 1 vacinação do animal — 2/2 asserções

**Interface**

- ✅ vacina não antirrábica: sem comunicação ao governo

### T14 — Indisponibilidade da API governamental e registro de pendência

**pytest**

- ✅ `test_T14_indisponibilidade_do_governo_registra_pendencia`
- ✅ `test_T14_governo_totalmente_fora_do_ar_conexao_recusada`

**Coleção Postman**

- ✅ `PUT` Derrubar o governo simulado (503) — 2/2 asserções
- ✅ `POST` Registrar antirrábica com o governo fora do ar — 4/4 asserções
- ✅ `GET` A vacina continua registrada na clínica — 3/3 asserções
- ✅ `GET` Governo realmente está fora do ar (503) — 2/2 asserções

**Interface**

- ✅ governo indisponível: vacina registrada localmente e comunicação PENDENTE

### T15 — Reenvio de comunicação pendente e confirmação posterior

**pytest**

- ✅ `test_T15_reenvio_manual_de_pendencia_e_confirmacao_posterior`
- ✅ `test_T15_reprocessamento_em_lote_das_pendencias`
- ✅ `test_T15_reenvio_automatico_respeita_limite_e_depois_o_manual_regulariza`
- ✅ `test_T15_reenvio_automatico_confirma_quando_o_governo_volta`

**Coleção Postman**

- ✅ `PUT` Governo volta ao normal — 2/2 asserções
- ✅ `POST` Reenviar a pendência — 3/3 asserções
- ✅ `GET` Comunicação agora CONFIRMADA — 2/2 asserções

**Interface**

- ✅ pendência reprocessada e CONFIRMADA após o governo voltar

### T16 — Repetição de solicitação sem duplicidade de vacinação no serviço externo

**pytest**

- ✅ `test_T16_repeticao_de_solicitacao_nao_duplica_registro_no_governo`
- ✅ `test_T16_timeout_com_operacao_ja_processada_nao_duplica_no_reenvio`
- ✅ `test_T16_governo_aplica_idempotencia_por_chave_e_por_chave_natural`

**Coleção Postman**

- ✅ `POST` Reenvio forçado de operação já confirmada — 4/4 asserções
- ✅ `GET` Governo tem apenas 2 vacinações (A e B), sem duplicata — 2/2 asserções
- ✅ `POST` Mesma Idempotency-Key direto no governo devolve a mesma resposta — 2/2 asserções

**Interface**

- ✅ reenvio idempotente: o governo devolve o mesmo protocolo, sem duplicar

## 6. Demais testes automatizados

Testes que sustentam os critérios de **modelagem/integridade**, **regras de negócio** e **documentação** (não numerados no enunciado).

**`tests/test_modelo_dados.py`** — 7/7

- ✅ `test_raca_precisa_pertencer_a_especie_do_animal`
- ✅ `test_unicidade_de_cpf_email_e_crmv`
- ✅ `test_animal_sempre_tem_tutor_e_dados_minimos`
- ✅ `test_microchip_unico_e_um_vigente_por_animal`
- ✅ `test_classificacao_antirrabica_e_estruturada_no_banco`
- ✅ `test_vacina_aplicada_exige_lote_e_integracao_e_unica_por_vacina`
- ✅ `test_ddl_do_mysql_e_gerado_a_partir_da_mesma_fonte`

**`tests/test_openapi.py`** — 8/8

- ✅ `test_clinica_openapi_cobre_exatamente_as_rotas_do_flask`
- ✅ `test_governo_openapi_cobre_exatamente_as_rotas_do_flask`
- ✅ `test_todos_os_refs_resolvem[SPEC_CLINICA]`
- ✅ `test_todos_os_refs_resolvem[SPEC_GOV]`
- ✅ `test_arquivos_yaml_estao_atualizados[SPEC_CLINICA-clinica.yaml]`
- ✅ `test_arquivos_yaml_estao_atualizados[SPEC_GOV-governo.yaml]`
- ✅ `test_toda_operacao_tem_resposta_de_sucesso_e_resumo`
- ✅ `test_swagger_e_arquivo_openapi_sao_servidos`

**`tests/test_regras_adicionais.py`** — 7/7

- ✅ `test_catalogo_de_especies_e_racas`
- ✅ `test_cadastro_de_veterinario_valida_e_nao_expoe_hash`
- ✅ `test_painel_resumo`
- ✅ `test_erros_sempre_em_json_padronizado`
- ✅ `test_sincronizacao_manual_do_animal`
- ✅ `test_frontend_e_estaticos_sao_servidos_pela_api`
- ✅ `test_atendimento_da_consulta_agendada_e_peso_atual`

## 7. Evidências

| Arquivo | Conteúdo |
|---|---|
| [`evidencias/junit.xml`](evidencias/junit.xml) | resultado do pytest (formato JUnit) |
| [`evidencias/pytest.txt`](evidencias/pytest.txt) | saída do pytest |
| [`evidencias/colecao.json`](evidencias/colecao.json) | resultado detalhado da coleção Postman, por requisição e asserção |
| [`evidencias/colecao.txt`](evidencias/colecao.txt) | saída do runner da coleção |
| [`evidencias/smoke_ui.txt`](evidencias/smoke_ui.txt) | saída do teste de interface |

Capturas de tela geradas pelo teste de interface (`docs/img/ui/`):

- [`01-login.png`](img/ui/01-login.png)
- [`01b-confirmar-senha.png`](img/ui/01b-confirmar-senha.png)
- [`02-painel.png`](img/ui/02-painel.png)
- [`03-tutor-viacep.png`](img/ui/03-tutor-viacep.png)
- [`04-animal-microchip.png`](img/ui/04-animal-microchip.png)
- [`05-vacina-confirmada.png`](img/ui/05-vacina-confirmada.png)
- [`06-vacina-pendente.png`](img/ui/06-vacina-pendente.png)
- [`07-vacinas-historico.png`](img/ui/07-vacinas-historico.png)
- [`08-integracoes.png`](img/ui/08-integracoes.png)
- [`09-catalogos.png`](img/ui/09-catalogos.png)
- [`10-veterinarios.png`](img/ui/10-veterinarios.png)
- [`11-tutores.png`](img/ui/11-tutores.png)
- [`12-animal-governo.png`](img/ui/12-animal-governo.png)
- [`13-animal-consultas.png`](img/ui/13-animal-consultas.png)
- [`14-movel-vacinas.png`](img/ui/14-movel-vacinas.png)
- [`15-consulta-atendida.png`](img/ui/15-consulta-atendida.png)
- [`16-movel-consultas.png`](img/ui/16-movel-consultas.png)

## 8. Como reproduzir

```bash
# 1) testes automatizados (não precisam de servidor; usam SQLite e serviços simulados)
python -m pytest -q

# 2) pilha completa no ar (SQLite + ViaCEP simulado) — veja o README para MySQL
python scripts/run_all.py --sqlite --reset --viacep-falso

# 3) em outro terminal: coleção Postman e interface
node scripts/executar_colecao.js
python scripts/smoke_ui.py

# 4) validar o ambiente de verdade (MySQL; com internet o ViaCEP é o real). Pilha: python scripts/run_all.py
node scripts/executar_colecao.js --json docs/evidencias/colecao_mysql.json --ambiente "MySQL 8.x + ViaCEP real"

# 5) regenerar este relatório (executa tudo e reescreve o .md)
python scripts/gerar_relatorio_testes.py --executar
```

A coleção também pode ser importada no **Postman** (`docs/postman/SDM_Clinica_Vet.postman_collection.json` e `SDM_Local.postman_environment.json`) e executada pelo *Collection Runner*; a pasta `00 – Preparação` gera dados novos a cada execução, então a coleção pode ser repetida sem limpar o banco.
