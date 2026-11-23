"""Integridade imposta pelo PRÓPRIO banco (chaves, unicidade e CHECK), independente da API."""
import sqlite3

import pytest

from database import ddl, seed


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    for cmd in ddl.comandos_clinica("sqlite"):
        c.execute(cmd)
    for cmd in seed.comandos_seed_clinica():
        c.execute(cmd)
    yield c
    c.close()


def _falha(con, sql, trecho=None):
    with pytest.raises(sqlite3.IntegrityError) as e:
        con.execute(sql)
    if trecho:
        assert trecho in str(e.value)


ANIMAL = ("INSERT INTO animal (nome, sexo, cor, peso_atual, tutor_id, especie_id, raca_id, data_nascimento, data_cadastro) "
          "VALUES ('X','MACHO','a',1,{tutor},{esp},{raca},'2020-01-01','2026-01-01 00:00:00')")
VINCULO = ("INSERT INTO vinculo_microchip (animal_id, codigo_microchip, veterinario_id, data_vinculo, situacao, vigente) "
           "VALUES ({animal},'{codigo}',1,'2026-11-01 10:00:00','ATIVO',1)")


def test_raca_precisa_pertencer_a_especie_do_animal(con):
    _falha(con, ANIMAL.format(tutor=1, esp=2, raca=1), "FOREIGN KEY")        # raça 1 é de Cão
    con.execute(ANIMAL.format(tutor=1, esp=1, raca=1))
    con.execute(ANIMAL.format(tutor=1, esp=1, raca="NULL"))                    # sem raça definida é permitido


def test_unicidade_de_cpf_email_e_crmv(con):
    _falha(con, "INSERT INTO tutor (nome_completo,cpf,data_nascimento,email,telefone,endereco_id,data_cadastro) "
                "SELECT 'Z',cpf,'1990-01-01','z@z.com','11999999999',1,'2026-01-01' FROM tutor LIMIT 1", "tutor.cpf")
    _falha(con, "INSERT INTO veterinario (nome_completo,cpf,crmv_numero,crmv_uf,email,telefone,senha_hash,data_cadastro) "
                "VALUES ('V','52998224725','12345','SP','outro@x.com','11999999999','h','2026-01-01')", "crmv")


def test_animal_sempre_tem_tutor_e_dados_minimos(con):
    _falha(con, ANIMAL.format(tutor=999, esp=1, raca=1), "FOREIGN KEY")
    _falha(con, "INSERT INTO animal (nome,sexo,cor,peso_atual,tutor_id,especie_id,data_cadastro) "
                "VALUES ('X','MACHO','a',1,1,1,'2026-01-01 00:00:00')", "ck_animal_idade")
    _falha(con, ANIMAL.format(tutor=1, esp=1, raca=1).replace(",1,", ",0,", 1), "ck_animal_peso")


def test_microchip_unico_e_um_vigente_por_animal(con):
    con.execute(VINCULO.format(animal=1, codigo="985112345678901"))
    _falha(con, VINCULO.format(animal=2, codigo="985112345678901"), "codigo_microchip")      # chip repetido
    _falha(con, VINCULO.format(animal=1, codigo="985112345678902"), "vigente")               # 2º vigente
    con.execute("UPDATE vinculo_microchip SET situacao='SUBSTITUIDO', vigente=NULL WHERE animal_id=1")
    con.execute(VINCULO.format(animal=1, codigo="985112345678902"))                          # histórico + novo vigente
    assert con.execute("SELECT COUNT(*) FROM vinculo_microchip WHERE animal_id=1").fetchone()[0] == 2
    _falha(con, VINCULO.format(animal=1, codigo="123"), "ck_vinculo_codigo")


def test_classificacao_antirrabica_e_estruturada_no_banco(con):
    base = ("INSERT INTO vacina (animal_id,veterinario_id,nome_vacina,tipo_vacina,antirrabica,data_aplicacao,dose,"
            "via_aplicacao,situacao,fabricante,numero_lote,validade_lote) VALUES (1,1,'v','{tipo}',{flag},"
            "'2026-11-01','1','ORAL','APLICADA','f','l','2027-01-01')")
    _falha(con, base.format(tipo="POLIVALENTE", flag=1), "ck_vacina_antirrabica")
    _falha(con, base.format(tipo="ANTIRRABICA", flag=0), "ck_vacina_antirrabica")
    con.execute(base.format(tipo="ANTIRRABICA", flag=1))


def test_vacina_aplicada_exige_lote_e_integracao_e_unica_por_vacina(con):
    _falha(con, "INSERT INTO vacina (animal_id,veterinario_id,nome_vacina,tipo_vacina,antirrabica,data_aplicacao,dose,"
                "via_aplicacao,situacao) VALUES (1,1,'v','POLIVALENTE',0,'2026-11-01','1','ORAL','APLICADA')",
           "ck_vacina_aplicada_completa")
    con.execute(VINCULO.format(animal=1, codigo="985112345678901"))
    con.execute("INSERT INTO vacina (animal_id,veterinario_id,nome_vacina,tipo_vacina,antirrabica,data_aplicacao,dose,"
                "via_aplicacao,situacao,fabricante,numero_lote,validade_lote) VALUES (1,1,'a','ANTIRRABICA',1,"
                "'2026-11-01','1','ORAL','APLICADA','f','l','2027-01-01')")
    vid = con.execute("SELECT MAX(id) FROM vacina").fetchone()[0]
    ins = ("INSERT INTO integracao_governo (animal_id,vacina_id,vinculo_microchip_id,tipo_operacao,chave_idempotencia,"
           "situacao,solicitada_em) VALUES (1,{v},1,'VACINACAO_ANTIRRABICA','{k}','PENDENTE','2026-11-01 10:00:00')")
    con.execute(ins.format(v=vid, k="k1"))
    _falha(con, ins.format(v=vid, k="k2"), "vacina_id")                       # só 1 comunicação por vacina
    _falha(con, ins.format(v=vid + 100, k="k3"), "FOREIGN KEY")
    _falha(con, ins.format(v="NULL", k="k4"), "ck_integracao_vacina")         # vacinação sem vacina


def test_ddl_do_mysql_e_gerado_a_partir_da_mesma_fonte():
    mysql = ddl.comandos_clinica("mysql")
    assert any("AUTO_INCREMENT" in c for c in mysql) and all("AUTOINCREMENT" not in c for c in mysql)
    assert all("ENGINE=InnoDB" in c for c in mysql if c.startswith("CREATE TABLE"))
    assert len([c for c in mysql if c.startswith("CREATE TABLE")]) == 12      # 10 obrigatórias + 2 auxiliares
    assert len([c for c in ddl.comandos_governo("mysql") if c.startswith("CREATE TABLE")]) == 3
