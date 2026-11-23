# 05 — Roteiro de apresentação (demonstração do fluxo completo)

Projeto A3 – SDM · Apresentação: **26/11/2026** · duração sugerida: **15 minutos** + perguntas

> **Entregável 11** do enunciado: apresentação demonstrando o fluxo completo do sistema.
> O roteiro segue o "resultado esperado" do enunciado (seção 12): login → tutor e endereço → CEP → animal →
> microchip → consulta e vacina → comunicação ao governo, **com ênfase na antirrábica**: indisponibilidade,
> pendência, regularização posterior **sem duplicidade**.

Todos os dados são **fictícios**. Senha de todos os usuários de demonstração: `Senha@123`.

---

## 0. Preparação (faça 10 minutos antes)

1. Banco limpo e pilha no ar (escolha uma):

   ```bash
   python scripts/run_all.py --reset                  # MySQL (ver README)
   python scripts/run_all.py --sqlite --reset         # sem MySQL (plano B)
   ```

   Para demonstrar o **reenvio manual** de forma previsível, suba com o reenvio automático desligado
   (`AUTO_RETRY=0` no `.env` ou na linha de comando). Se ficar ligado, o sistema também se regulariza sozinho a
   cada 30 s — mostre isso como bônus (passo 9).

2. Abas do navegador já abertas: **sistema** `http://localhost:5000`, **Swagger da clínica** `…:5000/docs` e
   **Swagger do governo** `…:5001/docs` (precisam de internet para carregar o Swagger UI; sem internet, mostre os
   arquivos `docs/openapi/*.yaml` ou a coleção no Postman).
3. Postman com a coleção importada (`docs/postman/`), para o passo final.
4. Terminal visível com o log do `run_all.py` (mostra as chamadas HTTP entre clínica e governo — ótima evidência
   de que são serviços separados conversando por HTTP).
5. Conferir: `http://localhost:5000/api/status` mostra API, banco e governo "ok".
6. **Internet**: com internet o CEP vem do ViaCEP real. Sem internet, suba com `--viacep-falso` e avise a banca.

**Contas de demonstração**

| Veterinário | E-mail | Estado | Para que serve |
|---|---|---|---|
| Dra. Ana Souza | `ana.souza@clinicavet.example` | ativa, senha confirmada | usuária da demonstração |
| Dr. Bruno Lima | `bruno.lima@clinicavet.example` | **inativo** | provar o bloqueio (T02) |
| Dra. Carla Mendes | `carla.mendes@clinicavet.example` | **senha não confirmada** | provar o bloqueio e o fluxo de confirmação (T03) |

---

## 1. Roteiro cronometrado

| Tempo | Passo | O que mostrar e dizer | Requisito / teste |
|---|---|---|---|
| 0:00 | **Contexto** (slide de arquitetura) | Três serviços por HTTP: frontend + API privada (5000), API governamental **simulada** (5001, banco próprio) e ViaCEP real. Mostrar `docs/diagramas/arquitetura.png`. | Seção 2 do doc. 01 |
| 1:30 | **1. Segurança de acesso** | Login da **Bruno** → bloqueado (inativo). Login da **Carla** → bloqueada e levada à **confirmação por código**. Login com **senha errada** → mensagem genérica (não revela se o e-mail existe). | T02, T03, T04 |
| 3:00 | **2. Login válido** | Entrar como **Ana**. Mostrar o painel (indicadores, saúde do governo). Dizer: token JWT + sessão revogável; cada requisição revalida se o veterinário continua ativo. | T01 |
| 3:45 | **3. Tutor + CEP (ViaCEP)** | *Tutores → Novo tutor*. Digitar CEP `01001000` → **Buscar CEP** preenche o endereço. Testar CEP `99999999` → "não encontrado" e campos liberados para preenchimento manual. CPF **inválido** e CPF **duplicado** (repetir o cadastro) → recusados. | T05, T06 |
| 5:30 | **4. Animal + microchip** | *Animais → Novo animal*: espécie obrigatória; escolher raça de **outra** espécie não é possível (lista filtrada) e existe "sem raça definida". Salvar → abre a ficha. *Resumo e microchip → Vincular microchip* → **Gerar código simulado** → confirma "cadastro confirmado pelo governo". Tentar vincular o **mesmo código** a outro animal → recusado. Substituir um chip → histórico preservado. | T07, T08 |
| 7:15 | **5. Consulta** | Aba *Consultas → Nova consulta* → salvar → aparece no histórico do animal. Mostrar o ciclo de situações: criar uma consulta **Agendada** (data futura) → **Atender** (vira *Realizada* com diagnóstico e peso, que atualiza o peso do animal) e outra agendada → **Faltou** (*Não compareceu*); **Editar** corrige uma consulta realizada; consulta **Realizada** não pode ser cancelada. | T09 |
| 8:00 | **6. Vacina não antirrábica** | Aba *Vacinas → Registrar vacina* (Polivalente, com próxima dose) → resposta: "**não é antirrábica; nenhuma comunicação ao governo**". Mostrar a lista de **próximas doses**. | T10, T13 |
| 8:45 | **7. Antirrábica com governo no ar** | Registrar vacina **Antirrábica**. A tela avisa se faltar microchip. Resposta separa **"Registro na clínica"** de **"Comunicação ao governo: CONFIRMADA"** com **protocolo** (`GOV-AAAAMMDD-…`). Abrir *Governo (integração) → Detalhes* e mostrar o payload enviado (microchip, animal, data, vacina, fabricante, lote, veterinário). | T12 |
| 10:00 | **8. Governo FORA DO AR** | No **Painel**, botão **Indisponível (503)**. Registrar **outra** antirrábica → "**Registrada na clínica**, comunicação **PENDENTE**". Mostrar que a vacina está no histórico (registro local garantido) e a integração na fila com a mensagem de erro e `tentativas`. | T14 |
| 11:30 | **9. Regularização** | Painel → **Normal**. Em *Painel*, **Reprocessar pendências** (ou *Governo (integração) → Reenviar*) → **CONFIRMADA** com protocolo. *Bônus (reenvio automático ligado):* esperar o ciclo de 30 s e mostrar que ela se confirma sozinha. | T15 |
| 12:30 | **10. Idempotência** | *Governo (integração)* → **Testar idempotência** numa integração já confirmada → "**mesmo protocolo**, nada duplicado". Abrir `GET /api/governo/animais/{microchip}` no Swagger do governo e mostrar que há **uma** vacinação por aplicação. Explicar `Idempotency-Key` + chaves únicas no banco do governo. | T16 |
| 13:30 | **11. Evidências** | Mostrar `docs/04-relatorio-de-testes.md`: pytest 66/66, coleção Postman 128/128, interface 26/26; rodar `node scripts/executar_colecao.js` ao vivo (≈ 5 s) **ou** a coleção no Postman. Citar a limitação (SQLite/ViaCEP simulado) se for o caso — ver relatório, seção 3. | Testes, docs |
| 14:30 | **Encerramento** | Rastreabilidade: cada requisito do enunciado ↔ doc. 01, seção 7. Abrir para perguntas. | — |

### Variação de contingência para a falha de timeout (opcional, +1 min)

No Painel, **Resposta lenta (timeout)**: o governo **processa e demora** a responder; a clínica estoura o
*timeout* e deixa a integração como **ENVIADA** ("resultado incerto"). Ao reenviar, o governo devolve o **mesmo
protocolo** — é o caso clássico que justifica a idempotência (o cliente não sabe se a operação foi feita).

---

## 2. Plano B (se algo falhar na hora)

| Problema | Solução rápida |
|---|---|
| MySQL não sobe | `python scripts/run_all.py --sqlite --reset` (mesmo sistema, banco em arquivo); avise a banca |
| Sem internet / ViaCEP fora | `--viacep-falso`; CEPs: `01001000` (ok), `99999999` (não existe), `11111111` (timeout) |
| Swagger UI não carrega (CDN) | Mostrar `docs/openapi/*.yaml` ou usar a coleção no Postman |
| A demonstração "bagunçou" os dados | `Ctrl+C` e subir de novo com `--reset` (leva segundos) |
| Governo ficou em modo falha | Painel → **Normal** (ou reiniciar a API do governo: o modo volta a NORMAL) |
| Pendência virou **FALHA** (muitos reenvios automáticos com o governo fora do ar) | Reenvio **manual** sempre é permitido: *Reenviar* regulariza |
| Quiser mostrar tudo sem digitar | `python scripts/smoke_ui.py` roda o fluxo completo no navegador (gera as capturas em `docs/img/ui/`) |

---

## 3. Perguntas prováveis da banca (e onde está a resposta)

| Pergunta | Resposta curta |
|---|---|
| *Como vocês garantem que a vacina não se perde se o governo cair?* | **Outbox**: vacina e a linha `PENDENTE` são gravadas na mesma transação; a chamada de rede só acontece depois do *commit*. |
| *E se o governo processar mas a resposta não chegar?* | O estado fica **ENVIADA** (incerto). O reenvio usa a **mesma `Idempotency-Key`**; o governo devolve o protocolo original (`200`, `repetida: true`). |
| *Como impedem duplicidade no governo?* | Duas barreiras: chave de idempotência por vacina (`vacina-{id}-antirrabica`) e `UNIQUE` por `(microchip, id_aplicacao_origem)` e por `(microchip, data, lote)` no banco do governo. |
| *Como sabem que uma vacina é antirrábica?* | Pelo **campo estruturado** `tipo_vacina = ANTIRRABICA` (com `CHECK` no banco), não pelo nome digitado. |
| *E se o animal não estiver cadastrado no governo?* | A vacinação é comunicada mesmo assim (regra 2 do enunciado); o cadastro é outra integração independente. |
| *Como é a segurança da senha?* | Hash **scrypt** com *salt*; o código de confirmação só é guardado como HMAC, com validade, uso único e limite de tentativas. |
| *Por que o e-mail/ViaCEP/governo não derrubam o sistema?* | Todo acesso externo tem *timeout* e é classificado (OK, indisponível, incerto, rejeitado); o cadastro nunca depende do serviço externo. |
| *Por que dois bancos?* | Clínica e governo são sistemas distintos; a separação é real (bancos e processos independentes) e só se falam por HTTP. |
| *Como um microchip pode ser substituído sem perder o histórico?* | Tabela `vinculo_microchip`: o anterior vira `SUBSTITUIDO` (motivo e data); `UNIQUE (animal_id, vigente)` garante um só ativo. |
| *O governo é real?* | **Não.** É uma simulação acadêmica, declarada como tal em todo o código e documentação. |

---

## 4. Divisão sugerida de falas (ajuste ao tamanho do grupo)

| Bloco | Conteúdo | Tempo |
|---|---|---|
| A | Contexto, arquitetura, modelo de dados (ER) | 2 min |
| B | Segurança de acesso e cadastros (tutor, CEP, animal, microchip) — passos 1–4 | 4 min |
| C | Consulta e vacinas; antirrábica com governo no ar — passos 5–7 | 3 min |
| D | Falha, pendência, regularização e idempotência — passos 8–10 | 4 min |
| E | Testes, documentação e encerramento — passo 11 | 2 min |
