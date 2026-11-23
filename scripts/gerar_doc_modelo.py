"""Gera docs/02-modelo-de-dados.md: texto explicativo + tabelas do modelo relacional
extraídas do DDL real (database/ddl.py), para que o documento nunca fique
defasado em relação ao banco.

Uso:  python scripts/gerar_doc_modelo.py
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

from database import ddl  # noqa: E402
from gerar_modelo_relacional import descrever  # noqa: E402


def tabelas(titulo, comandos):
    texto = descrever(titulo, comandos)
    # O DDL do SQLite usa INTEGER nas PKs; no MySQL (entregável) o tipo é INT.
    texto = texto.replace("| INTEGER |", "| INT |")
    # Rebaixa o título gerado (###) para o nível da seção do documento (###)
    return texto


CABECALHO = """# 02 — Modelo de dados (ER e modelo relacional)

Projeto A3 – SDM · Sistema Web para Gestão de Clínica Veterinária com Integração de APIs

> **Entregável 2** do enunciado: modelo entidade-relacionamento e modelo relacional.
> Este arquivo é **gerado** por `scripts/gerar_doc_modelo.py` a partir do DDL real
> (`database/ddl.py`); as tabelas abaixo, portanto, correspondem exatamente ao banco criado
> por `database/mysql/*.sql`.

## 1. Visão geral

O sistema usa **dois bancos independentes**, porque a clínica e o governo são sistemas
distintos e só se comunicam por HTTP:

| Banco | Dono | Conteúdo |
|---|---|---|
| `sdm_clinica` | API privada da clínica | as 10 entidades obrigatórias do enunciado + 2 tabelas auxiliares de autenticação |
| `sdm_governo` | API governamental simulada | cadastro nacional de animais, registro de operações (idempotência) e vacinações antirrábicas |

### 1.1 Entidades obrigatórias (enunciado) e tabelas auxiliares

| # | Entidade do enunciado | Tabela | Observação |
|---|---|---|---|
| 1 | Espécie | `especie` | catálogo com situação ATIVA/INATIVA |
| 2 | Raça | `raca` | pertence a uma espécie; nome único dentro da espécie |
| 3 | Endereço | `endereco` | preenchido a partir do ViaCEP + número/complemento |
| 4 | Tutor | `tutor` | CPF único; um endereço |
| 5 | Veterinário | `veterinario` | CRMV (número+UF) único; senha com hash; confirmação de senha |
| 6 | Animal | `animal` | tutor, espécie e raça opcional (raça deve pertencer à espécie) |
| 7 | Microchip | `vinculo_microchip` | histórico de vínculos; **apenas um vigente** por animal |
| 8 | Consulta | `consulta` | anamnese, diagnóstico, tratamento, prescrição, sinais vitais |
| 9 | Vacina | `vacina` | aplicações/agendamentos; indicador `antirrabica` |
| 10 | Integração com o governo | `integracao_governo` | controle de comunicação: PENDENTE/ENVIADA/CONFIRMADA/FALHA |
| — | (auxiliar) | `codigo_confirmacao` | código de 6 dígitos guardado apenas como HMAC |
| — | (auxiliar) | `sessao_login` | sessões JWT revogáveis (logout/inativação) |

## 2. Diagrama entidade-relacionamento

### 2.1 Banco da clínica

![ER da clínica](er-clinica.png)

Fonte editável: [`er-clinica.mmd`](er-clinica.mmd) (Mermaid).

Cardinalidades principais:

* **Espécie 1 — N Raça**; **Espécie 1 — N Animal**; **Raça 0..1 — N Animal** (a raça é opcional, p.ex. SRD).
* **Endereço 1 — N Tutor**; **Tutor 1 — N Animal**.
* **Animal 1 — N Vínculo de microchip** (histórico), com **no máximo 1 vigente**.
* **Animal 1 — N Consulta**, **Animal 1 — N Vacina**; ambos registram o **Veterinário** responsável.
* **Vacina 0..1 — 0..1 Integração** (somente vacinas antirrábicas geram integração de vacinação).
* **Animal 1 — N Integração** (cadastro/atualização do animal e vacinação).
* **Veterinário 1 — N Código de confirmação** e **1 — N Sessão de login**.

### 2.2 Banco do governo simulado

![ER do governo](er-governo.png)

Fonte editável: [`er-governo.mmd`](er-governo.mmd).

O governo guarda **sua própria visão** do animal (chaveada pelo microchip, sem `id` da clínica
como chave) e registra cada operação recebida em `gov_operacao`, o que permite responder
a uma repetição da mesma `Idempotency-Key` com o **mesmo protocolo**, sem duplicar a vacinação.

## 3. Modelo relacional

Legenda: **PK** chave primária · **FK** chave estrangeira · **UK** parte de restrição de
unicidade · nomes `uq_*` (unicidade), `ck_*` (CHECK) e `fk_*` (chave estrangeira) são os
mesmos nomes de constraint existentes no script SQL.

"""

DECISOES = """

## 4. Decisões de modelagem

**4.1 Raça compatível com a espécie (FK composta).**
`raca` possui `UNIQUE (id, especie_id)` e `animal` referencia `(raca_id, especie_id)`.
Assim o *próprio banco* impede cadastrar, por exemplo, um "Siamês" para um cão. Como a raça é
opcional (`raca_id NULL`), o MySQL não valida a FK composta quando `raca_id` é nulo (comportamento
`MATCH SIMPLE`), e o animal sem raça definida (SRD) continua permitido.

**4.2 Apenas um microchip vigente por animal (coluna `vigente`).**
Um índice `UNIQUE (animal_id)` impediria guardar o histórico. A solução usada é
`UNIQUE (animal_id, vigente)` com `vigente = 1` para o vínculo ativo e `vigente = NULL` para os
substituídos: unicidade em colunas com `NULL` não é violada (vários `NULL` são permitidos), então
existe no máximo **um** registro ativo por animal, mas qualquer quantidade de históricos.
O `CHECK ck_vinculo_situacao` mantém `situacao` e `vigente` coerentes. O código do chip também
é único globalmente (`uq_microchip_codigo`): um mesmo chip não pode estar em dois animais.

**4.3 Domínios por CHECK, não ENUM.**
Situações e tipos usam `CHECK (... IN (...))`, o que mantém o DDL idêntico em MySQL e SQLite e
facilita a evolução (basta alterar a constraint). Exige **MySQL ≥ 8.0.16** — versões anteriores
aceitam a sintaxe mas *ignoram* o CHECK.

**4.4 Exclusão lógica.**
Nenhuma tabela usa `ON DELETE CASCADE`. Registros clínicos nunca são apagados: tutores,
animais, veterinários e catálogos mudam de `situacao` (ATIVO/INATIVO etc.), e consultas/vacinas
são *canceladas*. Isso preserva o histórico e a rastreabilidade exigida em dados de saúde animal.

**4.5 Vacina antirrábica identificada por coluna e consistente com o tipo.**
`vacina.antirrabica` (0/1) existe para consulta rápida, e o `CHECK ck_vacina_antirrabica` garante que
seja 1 *se e somente se* `tipo_vacina = 'ANTIRRABICA'`. Uma vacina com `situacao = 'APLICADA'` exige
fabricante, lote e validade do lote (`ck_vacina_aplicada_completa`); a próxima dose, quando
informada, é posterior à aplicação (`ck_vacina_proxima`).

**4.6 Controle de integração como *outbox*.**
`integracao_governo` é gravada **na mesma transação** da vacina/vínculo que a originou, já como
`PENDENTE`; só depois a API tenta chamar o governo. Se o governo estiver fora do ar, o registro local
permanece e a pendência fica visível e reenviável. Garantias de integridade:

* `uq_integracao_vacina (vacina_id)` — uma vacina gera **no máximo uma** integração;
* `uq_integracao_chave (chave_idempotencia)` — a chave enviada no cabeçalho `Idempotency-Key`
  é única, o que permite reenviar sem duplicar do lado do governo;
* `ck_integracao_vacina` — `vacina_id` é obrigatório para `VACINACAO_ANTIRRABICA` e proibido
  para os demais tipos;
* `ck_integracao_situacao` — estados válidos: `PENDENTE`, `ENVIADA`, `CONFIRMADA`, `FALHA`;
* `payload_enviado` guarda o JSON exatamente como foi enviado (auditoria / reenvio idêntico).

**4.7 Segurança dos dados de autenticação.**
`veterinario.senha_hash` guarda apenas o hash *scrypt* (Werkzeug) — nunca a senha.
`codigo_confirmacao.codigo_hash` guarda um HMAC-SHA256 do código de 6 dígitos (64 caracteres hex),
com validade (`expira_em`), uso único (`utilizado_em`) e contador de tentativas.
`ck_veterinario_confirmacao` garante que `senha_confirmada = 1` ocorra somente com a data
de confirmação preenchida. `sessao_login.jti` permite **revogar** tokens (logout, inativação do
veterinário) mesmo antes da expiração.

**4.8 Endereço separado do tutor.**
O endereço (CEP, logradouro, bairro, cidade, UF, código IBGE) vem do ViaCEP; `numero` e
`complemento` são informados pelo usuário. Fica em tabela própria (1 endereço → N tutores)
conforme a lista de entidades do enunciado.

**4.9 Tipos e formatos.**
CPF e CEP são `CHAR` só com dígitos (a máscara é apenas de apresentação); o microchip é
`VARCHAR(15)` com `CHECK` de 15 caracteres (padrão ISO 11784/11785); peso com `DECIMAL(6,2)`
e temperatura com `DECIMAL(4,1)` (faixa 30–45 °C). Datas/horas são gravadas pela aplicação
(sem `DEFAULT` dependente de função) no horário local do servidor, sem fuso.

**4.10 Índices.**
Além dos índices implícitos de PK/UK/FK: `idx_animal_tutor`, `idx_consulta_animal_data`,
`idx_vacina_animal_data` (históricos por animal), `idx_integracao_situacao` (fila de pendentes) e
`idx_integracao_animal`.

**4.11 Banco do governo.**
`gov_animal` é chaveado por `microchip` (único). `gov_operacao` registra *toda* operação recebida —
inclusive as rejeitadas — com `chave_idempotencia` única, o código HTTP e a resposta original, para
repetir exatamente a mesma resposta num reenvio. `gov_vacinacao_antirrabica` tem duas unicidades:
`(microchip, id_aplicacao_origem)` (a mesma aplicação da clínica nunca é registrada duas vezes) e
`(microchip, data_aplicacao, numero_lote)` (a mesma dose física não vira dois registros mesmo com
chaves de idempotência diferentes).

## 5. Como o modelo foi validado

* O DDL é executado na criação do banco em **todos** os testes automatizados
  (`tests/test_modelo_dados.py`), que exercitam cada `CHECK`, `UNIQUE` e `FOREIGN KEY` relevante:
  raça de outra espécie, segundo microchip vigente, vacina aplicada sem lote, integração duplicada etc.
* O script MySQL (`database/mysql/01_clinica_schema.sql`, `03_governo_schema.sql`) é **gerado** do mesmo
  DDL por `scripts/gerar_sql.py`. Neste ambiente de desenvolvimento não havia servidor MySQL, então os
  testes automatizados rodam em SQLite com o mesmo DDL; a execução em MySQL deve ser conferida
  seguindo o README (seção "Banco MySQL") — ver limitações no relatório de testes.
"""


def main():
    partes = [
        CABECALHO,
        tabelas("3.1 Banco da clínica (`sdm_clinica`)", ddl.comandos_clinica("sqlite")),
        "",
        tabelas("3.2 Banco do governo simulado (`sdm_governo`)", ddl.comandos_governo("sqlite")),
        DECISOES,
    ]
    saida = os.path.join(RAIZ, "docs", "02-modelo-de-dados.md")
    with open(saida, "w", encoding="utf-8") as f:
        f.write("\n".join(partes))
    print("gerado:", saida)


if __name__ == "__main__":
    main()
