"""
Dados FICTÍCIOS para demonstração (requisito não funcional: "utilização de
dados fictícios na demonstração"). Nenhum dado aqui pertence a pessoas reais.

Contas de veterinário criadas (senha de todas: Senha@123):
  * ana.souza@clinicavet.example   -> ATIVA, senha confirmada   (login normal)
  * bruno.lima@clinicavet.example  -> INATIVO, senha confirmada (deve ser bloqueado)
  * carla.mendes@clinicavet.example-> ATIVA, senha NÃO confirmada (deve ser bloqueada)

Os animais são criados SEM microchip de propósito: o vínculo do chip é uma das
etapas da demonstração e é ele que dispara o cadastro na API governamental.
"""
from werkzeug.security import generate_password_hash

SENHA_DEMO = "Senha@123"


def cpf_com_digitos(base9: str) -> str:
    """Completa os 9 primeiros dígitos com os dois verificadores do CPF."""
    nums = [int(c) for c in base9]
    for tamanho in (9, 10):
        soma = sum(n * p for n, p in zip(nums, range(tamanho + 1, 1, -1)))
        resto = (soma * 10) % 11
        nums.append(0 if resto == 10 else resto)
    return "".join(str(n) for n in nums)


def _lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _insert(tabela, **cols):
    nomes = ", ".join(cols)
    valores = ", ".join(_lit(v) for v in cols.values())
    return f"INSERT INTO {tabela} ({nomes}) VALUES ({valores})"


def comandos_seed_clinica():
    c = []
    for i, (nome, desc) in enumerate([
        ("Cão", "Canis lupus familiaris"),
        ("Gato", "Felis catus"),
        ("Ave", "Aves de companhia"),
        ("Coelho", "Oryctolagus cuniculus"),
    ], start=1):
        c.append(_insert("especie", id=i, nome=nome, descricao=desc, situacao="ATIVA"))

    racas = [
        (1, "Labrador Retriever", 1), (2, "Poodle", 1), (3, "Golden Retriever", 1),
        (4, "Siamês", 2), (5, "Persa", 2), (6, "Maine Coon", 2),
        (7, "Calopsita", 3), (8, "Periquito", 3),
    ]
    for i, nome, esp in racas:
        c.append(_insert("raca", id=i, nome=nome, descricao=None, especie_id=esp, situacao="ATIVA"))

    enderecos = [
        (1, "01001000", "Praça da Sé", "100", None, "Sé", "São Paulo", "SP", "3550308"),
        (2, "01310100", "Avenida Paulista", "1578", "Apto 82", "Bela Vista", "São Paulo", "SP", "3550308"),
        (3, "01310100", "Avenida Paulista", "900", None, "Bela Vista", "São Paulo", "SP", "3550308"),
    ]
    for i, cep, log, num, comp, bairro, cid, uf, ibge in enderecos:
        c.append(_insert("endereco", id=i, cep=cep, logradouro=log, numero=num, complemento=comp,
                         bairro=bairro, cidade=cid, uf=uf, codigo_ibge=ibge))

    tutores = [
        (1, "Mariana Oliveira Costa", cpf_com_digitos("529982247"), "1988-03-14",
         "mariana.costa@example.com", "11987654321", 1),
        (2, "Carlos Eduardo Pereira", cpf_com_digitos("111444777"), "1975-11-02",
         "carlos.pereira@example.com", "11976543210", 2),
        (3, "Fernanda Lima Santos", cpf_com_digitos("390533447"), "1992-07-25",
         "fernanda.santos@example.com", "11965432109", 3),
    ]
    for i, nome, cpf, nasc, email, tel, end in tutores:
        c.append(_insert("tutor", id=i, nome_completo=nome, cpf=cpf, data_nascimento=nasc, email=email,
                         telefone=tel, endereco_id=end, data_cadastro="2026-10-20 09:00:00", situacao="ATIVO"))

    vets = [
        (1, "Dra. Ana Souza", cpf_com_digitos("987654321"), "12345", "SP",
         "ana.souza@clinicavet.example", "11911110001", "ATIVO", 1),
        (2, "Dr. Bruno Lima", cpf_com_digitos("123456789"), "23456", "RJ",
         "bruno.lima@clinicavet.example", "21922220002", "INATIVO", 1),
        (3, "Dra. Carla Mendes", cpf_com_digitos("246813579"), "34567", "MG",
         "carla.mendes@clinicavet.example", "31933330003", "ATIVO", 0),
    ]
    for i, nome, cpf, crmv, uf, email, tel, sit, conf in vets:
        c.append(_insert(
            "veterinario", id=i, nome_completo=nome, cpf=cpf, crmv_numero=crmv, crmv_uf=uf, email=email,
            telefone=tel, senha_hash=generate_password_hash(SENHA_DEMO), senha_confirmada=conf,
            senha_confirmada_em="2026-10-20 09:05:00" if conf else None,
            data_cadastro="2026-10-20 09:00:00", situacao=sit, ultimo_acesso_em=None))

    animais = [
        (1, "Thor", "2021-05-10", None, "MACHO", "Caramelo", 28.5, 1, 1, 1),
        (2, "Mia", "2022-09-01", None, "FEMEA", "Creme", 4.2, 2, 2, 4),
        (3, "Bolt", None, 36, "MACHO", "Preto", 12.0, 2, 1, None),   # sem raça definida
        (4, "Piu", None, 18, "FEMEA", "Cinza", 0.09, 3, 3, 7),
    ]
    for i, nome, nasc, idade, sexo, cor, peso, tutor, esp, raca in animais:
        c.append(_insert("animal", id=i, nome=nome, data_nascimento=nasc, idade_estimada_meses=idade,
                         sexo=sexo, cor=cor, peso_atual=peso, tutor_id=tutor, especie_id=esp, raca_id=raca,
                         situacao="ATIVO", data_cadastro="2026-10-20 09:30:00"))

    c.append(_insert("consulta", id=1, animal_id=1, veterinario_id=1, data_hora="2026-10-22 10:30:00",
                     motivo="Check-up anual", anamnese="Tutor relata bom apetite e disposição.",
                     sintomas="Nenhum", diagnostico="Animal saudável", tratamento="Manter rotina",
                     prescricao_medicamentos=None, peso_kg=28.5, temperatura_c=38.6,
                     observacoes="Retorno em 12 meses.", situacao="REALIZADA"))
    c.append(_insert("consulta", id=2, animal_id=2, veterinario_id=1, data_hora="2026-11-12 14:00:00",
                     motivo="Avaliação de pelagem", anamnese=None, sintomas=None, diagnostico=None,
                     tratamento=None, prescricao_medicamentos=None, peso_kg=None, temperatura_c=None,
                     observacoes=None, situacao="AGENDADA"))

    # Vacinas NÃO antirrábicas (a antirrábica é aplicada ao vivo na demonstração).
    c.append(_insert("vacina", id=1, animal_id=1, veterinario_id=1, nome_vacina="Polivalente V10",
                     tipo_vacina="POLIVALENTE", antirrabica=0, fabricante="Laboratório Exemplo",
                     numero_lote="PV10-2026-A", data_aplicacao="2026-09-15", dose="2ª dose",
                     via_aplicacao="SUBCUTANEA", data_proxima_dose="2026-10-15",
                     validade_lote="2027-03-01", observacoes=None, situacao="APLICADA"))
    c.append(_insert("vacina", id=2, animal_id=2, veterinario_id=1, nome_vacina="Tríplice Felina",
                     tipo_vacina="TRIPLICE_FELINA", antirrabica=0, fabricante="Laboratório Exemplo",
                     numero_lote="TF-2026-B", data_aplicacao="2026-10-10", dose="Dose única anual",
                     via_aplicacao="SUBCUTANEA", data_proxima_dose="2027-10-10",
                     validade_lote="2027-06-01", observacoes=None, situacao="APLICADA"))
    return c
