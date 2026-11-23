# 3. Documentação dos endpoints

Gerado automaticamente por `scripts/gerar_openapi.py` a partir da mesma especificação OpenAPI usada pelo Swagger. O teste `tests/test_openapi.py` garante que **todo caminho do Flask está documentado e vice-versa**.

* Swagger da clínica: <http://localhost:5000/docs> (arquivo: `docs/openapi/clinica.yaml`)
* Swagger do governo simulado: <http://localhost:5001/docs> (arquivo: `docs/openapi/governo.yaml`)
* Erros: sempre `{"erro": {"codigo", "mensagem", "detalhes"}}`. Exclusão é lógica. Listas aceitam `limite`/`offset`.

## Endpoints

### API privada da clínica (porta 5000)

**Sistema**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/status` | não | Saúde da API, do banco e do governo | 200 | — |
| `GET` | `/api/resumo` | sim | Indicadores do painel | 200 | 401 |

**Autenticação**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `POST` | `/api/auth/login` | não | Login do veterinário | 200 | 400, 401, 403, 422 |
| `POST` | `/api/auth/logout` | sim | Encerra (revoga) a sessão atual | 200 | 401 |
| `GET` | `/api/auth/me` | sim | Dados do veterinário autenticado | 200 | 401 |
| `POST` | `/api/auth/confirmar-senha` | não | Confirma a senha com o código de 6 dígitos | 200 | 400, 422, 429 |
| `POST` | `/api/auth/reenviar-codigo` | não | Reenvia o código de confirmação (e-mail simulado) | 202 | 400, 422 |

**Veterinários**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/veterinarios` | sim | Listar veterinário | 200 | 401 |
| `POST` | `/api/veterinarios` | sim | Cadastrar veterinário | 201 | 400, 401, 409, 422 |
| `GET` | `/api/veterinarios/{id}` | sim | Consultar veterinário | 200 | 401, 404 |
| `PUT` | `/api/veterinarios/{id}` | sim | Alterar veterinário | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/veterinarios/{id}` | sim | Inativar veterinário (exclusão lógica) | 200 | 401, 404, 409 |
| `POST` | `/api/veterinarios/{id}/reativar` | sim | Reativar veterinário | 200 | 401, 404, 409, 422 |

**Endereços e CEP**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/cep/{cep}` | sim | Consulta o ViaCEP | 200 | 401, 404, 422, 502, 503, 504 |
| `POST` | `/api/enderecos` | sim | Cadastrar endereço | 201 | 400, 401, 422 |
| `GET` | `/api/enderecos/{id}` | sim | Consultar endereço | 200 | 401, 404 |
| `PUT` | `/api/enderecos/{id}` | sim | Alterar endereço | 200 | 400, 401, 404, 422 |

**Tutores**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/tutores` | sim | Listar tutor | 200 | 401 |
| `POST` | `/api/tutores` | sim | Cadastrar tutor | 201 | 400, 401, 409, 422 |
| `GET` | `/api/tutores/{id}` | sim | Consultar tutor | 200 | 401, 404 |
| `PUT` | `/api/tutores/{id}` | sim | Alterar tutor | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/tutores/{id}` | sim | Inativar tutor (exclusão lógica) | 200 | 401, 404, 409 |
| `POST` | `/api/tutores/{id}/reativar` | sim | Reativar tutor | 200 | 401, 404, 409, 422 |

**Espécies e raças**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/especies` | sim | Listar espécie | 200 | 401 |
| `POST` | `/api/especies` | sim | Cadastrar espécie | 201 | 400, 401, 409, 422 |
| `GET` | `/api/especies/{id}` | sim | Consultar espécie | 200 | 401, 404 |
| `PUT` | `/api/especies/{id}` | sim | Alterar espécie | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/especies/{id}` | sim | Inativar espécie (exclusão lógica) | 200 | 401, 404, 409 |
| `POST` | `/api/especies/{id}/reativar` | sim | Reativar espécie | 200 | 401, 404, 409, 422 |
| `GET` | `/api/racas` | sim | Listar raça | 200 | 401 |
| `POST` | `/api/racas` | sim | Cadastrar raça | 201 | 400, 401, 409, 422 |
| `GET` | `/api/racas/{id}` | sim | Consultar raça | 200 | 401, 404 |
| `PUT` | `/api/racas/{id}` | sim | Alterar raça | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/racas/{id}` | sim | Inativar raça (exclusão lógica) | 200 | 401, 404, 409 |
| `POST` | `/api/racas/{id}/reativar` | sim | Reativar raça | 200 | 401, 404, 409, 422 |

**Animais**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/animais` | sim | Listar animal | 200 | 401 |
| `POST` | `/api/animais` | sim | Cadastrar animal | 201 | 400, 401, 409, 422 |
| `GET` | `/api/animais/{id}` | sim | Consultar animal | 200 | 401, 404 |
| `PUT` | `/api/animais/{id}` | sim | Alterar animal | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/animais/{id}` | sim | Inativar animal (exclusão lógica) | 200 | 401, 404, 409 |
| `POST` | `/api/animais/{id}/reativar` | sim | Reativar animal | 200 | 401, 404, 409, 422 |

**Microchip**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `POST` | `/api/animais/{id}/microchip` | sim | Vincular ou substituir o microchip RFID | 201 | 400, 401, 404, 409, 422 |
| `GET` | `/api/animais/{id}/microchips` | sim | Histórico de microchips do animal | 200 | 401, 404 |

**Consultas**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/animais/{id}/consultas` | sim | Histórico de consultas do animal | 200 | 401, 404 |
| `GET` | `/api/consultas` | sim | Listar consultas | 200 | 401 |
| `POST` | `/api/consultas` | sim | Registrar consulta | 201 | 400, 401, 422 |
| `GET` | `/api/consultas/{id}` | sim | Consultar consulta | 200 | 401, 404 |
| `PUT` | `/api/consultas/{id}` | sim | Alterar consulta | 200 | 400, 401, 404, 409, 422 |
| `DELETE` | `/api/consultas/{id}` | sim | Cancelar consulta | 200 | 401, 404, 409 |

**Vacinas**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/animais/{id}/vacinas` | sim | Histórico de vacinação (com status no governo) | 200 | 401, 404 |
| `GET` | `/api/animais/{id}/vacinas/proximas-doses` | sim | Próximas doses e reforços | 200 | 401, 404 |
| `POST` | `/api/vacinas` | sim | Registrar vacina | 201 | 400, 401, 422 |
| `GET` | `/api/vacinas/{id}` | sim | Consultar vacina | 200 | 401, 404 |
| `DELETE` | `/api/vacinas/{id}` | sim | Cancelar vacina agendada | 200 | 401, 404, 409 |
| `POST` | `/api/vacinas/{id}/aplicar` | sim | Aplicar uma vacina agendada | 200 | 400, 401, 404, 409, 422 |
| `GET` | `/api/vacinas/{id}/comunicacao-governo` | sim | Estado da comunicação ao governo | 200 | 401, 404 |

**Integração com o governo**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/animais/{id}/integracao-governo` | sim | Situação da integração do animal + operações | 200 | 401, 404 |
| `POST` | `/api/animais/{id}/sincronizar` | sim | Sincronização manual com o governo | 200 | 401, 404, 422 |
| `GET` | `/api/integracoes` | sim | Listar comunicações com o governo | 200 | 401 |
| `GET` | `/api/integracoes/{id}` | sim | Detalhe de uma comunicação (com o payload enviado) | 200 | 401, 404 |
| `POST` | `/api/integracoes/{id}/reenviar` | sim | Reenviar uma comunicação | 200 | 401, 404 |
| `POST` | `/api/integracoes/reprocessar-pendentes` | sim | Reprocessar todas as pendências | 200 | 401 |

**Demonstração**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/demo/governo/simulacao` | sim | Ver o modo de falha do governo simulado | 200 | 401, 503 |
| `PUT` | `/api/demo/governo/simulacao` | sim | Provocar indisponibilidade / lentidão do governo simulado | 200 | 400, 401, 422, 503 |

### API governamental simulada (porta 5001)

**Sistema**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/governo/health` | não | Saúde do serviço | 200 | 503 |

**Simulação de falhas**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/governo/simulacao` | sim | Ver o modo atual | 200 | 401 |
| `PUT` | `/api/governo/simulacao` | sim | Definir o modo (NORMAL / INDISPONIVEL / RESPOSTA_LENTA) | 200 | 400, 401, 422 |

**Animais**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `POST` | `/api/governo/animais` | sim | Cadastrar animal por microchip | 201 | 400, 401, 409, 422, 503 |
| `GET` | `/api/governo/animais/{microchip}` | sim | Consultar animal por microchip (inclui vacinações antirrábicas) | 200 | 401, 404, 503 |
| `PUT` | `/api/governo/animais/{microchip}` | sim | Atualizar cadastro do animal | 200 | 400, 401, 404, 422, 503 |

**Vacinações antirrábicas**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `POST` | `/api/governo/vacinacoes-antirrabicas` | sim | Receber vacinação antirrábica | 201 | 400, 401, 409, 422, 503 |
| `GET` | `/api/governo/vacinacoes-antirrabicas` | sim | Listar vacinações recebidas | 200 | 401, 503 |

**Protocolos**

| Método | Caminho | Auth | Resumo | Sucesso | Erros |
|---|---|---|---|---|---|
| `GET` | `/api/governo/operacoes/{protocolo}` | sim | Consultar uma operação pelo protocolo | 200 | 401, 404, 503 |

## Exemplos de uso (curl)

> Com a pilha no ar (`python scripts/run_all.py`). O token vem do login; `jq` é opcional.

```bash
# 1) Login (contas de demonstração em README.md)
TOKEN=$(curl -s localhost:5000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"ana.souza@clinicavet.example","senha":"Senha@123"}' | jq -r .token)
AUTH="Authorization: Bearer $TOKEN"

# 2) Consultar CEP (ViaCEP) — também trata CEP inexistente, timeout e serviço fora do ar
curl -s localhost:5000/api/cep/01001000 -H "$AUTH"

# 3) Cadastrar tutor (CPF único) com endereço aninhado
curl -s localhost:5000/api/tutores -H "$AUTH" -H 'Content-Type: application/json' -d '{
  "nome_completo":"Maria Oliveira","cpf":"52998224725","data_nascimento":"1990-05-10",
  "email":"maria@example.com","telefone":"11912345678",
  "endereco":{"cep":"01001000","logradouro":"Praça da Sé","numero":"100","bairro":"Sé","cidade":"São Paulo","uf":"SP"}}'

# 4) Cadastrar animal e vincular o microchip (15 dígitos, único e nunca reutilizável)
curl -s localhost:5000/api/animais -H "$AUTH" -H 'Content-Type: application/json' -d '{
  "nome":"Thor","tutor_id":1,"especie_id":1,"sexo":"MACHO","cor":"Caramelo","peso_atual":12.5,"data_nascimento":"2022-03-01"}'
curl -s localhost:5000/api/animais/1/microchip -H "$AUTH" -H 'Content-Type: application/json' -d '{"codigo":"900123456789012"}'

# 5) Registrar a vacina ANTIRRÁBICA: grava local e comunica o governo (CONFIRMADA ou PENDENTE)
curl -s localhost:5000/api/vacinas -H "$AUTH" -H 'Content-Type: application/json' -d '{
  "animal_id":1,"nome_vacina":"Antirrábica anual","tipo_vacina":"ANTIRRABICA","dose":"Dose única","via_aplicacao":"SUBCUTANEA",
  "data_aplicacao":"2026-11-05","fabricante":"Zoetis","numero_lote":"L2026-0457","validade_lote":"2027-08-31"}'

# 6) Governo fora do ar -> a vacina fica registrada e a comunicação PENDENTE; depois reenvie
curl -s -X PUT localhost:5000/api/demo/governo/simulacao -H "$AUTH" -H 'Content-Type: application/json' -d '{"modo":"INDISPONIVEL"}'
curl -s -X PUT localhost:5000/api/demo/governo/simulacao -H "$AUTH" -H 'Content-Type: application/json' -d '{"modo":"NORMAL"}'
curl -s -X POST localhost:5000/api/integracoes/reprocessar-pendentes -H "$AUTH"

# 7) Idempotência: reenviar uma operação já confirmada devolve o MESMO protocolo
curl -s -X POST 'localhost:5000/api/integracoes/1/reenviar?forcar=true' -H "$AUTH"

# API do governo diretamente (chave de demonstração)
curl -s localhost:5001/api/governo/animais/900123456789012 -H 'X-API-Key: chave-demo-governo'
```
