"""
Fonte única do DDL do projeto SDM (Clínica Veterinária).

O mesmo texto gera o script para MySQL 8 (entregável) e para SQLite (usado em
desenvolvimento rápido e nos testes automatizados). Só dois tokens mudam entre
os dialetos: {PK} e {ENGINE}. Todo o resto usa um subconjunto portável:

  * FOREIGN KEY sempre no nível da tabela (no MySQL a forma inline é ignorada);
  * domínios por CHECK (em vez de ENUM), exigindo MySQL >= 8.0.16 para valer;
  * nenhum DEFAULT dependente de função (datas são informadas pela aplicação).

Para regenerar os .sql:  python scripts/gerar_sql.py
"""

DIALETOS = {
    "mysql": {
        "PK": "INT NOT NULL AUTO_INCREMENT PRIMARY KEY",
        "ENGINE": "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
    },
    "sqlite": {
        "PK": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "ENGINE": "",
    },
}

# --------------------------------------------------------------------------
# Banco da CLÍNICA  (sdm_clinica)
# A ordem respeita as dependências entre chaves estrangeiras.
# --------------------------------------------------------------------------
CLINICA_TABELAS = [
    ("especie", """
CREATE TABLE especie (
  id {PK},
  nome VARCHAR(60) NOT NULL,
  descricao VARCHAR(255) NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVA',
  CONSTRAINT uq_especie_nome UNIQUE (nome),
  CONSTRAINT ck_especie_situacao CHECK (situacao IN ('ATIVA','INATIVA'))
) {ENGINE}"""),

    ("raca", """
CREATE TABLE raca (
  id {PK},
  nome VARCHAR(80) NOT NULL,
  descricao VARCHAR(255) NULL,
  especie_id INT NOT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVA',
  CONSTRAINT uq_raca_especie_nome UNIQUE (especie_id, nome),
  CONSTRAINT uq_raca_id_especie UNIQUE (id, especie_id),
  CONSTRAINT fk_raca_especie FOREIGN KEY (especie_id) REFERENCES especie (id),
  CONSTRAINT ck_raca_situacao CHECK (situacao IN ('ATIVA','INATIVA'))
) {ENGINE}"""),

    ("endereco", """
CREATE TABLE endereco (
  id {PK},
  cep CHAR(8) NOT NULL,
  logradouro VARCHAR(150) NOT NULL,
  numero VARCHAR(10) NOT NULL,
  complemento VARCHAR(80) NULL,
  bairro VARCHAR(80) NOT NULL,
  cidade VARCHAR(80) NOT NULL,
  uf CHAR(2) NOT NULL,
  codigo_ibge CHAR(7) NULL,
  CONSTRAINT ck_endereco_cep CHECK (LENGTH(cep) = 8)
) {ENGINE}"""),

    ("tutor", """
CREATE TABLE tutor (
  id {PK},
  nome_completo VARCHAR(150) NOT NULL,
  cpf CHAR(11) NOT NULL,
  data_nascimento DATE NOT NULL,
  email VARCHAR(150) NOT NULL,
  telefone VARCHAR(15) NOT NULL,
  endereco_id INT NOT NULL,
  data_cadastro DATETIME NOT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  CONSTRAINT uq_tutor_cpf UNIQUE (cpf),
  CONSTRAINT fk_tutor_endereco FOREIGN KEY (endereco_id) REFERENCES endereco (id),
  CONSTRAINT ck_tutor_situacao CHECK (situacao IN ('ATIVO','INATIVO')),
  CONSTRAINT ck_tutor_cpf CHECK (LENGTH(cpf) = 11)
) {ENGINE}"""),

    ("veterinario", """
CREATE TABLE veterinario (
  id {PK},
  nome_completo VARCHAR(150) NOT NULL,
  cpf CHAR(11) NOT NULL,
  crmv_numero VARCHAR(10) NOT NULL,
  crmv_uf CHAR(2) NOT NULL,
  email VARCHAR(150) NOT NULL,
  telefone VARCHAR(15) NOT NULL,
  senha_hash VARCHAR(255) NOT NULL,
  senha_confirmada TINYINT NOT NULL DEFAULT 0,
  senha_confirmada_em DATETIME NULL,
  data_cadastro DATETIME NOT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  ultimo_acesso_em DATETIME NULL,
  CONSTRAINT uq_veterinario_cpf UNIQUE (cpf),
  CONSTRAINT uq_veterinario_email UNIQUE (email),
  CONSTRAINT uq_veterinario_crmv UNIQUE (crmv_numero, crmv_uf),
  CONSTRAINT ck_veterinario_situacao CHECK (situacao IN ('ATIVO','INATIVO')),
  CONSTRAINT ck_veterinario_confirmacao CHECK (
    (senha_confirmada = 0 AND senha_confirmada_em IS NULL) OR
    (senha_confirmada = 1 AND senha_confirmada_em IS NOT NULL))
) {ENGINE}"""),

    # Auxiliar: códigos de confirmação de senha (armazenados somente como HMAC).
    ("codigo_confirmacao", """
CREATE TABLE codigo_confirmacao (
  id {PK},
  veterinario_id INT NOT NULL,
  codigo_hash CHAR(64) NOT NULL,
  criado_em DATETIME NOT NULL,
  expira_em DATETIME NOT NULL,
  utilizado_em DATETIME NULL,
  tentativas INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_codconf_vet FOREIGN KEY (veterinario_id) REFERENCES veterinario (id)
) {ENGINE}"""),

    # Auxiliar: sessões de login, o que permite logout real (revogação do token).
    ("sessao_login", """
CREATE TABLE sessao_login (
  id {PK},
  jti CHAR(32) NOT NULL,
  veterinario_id INT NOT NULL,
  criada_em DATETIME NOT NULL,
  expira_em DATETIME NOT NULL,
  revogada_em DATETIME NULL,
  CONSTRAINT uq_sessao_jti UNIQUE (jti),
  CONSTRAINT fk_sessao_vet FOREIGN KEY (veterinario_id) REFERENCES veterinario (id)
) {ENGINE}"""),

    ("animal", """
CREATE TABLE animal (
  id {PK},
  nome VARCHAR(80) NOT NULL,
  data_nascimento DATE NULL,
  idade_estimada_meses INT NULL,
  sexo VARCHAR(10) NOT NULL,
  cor VARCHAR(50) NOT NULL,
  peso_atual DECIMAL(6,2) NOT NULL,
  tutor_id INT NOT NULL,
  especie_id INT NOT NULL,
  raca_id INT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  data_cadastro DATETIME NOT NULL,
  CONSTRAINT fk_animal_tutor FOREIGN KEY (tutor_id) REFERENCES tutor (id),
  CONSTRAINT fk_animal_especie FOREIGN KEY (especie_id) REFERENCES especie (id),
  CONSTRAINT fk_animal_raca_especie FOREIGN KEY (raca_id, especie_id) REFERENCES raca (id, especie_id),
  CONSTRAINT ck_animal_sexo CHECK (sexo IN ('MACHO','FEMEA')),
  CONSTRAINT ck_animal_situacao CHECK (situacao IN ('ATIVO','INATIVO','OBITO')),
  CONSTRAINT ck_animal_idade CHECK (data_nascimento IS NOT NULL OR idade_estimada_meses IS NOT NULL),
  CONSTRAINT ck_animal_peso CHECK (peso_atual > 0)
) {ENGINE}"""),

    ("vinculo_microchip", """
CREATE TABLE vinculo_microchip (
  id {PK},
  animal_id INT NOT NULL,
  codigo_microchip VARCHAR(15) NOT NULL,
  veterinario_id INT NOT NULL,
  data_vinculo DATETIME NOT NULL,
  situacao VARCHAR(12) NOT NULL DEFAULT 'ATIVO',
  vigente TINYINT NULL,
  data_substituicao DATETIME NULL,
  motivo_substituicao VARCHAR(255) NULL,
  CONSTRAINT uq_microchip_codigo UNIQUE (codigo_microchip),
  CONSTRAINT uq_microchip_animal_vigente UNIQUE (animal_id, vigente),
  CONSTRAINT fk_vinculo_animal FOREIGN KEY (animal_id) REFERENCES animal (id),
  CONSTRAINT fk_vinculo_vet FOREIGN KEY (veterinario_id) REFERENCES veterinario (id),
  CONSTRAINT ck_vinculo_codigo CHECK (LENGTH(codigo_microchip) = 15),
  CONSTRAINT ck_vinculo_situacao CHECK (
    (situacao = 'ATIVO' AND vigente = 1) OR
    (situacao = 'SUBSTITUIDO' AND vigente IS NULL))
) {ENGINE}"""),

    ("consulta", """
CREATE TABLE consulta (
  id {PK},
  animal_id INT NOT NULL,
  veterinario_id INT NOT NULL,
  data_hora DATETIME NOT NULL,
  motivo VARCHAR(255) NOT NULL,
  anamnese TEXT NULL,
  sintomas TEXT NULL,
  diagnostico TEXT NULL,
  tratamento TEXT NULL,
  prescricao_medicamentos TEXT NULL,
  peso_kg DECIMAL(6,2) NULL,
  temperatura_c DECIMAL(4,1) NULL,
  observacoes TEXT NULL,
  situacao VARCHAR(15) NOT NULL DEFAULT 'AGENDADA',
  CONSTRAINT fk_consulta_animal FOREIGN KEY (animal_id) REFERENCES animal (id),
  CONSTRAINT fk_consulta_vet FOREIGN KEY (veterinario_id) REFERENCES veterinario (id),
  CONSTRAINT ck_consulta_situacao CHECK (situacao IN ('AGENDADA','REALIZADA','CANCELADA','NAO_COMPARECEU')),
  CONSTRAINT ck_consulta_peso CHECK (peso_kg IS NULL OR peso_kg > 0),
  CONSTRAINT ck_consulta_temp CHECK (temperatura_c IS NULL OR (temperatura_c >= 30 AND temperatura_c <= 45))
) {ENGINE}"""),

    ("vacina", """
CREATE TABLE vacina (
  id {PK},
  animal_id INT NOT NULL,
  veterinario_id INT NOT NULL,
  nome_vacina VARCHAR(100) NOT NULL,
  tipo_vacina VARCHAR(30) NOT NULL,
  antirrabica TINYINT NOT NULL DEFAULT 0,
  fabricante VARCHAR(100) NULL,
  numero_lote VARCHAR(50) NULL,
  data_aplicacao DATE NOT NULL,
  dose VARCHAR(40) NOT NULL,
  via_aplicacao VARCHAR(20) NOT NULL,
  data_proxima_dose DATE NULL,
  validade_lote DATE NULL,
  observacoes TEXT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'APLICADA',
  CONSTRAINT fk_vacina_animal FOREIGN KEY (animal_id) REFERENCES animal (id),
  CONSTRAINT fk_vacina_vet FOREIGN KEY (veterinario_id) REFERENCES veterinario (id),
  CONSTRAINT ck_vacina_tipo CHECK (tipo_vacina IN
    ('ANTIRRABICA','POLIVALENTE','TRIPLICE_FELINA','GRIPE_CANINA','GIARDIA','LEISHMANIOSE','OUTRA')),
  CONSTRAINT ck_vacina_via CHECK (via_aplicacao IN ('SUBCUTANEA','INTRAMUSCULAR','INTRANASAL','ORAL')),
  CONSTRAINT ck_vacina_situacao CHECK (situacao IN ('AGENDADA','APLICADA','CANCELADA')),
  CONSTRAINT ck_vacina_antirrabica CHECK (
    (antirrabica = 1 AND tipo_vacina = 'ANTIRRABICA') OR
    (antirrabica = 0 AND tipo_vacina <> 'ANTIRRABICA')),
  CONSTRAINT ck_vacina_proxima CHECK (data_proxima_dose IS NULL OR data_proxima_dose > data_aplicacao),
  CONSTRAINT ck_vacina_aplicada_completa CHECK (
    situacao <> 'APLICADA' OR
    (fabricante IS NOT NULL AND numero_lote IS NOT NULL AND validade_lote IS NOT NULL))
) {ENGINE}"""),

    ("integracao_governo", """
CREATE TABLE integracao_governo (
  id {PK},
  animal_id INT NOT NULL,
  vacina_id INT NULL,
  vinculo_microchip_id INT NULL,
  tipo_operacao VARCHAR(30) NOT NULL,
  protocolo_externo VARCHAR(40) NULL,
  chave_idempotencia VARCHAR(100) NOT NULL,
  situacao VARCHAR(12) NOT NULL DEFAULT 'PENDENTE',
  solicitada_em DATETIME NOT NULL,
  respondida_em DATETIME NULL,
  ultima_tentativa_em DATETIME NULL,
  tentativas INT NOT NULL DEFAULT 0,
  mensagem_erro VARCHAR(500) NULL,
  payload_enviado TEXT NULL,
  CONSTRAINT uq_integracao_chave UNIQUE (chave_idempotencia),
  CONSTRAINT uq_integracao_vacina UNIQUE (vacina_id),
  CONSTRAINT fk_integracao_animal FOREIGN KEY (animal_id) REFERENCES animal (id),
  CONSTRAINT fk_integracao_vacina FOREIGN KEY (vacina_id) REFERENCES vacina (id),
  CONSTRAINT fk_integracao_vinculo FOREIGN KEY (vinculo_microchip_id) REFERENCES vinculo_microchip (id),
  CONSTRAINT ck_integracao_tipo CHECK (tipo_operacao IN
    ('CADASTRO_ANIMAL','ATUALIZACAO_ANIMAL','VACINACAO_ANTIRRABICA')),
  CONSTRAINT ck_integracao_situacao CHECK (situacao IN ('PENDENTE','ENVIADA','CONFIRMADA','FALHA')),
  CONSTRAINT ck_integracao_vacina CHECK (
    (tipo_operacao = 'VACINACAO_ANTIRRABICA' AND vacina_id IS NOT NULL) OR
    (tipo_operacao <> 'VACINACAO_ANTIRRABICA' AND vacina_id IS NULL)),
  CONSTRAINT ck_integracao_tentativas CHECK (tentativas >= 0)
) {ENGINE}"""),
]

CLINICA_INDICES = [
    "CREATE INDEX idx_animal_tutor ON animal (tutor_id)",
    "CREATE INDEX idx_consulta_animal_data ON consulta (animal_id, data_hora)",
    "CREATE INDEX idx_vacina_animal_data ON vacina (animal_id, data_aplicacao)",
    "CREATE INDEX idx_integracao_situacao ON integracao_governo (situacao)",
    "CREATE INDEX idx_integracao_animal ON integracao_governo (animal_id)",
]

# --------------------------------------------------------------------------
# Banco do GOVERNO SIMULADO  (sdm_governo) — persistência própria e independente
# --------------------------------------------------------------------------
GOVERNO_TABELAS = [
    ("gov_animal", """
CREATE TABLE gov_animal (
  id {PK},
  microchip VARCHAR(15) NOT NULL,
  nome VARCHAR(80) NOT NULL,
  especie VARCHAR(60) NOT NULL,
  raca VARCHAR(80) NULL,
  sexo VARCHAR(10) NOT NULL,
  data_nascimento DATE NULL,
  tutor_nome VARCHAR(150) NOT NULL,
  tutor_cpf CHAR(11) NOT NULL,
  situacao VARCHAR(10) NOT NULL DEFAULT 'ATIVO',
  criado_em DATETIME NOT NULL,
  atualizado_em DATETIME NOT NULL,
  CONSTRAINT uq_gov_animal_microchip UNIQUE (microchip),
  CONSTRAINT ck_gov_animal_sexo CHECK (sexo IN ('MACHO','FEMEA')),
  CONSTRAINT ck_gov_animal_situacao CHECK (situacao IN ('ATIVO','INATIVO','OBITO'))
) {ENGINE}"""),

    ("gov_operacao", """
CREATE TABLE gov_operacao (
  id {PK},
  protocolo VARCHAR(30) NOT NULL,
  tipo VARCHAR(30) NOT NULL,
  chave_idempotencia VARCHAR(100) NULL,
  microchip VARCHAR(15) NULL,
  status VARCHAR(12) NOT NULL,
  codigo_http INT NOT NULL,
  resposta TEXT NOT NULL,
  criada_em DATETIME NOT NULL,
  CONSTRAINT uq_gov_operacao_protocolo UNIQUE (protocolo),
  CONSTRAINT uq_gov_operacao_chave UNIQUE (chave_idempotencia),
  CONSTRAINT ck_gov_operacao_tipo CHECK (tipo IN
    ('CADASTRO_ANIMAL','ATUALIZACAO_ANIMAL','VACINACAO_ANTIRRABICA')),
  CONSTRAINT ck_gov_operacao_status CHECK (status IN ('PROCESSADA','REJEITADA'))
) {ENGINE}"""),

    ("gov_vacinacao_antirrabica", """
CREATE TABLE gov_vacinacao_antirrabica (
  id {PK},
  protocolo VARCHAR(30) NOT NULL,
  microchip VARCHAR(15) NOT NULL,
  id_aplicacao_origem INT NOT NULL,
  animal_origem_id INT NOT NULL,
  animal_nome VARCHAR(80) NOT NULL,
  data_aplicacao DATE NOT NULL,
  vacina VARCHAR(100) NOT NULL,
  fabricante VARCHAR(100) NOT NULL,
  numero_lote VARCHAR(50) NOT NULL,
  veterinario_nome VARCHAR(150) NOT NULL,
  veterinario_crmv VARCHAR(20) NOT NULL,
  criada_em DATETIME NOT NULL,
  CONSTRAINT uq_gov_vac_origem UNIQUE (microchip, id_aplicacao_origem),
  CONSTRAINT uq_gov_vac_natural UNIQUE (microchip, data_aplicacao, numero_lote),
  CONSTRAINT fk_gov_vac_operacao FOREIGN KEY (protocolo) REFERENCES gov_operacao (protocolo)
) {ENGINE}"""),
]

GOVERNO_INDICES = [
    "CREATE INDEX idx_gov_operacao_microchip ON gov_operacao (microchip)",
    "CREATE INDEX idx_gov_vac_microchip ON gov_vacinacao_antirrabica (microchip)",
]


def _render(texto, dialeto):
    for token, valor in DIALETOS[dialeto].items():
        texto = texto.replace("{" + token + "}", valor)
    return texto.strip()


def _ddl(tabelas, indices, dialeto):
    cmds = [_render(sql, dialeto) for _, sql in tabelas]
    cmds += indices
    return cmds


def comandos_clinica(dialeto):
    """Lista de comandos CREATE (tabelas + índices) do banco da clínica."""
    return _ddl(CLINICA_TABELAS, CLINICA_INDICES, dialeto)


def comandos_governo(dialeto):
    """Lista de comandos CREATE (tabelas + índices) do banco do governo simulado."""
    return _ddl(GOVERNO_TABELAS, GOVERNO_INDICES, dialeto)


def ordem_drop_clinica():
    return [nome for nome, _ in reversed(CLINICA_TABELAS)]


def ordem_drop_governo():
    return [nome for nome, _ in reversed(GOVERNO_TABELAS)]
