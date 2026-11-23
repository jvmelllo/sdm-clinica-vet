-- SDM - Banco da API governamental SIMULADA (independente do banco da clínica)
-- Arquivo GERADO por scripts/gerar_sql.py a partir de database/ddl.py (não edite à mão).
-- Requer MySQL >= 8.0.16 (as restrições CHECK só são aplicadas a partir dessa versão).

CREATE DATABASE IF NOT EXISTS sdm_governo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sdm_governo;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS gov_vacinacao_antirrabica;
DROP TABLE IF EXISTS gov_operacao;
DROP TABLE IF EXISTS gov_animal;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE gov_animal (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE gov_operacao (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE gov_vacinacao_antirrabica (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_gov_operacao_microchip ON gov_operacao (microchip);

CREATE INDEX idx_gov_vac_microchip ON gov_vacinacao_antirrabica (microchip);
