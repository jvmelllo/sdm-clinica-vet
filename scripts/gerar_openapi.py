"""Gera a documentação OpenAPI 3 (Swagger) das duas APIs e o resumo em Markdown.

Saídas:
    docs/openapi/clinica.yaml     API privada da clínica   (servida em /docs e /openapi.yaml, porta 5000)
    docs/openapi/governo.yaml     API governamental simulada (porta 5001)
    docs/03-endpoints.md          tabela de endpoints + exemplos de uso

Uso:  python scripts/gerar_openapi.py
O teste tests/test_openapi.py garante que os caminhos documentados são exatamente os que o Flask registra.
"""
import os
import re

import yaml

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================ helpers de esquema
S_ = {"type": "string"}
I_ = {"type": "integer"}
N_ = {"type": "number"}
B_ = {"type": "boolean"}
D_ = {"type": "string", "format": "date", "example": "2026-11-05"}
DT_ = {"type": "string", "example": "2026-11-05 14:30:00", "description": "AAAA-MM-DD HH:MM:SS (horário local da clínica)"}


def ref(nome):
    return {"$ref": f"#/components/schemas/{nome}"}


def arr(item):
    return {"type": "array", "items": item}


def enum(*valores, desc=None):
    d = {"type": "string", "enum": list(valores)}
    if desc:
        d["description"] = desc
    return d


def com(base, desc=None, ex=None, nullable=False):
    d = dict(base)
    if desc:
        d["description"] = desc
    if ex is not None:
        d["example"] = ex
    if nullable:
        d["nullable"] = True
    return d


def obj(props, req=(), desc=None, ex=None):
    d = {"type": "object", "properties": props}
    if req:
        d["required"] = list(req)
    if desc:
        d["description"] = desc
    if ex is not None:
        d["example"] = ex
    return d


def extend(*bases, extra=None, req=()):
    d = {"allOf": [ref(b) for b in bases]}
    if extra:
        d["allOf"].append(obj(extra, req))
    return d


# ============================================================================ erros padronizados
ERROS = {
    "400": ("Requisição malformada (JSON ausente/inválido) ou código inválido.", "JSON_INVALIDO"),
    "401": ("Token ausente, inválido, expirado ou sessão encerrada; ou veterinário inativo/sem senha confirmada.", "NAO_AUTENTICADO"),
    "403": ("Acesso bloqueado: veterinário inativo ou senha ainda não confirmada.", "VETERINARIO_INATIVO"),
    "404": ("Recurso não encontrado.", "NAO_ENCONTRADO"),
    "409": ("Conflito com o estado atual (duplicidade, vínculo existente, registro em uso).", "CPF_DUPLICADO"),
    "422": ("Dados inválidos (campo a campo em `detalhes`) ou regra de negócio violada.", "VALIDACAO"),
    "429": ("Muitas tentativas de confirmação de código.", "CODIGO_BLOQUEADO"),
    "502": ("Resposta inesperada do serviço externo.", "CEP_RESPOSTA_INVALIDA"),
    "503": ("Serviço externo ou banco indisponível.", "CEP_INDISPONIVEL"),
    "504": ("Tempo esgotado no serviço externo.", "CEP_TIMEOUT"),
}


def componentes_erro():
    out = {}
    for cod, (desc, exemplo) in ERROS.items():
        out[f"Erro{cod}"] = {
            "description": desc,
            "content": {"application/json": {"schema": ref("Erro"), "example": {"erro": {"codigo": exemplo, "mensagem": desc.split(";")[0].rstrip(".") + "."}}}},
        }
    return out


# ============================================================================ DSL de endpoints
PAGINA = [
    {"name": "limite", "in": "query", "schema": {"type": "integer", "default": 100, "maximum": 500}, "description": "Itens por página."},
    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}, "description": "Deslocamento."},
]


def q(nome, schema, desc):
    return {"name": nome, "in": "query", "schema": schema, "description": desc}


def ep(metodo, caminho, tag, resumo, *, desc="", auth=True, body=None, exemplo=None, ok=("200", None), params=(),
       erros=(), headers=()):
    return dict(metodo=metodo, caminho=caminho, tag=tag, resumo=resumo, desc=desc, auth=auth, body=body, exemplo=exemplo,
                ok=ok, params=list(params), erros=list(erros), headers=list(headers))


def montar_spec(info, servers, tags, schemas, endpoints, seguranca, extras_comp=None):
    paths = {}
    for e in endpoints:
        op = {"tags": [e["tag"]], "summary": e["resumo"]}
        if e["desc"]:
            op["description"] = e["desc"]
        params = []
        for nome in re.findall(r"\{(\w+)\}", e["caminho"]):
            esquema = I_ if nome == "id" else S_
            params.append({"name": nome, "in": "path", "required": True, "schema": esquema})
        params += e["params"] + e["headers"]
        if params:
            op["parameters"] = params
        if e["auth"]:
            op["security"] = [{seguranca[0]: []}]
        else:
            op["security"] = []
        if e["body"]:
            media = {"schema": ref(e["body"]) if isinstance(e["body"], str) else e["body"]}
            if e["exemplo"] is not None:
                media["example"] = e["exemplo"]
            op["requestBody"] = {"required": True, "content": {"application/json": media}}
        status, esquema, *resto = e["ok"]
        resp = {"description": resto[0] if resto else "Sucesso."}
        if esquema is not None:
            resp["content"] = {"application/json": {"schema": ref(esquema) if isinstance(esquema, str) else esquema}}
        respostas = {status: resp}
        automaticos = set(e["erros"])
        if e["auth"]:
            automaticos.add("401")
        if "{" in e["caminho"] and e["auth"]:
            automaticos.add("404")
        if e["body"]:
            automaticos |= {"400", "422"}
        for cod in sorted(automaticos):
            respostas[cod] = {"$ref": f"#/components/responses/Erro{cod}"}
        op["responses"] = respostas
        paths.setdefault(e["caminho"], {})[e["metodo"].lower()] = op
    comp = {"securitySchemes": seguranca[1], "schemas": schemas, "responses": componentes_erro()}
    comp.update(extras_comp or {})
    return {"openapi": "3.0.3", "info": info, "servers": servers, "tags": tags, "paths": paths, "components": comp}


# ============================================================================ API DA CLÍNICA
SIT_ATIVO = enum("ATIVO", "INATIVO")
SIT_CAT = enum("ATIVA", "INATIVA")
SIT_INTEG = enum("PENDENTE", "ENVIADA", "CONFIRMADA", "FALHA", desc="Estados da comunicação com o governo.")
TIPOS_VACINA = enum("ANTIRRABICA", "POLIVALENTE", "TRIPLICE_FELINA", "GRIPE_CANINA", "GIARDIA", "LEISHMANIOSE", "OUTRA",
                    desc="A antirrábica é identificada por ESTE campo, nunca pelo nome da vacina.")
VIAS = enum("SUBCUTANEA", "INTRAMUSCULAR", "INTRANASAL", "ORAL")

CPF_EX = "52998224725"

SCHEMAS_CLINICA = {
    "Erro": obj({"erro": obj({"codigo": S_, "mensagem": S_, "detalhes": {"type": "object", "additionalProperties": True}},
                             ["codigo", "mensagem"])}, ["erro"],
                desc="Formato único de erro de toda a API."),
    # ---- autenticação / veterinários
    "Login": obj({"email": com(S_, ex="ana.souza@clinicavet.example"), "senha": com(S_, ex="Senha@123")}, ["email", "senha"]),
    "LoginResposta": obj({"token": com(S_, "JWT (HS256). Enviar em `Authorization: Bearer <token>`."), "tipo": com(S_, ex="Bearer"),
                          "expira_em": S_, "veterinario": ref("Veterinario")}),
    "ConfirmarSenha": obj({"email": S_, "codigo": com(S_, "Código de 6 dígitos recebido por e-mail (simulado).", "123456")}, ["email", "codigo"]),
    "EmailEntrada": obj({"email": S_}, ["email"]),
    "Mensagem": obj({"mensagem": S_, "codigo_simulado": com(S_, "Só aparece em desenvolvimento (EXPOR_CODIGO_NA_RESPOSTA=1).")}),
    "Veterinario": obj({
        "id": I_, "nome_completo": S_, "cpf": S_, "crmv_numero": S_, "crmv_uf": S_, "email": S_, "telefone": S_,
        "senha_confirmada": B_, "senha_confirmada_em": com(S_, nullable=True), "data_cadastro": S_, "situacao": SIT_ATIVO,
        "ultimo_acesso_em": com(S_, nullable=True)}, desc="Nunca expõe o hash da senha."),
    "VeterinarioNovo": obj({
        "nome_completo": com(S_, ex="Dr. Carlos Pereira"), "cpf": com(S_, ex=CPF_EX), "crmv_numero": com(S_, ex="67890"),
        "crmv_uf": com(S_, ex="SP"), "email": com(S_, ex="carlos.pereira@clinicavet.example"), "telefone": com(S_, ex="11987654321"),
        "senha": com(S_, "Mínimo 8 caracteres com letras e números. Guardada só como hash.", "Senha@456")},
        ["nome_completo", "cpf", "crmv_numero", "crmv_uf", "email", "telefone", "senha"]),
    "VeterinarioCriado": extend("Veterinario", extra={"codigo_simulado": S_}),
    # ---- endereço / tutor
    "CepResposta": obj({"cep": S_, "logradouro": S_, "complemento": S_, "bairro": S_, "cidade": S_, "uf": S_,
                        "codigo_ibge": com(S_, nullable=True), "fonte": com(S_, ex="ViaCEP")}),
    "Endereco": obj({"id": I_, "cep": S_, "logradouro": S_, "numero": S_, "complemento": com(S_, nullable=True), "bairro": S_,
                     "cidade": S_, "uf": S_, "codigo_ibge": com(S_, nullable=True)}),
    "EnderecoNovo": obj({"cep": com(S_, ex="01001000"), "logradouro": com(S_, ex="Praça da Sé"), "numero": com(S_, ex="100"),
                         "complemento": S_, "bairro": com(S_, ex="Sé"), "cidade": com(S_, ex="São Paulo"), "uf": com(S_, ex="SP"),
                         "codigo_ibge": com(S_, "7 dígitos (opcional).", "3550308")},
                        ["cep", "logradouro", "numero", "bairro", "cidade", "uf"]),
    "Tutor": obj({"id": I_, "nome_completo": S_, "cpf": S_, "data_nascimento": D_, "email": S_, "telefone": S_, "endereco_id": I_,
                  "data_cadastro": S_, "situacao": SIT_ATIVO, "endereco": ref("Endereco")}),
    "TutorLista": obj({"id": I_, "nome_completo": S_, "cpf": S_, "data_nascimento": D_, "email": S_, "telefone": S_,
                       "endereco_id": I_, "data_cadastro": S_, "situacao": SIT_ATIVO, "cidade": S_, "uf": S_, "total_animais": I_}),
    "TutorNovo": obj({"nome_completo": com(S_, ex="Maria Oliveira"), "cpf": com(S_, ex=CPF_EX), "data_nascimento": com(D_, ex="1990-05-10"),
                      "email": com(S_, ex="maria.oliveira@example.com"), "telefone": com(S_, ex="11912345678"),
                      "endereco": ref("EnderecoNovo"),
                      "endereco_id": com(I_, "Alternativa a `endereco`: reutiliza um endereço já cadastrado.")},
                     ["nome_completo", "cpf", "data_nascimento", "email", "telefone"],
                     desc="Informe `endereco` (objeto) ou `endereco_id`."),
    # ---- catálogos
    "Especie": obj({"id": I_, "nome": S_, "descricao": com(S_, nullable=True), "situacao": SIT_CAT}),
    "EspecieNova": obj({"nome": com(S_, ex="Hamster"), "descricao": S_}, ["nome"]),
    "Raca": obj({"id": I_, "nome": S_, "descricao": com(S_, nullable=True), "especie_id": I_, "especie_nome": S_, "situacao": SIT_CAT}),
    "RacaNova": obj({"nome": com(S_, ex="Beagle"), "especie_id": I_, "descricao": S_}, ["nome", "especie_id"]),
    # ---- animais / microchip
    "MicrochipAtual": obj({"id": I_, "codigo": com(S_, ex="900123456789012"), "data_vinculo": S_, "veterinario_id": I_, "veterinario_nome": S_},
                          desc="Vínculo vigente (um por animal)."),
    "IntegracaoResumo": obj({
        "situacao_cadastro": enum("PENDENTE", "ENVIADA", "CONFIRMADA", "FALHA", "SEM_MICROCHIP", "NAO_SOLICITADO"),
        "protocolo_cadastro": com(S_, nullable=True), "sincronizado": B_, "pendencias": I_}),
    "Animal": obj({
        "id": I_, "nome": S_, "data_nascimento": com(D_, nullable=True), "idade_estimada_meses": com(I_, nullable=True),
        "sexo": enum("MACHO", "FEMEA"), "cor": S_, "peso_atual": N_, "tutor_id": I_, "especie_id": I_,
        "raca_id": com(I_, "Nulo = sem raça definida (SRD).", nullable=True), "situacao": enum("ATIVO", "INATIVO", "OBITO"),
        "data_cadastro": S_, "tutor_nome": S_, "especie_nome": S_, "raca_nome": com(S_, nullable=True), "sem_raca_definida": B_,
        "microchip_atual": {**ref("MicrochipAtual"), "nullable": True}, "integracao_governo": ref("IntegracaoResumo")}),
    "AnimalLista": obj({
        "id": I_, "nome": S_, "sexo": S_, "cor": S_, "peso_atual": N_, "tutor_id": I_, "tutor_nome": S_, "especie_id": I_,
        "especie_nome": S_, "raca_id": com(I_, nullable=True), "raca_nome": com(S_, nullable=True), "situacao": S_,
        "microchip": com(S_, "Código do microchip vigente, se houver.", nullable=True)}),
    "AnimalNovo": obj({
        "nome": com(S_, ex="Thor"), "tutor_id": I_, "especie_id": I_,
        "raca_id": com(I_, "Opcional. Deve pertencer à espécie informada."), "sexo": enum("MACHO", "FEMEA"), "cor": com(S_, ex="Caramelo"),
        "peso_atual": com(N_, ex=12.5), "data_nascimento": D_,
        "idade_estimada_meses": com(I_, "Use quando a data de nascimento é desconhecida."),
        "situacao": enum("ATIVO", "INATIVO", "OBITO")},
        ["nome", "tutor_id", "especie_id", "sexo", "cor", "peso_atual"], desc="Informe `data_nascimento` OU `idade_estimada_meses`."),
    "MicrochipNovo": obj({"codigo": com(S_, "Exatamente 15 dígitos (ISO 11784/11785).", "900123456789012"),
                          "substituir": com(B_, "true para trocar o microchip vigente (histórico é preservado)."),
                          "motivo_substituicao": com(S_, "Obrigatório quando `substituir=true`.")}, ["codigo"]),
    "VinculoMicrochip": obj({"id": I_, "animal_id": I_, "codigo_microchip": S_, "data_vinculo": S_, "situacao": enum("ATIVO", "SUBSTITUIDO"),
                             "data_substituicao": com(S_, nullable=True), "motivo_substituicao": com(S_, nullable=True),
                             "veterinario_id": I_, "veterinario_nome": S_, "crmv_numero": S_, "crmv_uf": S_}),
    "MicrochipResposta": obj({"vinculo": ref("VinculoMicrochip"), "animal": ref("Animal"), "integracao_governo": ref("IntegracaoEnvio")},
                             desc="O microchip fica gravado mesmo que o governo esteja fora do ar (situação PENDENTE)."),
    # ---- integração
    "Integracao": obj({
        "id": I_, "animal_id": I_, "vacina_id": com(I_, nullable=True), "vinculo_microchip_id": com(I_, nullable=True),
        "tipo_operacao": enum("CADASTRO_ANIMAL", "ATUALIZACAO_ANIMAL", "VACINACAO_ANTIRRABICA"),
        "protocolo_externo": com(S_, "Protocolo devolvido pelo governo.", nullable=True),
        "chave_idempotencia": com(S_, "Enviada em `Idempotency-Key`: reenviar nunca duplica."), "situacao": SIT_INTEG,
        "solicitada_em": S_, "respondida_em": com(S_, nullable=True), "ultima_tentativa_em": com(S_, nullable=True),
        "tentativas": I_, "mensagem_erro": com(S_, nullable=True), "animal_nome": S_, "microchip": com(S_, nullable=True),
        "payload_enviado": {"type": "object", "description": "Só no detalhe (GET /api/integracoes/{id})."}}),
    "IntegracaoEnvio": {"allOf": [ref("Integracao"), obj({"ultima_resposta": obj({
        "categoria": enum("OK", "INDISPONIVEL", "INCERTO", "REJEITADO"), "status_http": com(I_, nullable=True),
        "corpo": {"type": "object"}, "repeticao_idempotente": com(B_, "true quando o governo reconheceu a repetição e devolveu o mesmo protocolo.")},
        desc="Nulo se nada foi enviado (ex.: já confirmada).")})]},
    "ReprocessarResumo": obj({"analisadas": I_, "confirmadas": I_, "ainda_pendentes": I_, "falhas": I_}),
    "AnimalIntegracaoGoverno": {"allOf": [ref("IntegracaoResumo"), obj({"operacoes": arr(ref("Integracao"))})]},
    "SincronizarResposta": obj({"operacao": ref("IntegracaoEnvio"), "integracao_governo": ref("IntegracaoResumo")}),
    # ---- consultas
    "Consulta": obj({
        "id": I_, "animal_id": I_, "veterinario_id": I_, "data_hora": S_, "motivo": S_, "anamnese": com(S_, nullable=True),
        "sintomas": com(S_, nullable=True), "diagnostico": com(S_, nullable=True), "tratamento": com(S_, nullable=True),
        "prescricao_medicamentos": com(S_, nullable=True), "observacoes": com(S_, nullable=True), "peso_kg": com(N_, nullable=True),
        "temperatura_c": com(N_, nullable=True), "situacao": enum("AGENDADA", "REALIZADA", "CANCELADA", "NAO_COMPARECEU"),
        "animal_nome": S_, "veterinario_nome": S_}),
    "ConsultaNova": obj({
        "animal_id": I_, "veterinario_id": com(I_, "Opcional: padrão = veterinário autenticado."),
        "data_hora": com(S_, ex="2026-11-05 14:30"), "motivo": com(S_, ex="Vacinação e check-up"), "anamnese": S_, "sintomas": S_,
        "diagnostico": S_, "tratamento": S_, "prescricao_medicamentos": S_, "observacoes": S_,
        "peso_kg": com(N_, "Se a consulta é REALIZADA, atualiza o peso atual do animal."), "temperatura_c": com(N_, ex=38.5),
        "situacao": enum("AGENDADA", "REALIZADA", "CANCELADA", "NAO_COMPARECEU")},
        ["animal_id", "data_hora", "motivo"]),
    # ---- vacinas
    "ComunicacaoVacina": obj({"obrigatoria": com(B_, "true somente para antirrábica APLICADA."), "integracao_id": com(I_, nullable=True),
                              "situacao": {**SIT_INTEG, "nullable": True}, "protocolo": com(S_, nullable=True), "tentativas": com(I_, nullable=True)}),
    "Vacina": obj({
        "id": I_, "animal_id": I_, "veterinario_id": I_, "nome_vacina": S_, "tipo_vacina": TIPOS_VACINA, "antirrabica": B_,
        "fabricante": com(S_, nullable=True), "numero_lote": com(S_, nullable=True), "data_aplicacao": D_, "dose": S_,
        "via_aplicacao": VIAS, "data_proxima_dose": com(D_, nullable=True), "validade_lote": com(D_, nullable=True),
        "observacoes": com(S_, nullable=True), "situacao": enum("AGENDADA", "APLICADA", "CANCELADA"),
        "animal_nome": S_, "veterinario_nome": S_, "comunicacao_governo": ref("ComunicacaoVacina")}),
    "VacinaNova": obj({
        "animal_id": I_, "nome_vacina": com(S_, ex="Antirrábica anual"), "tipo_vacina": TIPOS_VACINA, "dose": com(S_, ex="Dose única"),
        "via_aplicacao": VIAS, "data_aplicacao": D_, "fabricante": com(S_, "Obrigatório se APLICADA.", "Zoetis"),
        "numero_lote": com(S_, "Obrigatório se APLICADA.", "L2026-0457"), "validade_lote": com(D_, "Obrigatória se APLICADA.", "2027-08-31"),
        "data_proxima_dose": D_, "observacoes": S_, "situacao": com(enum("APLICADA", "AGENDADA"), "Padrão: APLICADA."),
        "veterinario_id": com(I_, "Opcional: padrão = veterinário autenticado.")},
        ["animal_id", "nome_vacina", "tipo_vacina", "dose", "via_aplicacao", "data_aplicacao"]),
    "VacinaAplicar": obj({"data_aplicacao": D_, "fabricante": S_, "numero_lote": S_, "validade_lote": D_, "data_proxima_dose": D_,
                          "observacoes": S_, "dose": S_, "via_aplicacao": VIAS},
                         ["fabricante", "numero_lote", "validade_lote"], desc="Converte uma vacina AGENDADA em APLICADA."),
    "VacinaResposta": obj({"vacina": ref("Vacina"), "comunicacao_governo": {**ref("IntegracaoEnvio"), "nullable": True,
                           "description": "Nulo quando a vacina não exige comunicação (não antirrábica ou ainda agendada)."}},
                          desc="Separa o registro LOCAL (já gravado) da CONFIRMAÇÃO do governo (pode estar PENDENTE)."),
    "ComunicacaoGoverno": obj({"vacina_id": I_, "antirrabica": B_, "registro_local": S_, "comunicacao_obrigatoria": B_,
                               "confirmacao_governo": enum("PENDENTE", "ENVIADA", "CONFIRMADA", "FALHA", "NAO_APLICAVEL", "NAO_SOLICITADA"),
                               "observacao": S_, "integracao": {**ref("Integracao"), "nullable": True}}),
    "ProximaDose": obj({"vacina_id": I_, "nome_vacina": S_, "tipo_vacina": S_, "dose": S_, "dose_anterior": S_, "data_prevista": D_,
                        "origem": enum("REFORCO_PREVISTO", "AGENDADA"), "dias_para_a_data": I_,
                        "situacao_prazo": enum("ATRASADA", "HOJE", "NO_PRAZO")}),
    # ---- apoio
    "Status": obj({"api": S_, "banco": enum("ok", "indisponivel"), "governo": enum("ok", "indisponivel")}),
    "ResumoPainel": obj({"tutores_ativos": I_, "animais_ativos": I_, "consultas_hoje": I_, "consultas_agendadas": I_,
                         "vacinas_com_reforco_atrasado": I_,
                         "integracoes": obj({"PENDENTE": I_, "ENVIADA": I_, "CONFIRMADA": I_, "FALHA": I_}), "governo_disponivel": B_}),
    "Simulacao": obj({"modo": enum("NORMAL", "INDISPONIVEL", "RESPOSTA_LENTA"), "atraso_s": N_, "falhar_proximas": I_}),
    "SimulacaoNova": obj({"modo": enum("NORMAL", "INDISPONIVEL", "RESPOSTA_LENTA"), "atraso_s": com(N_, ex=6),
                          "falhar_proximas": com(I_, "As próximas N chamadas falham com 503 e depois volta ao normal.", 0)}),
}


def crud(base, tag, nome, schema, schema_novo, *, lista=None, filtros=(), reativar=True, extra_desc=""):
    """Gera os endpoints padrão (listar/criar/obter/atualizar/inativar/reativar) de uma entidade."""
    plural = f"/api/{base}"
    e = [
        ep("GET", plural, tag, f"Listar {nome}", params=[*filtros, *PAGINA], ok=("200", arr(ref(lista or schema)))),
        ep("POST", plural, tag, f"Cadastrar {nome}", body=schema_novo, ok=("201", schema, "Criado."), erros=("409",), desc=extra_desc),
        ep("GET", f"{plural}/{{id}}", tag, f"Consultar {nome}", ok=("200", schema)),
        ep("PUT", f"{plural}/{{id}}", tag, f"Alterar {nome}", body=schema_novo, ok=("200", schema), erros=("409",)),
        ep("DELETE", f"{plural}/{{id}}", tag, f"Inativar {nome} (exclusão lógica)", ok=("200", schema),
           erros=("409",), desc="Nunca apaga fisicamente: o histórico clínico e a integridade referencial são preservados."),
    ]
    if reativar:
        e.append(ep("POST", f"{plural}/{{id}}/reativar", tag, f"Reativar {nome}", ok=("200", schema), erros=("409", "422")))
    return e


F_SIT = q("situacao", enum("ATIVO", "INATIVO"), "Filtra por situação.")
F_SIT_CAT = q("situacao", enum("ATIVA", "INATIVA"), "Filtra por situação.")
F_Q = q("q", S_, "Busca por texto.")

ENDPOINTS_CLINICA = [
    ep("GET", "/api/status", "Sistema", "Saúde da API, do banco e do governo", auth=False, ok=("200", "Status")),
    ep("GET", "/api/resumo", "Sistema", "Indicadores do painel", ok=("200", "ResumoPainel")),
    # ---- autenticação
    ep("POST", "/api/auth/login", "Autenticação", "Login do veterinário",
       desc="Gera um JWT revogável. Bloqueia veterinário **inativo** e **sem senha confirmada**. Credenciais erradas devolvem sempre a mesma "
            "mensagem (não revela se o e-mail existe); o motivo do bloqueio só aparece a quem acertou a senha.",
       auth=False, body="Login", exemplo={"email": "ana.souza@clinicavet.example", "senha": "Senha@123"},
       ok=("200", "LoginResposta"), erros=("401", "403")),
    ep("POST", "/api/auth/logout", "Autenticação", "Encerra (revoga) a sessão atual", ok=("200", "Mensagem")),
    ep("GET", "/api/auth/me", "Autenticação", "Dados do veterinário autenticado", ok=("200", "Veterinario")),
    ep("POST", "/api/auth/confirmar-senha", "Autenticação", "Confirma a senha com o código de 6 dígitos",
       desc="O código é guardado como HMAC, expira e tem limite de tentativas (429 ao exceder).",
       auth=False, body="ConfirmarSenha", ok=("200", "Mensagem"), erros=("429",)),
    ep("POST", "/api/auth/reenviar-codigo", "Autenticação", "Reenvia o código de confirmação (e-mail simulado)",
       desc="Resposta sempre igual, exista ou não o e-mail. O e-mail simulado é gravado em `data/emails_simulado.log`.",
       auth=False, body="EmailEntrada", ok=("202", "Mensagem", "Aceito.")),
    # ---- veterinários
    *crud("veterinarios", "Veterinários", "veterinário", "Veterinario", "VeterinarioNovo", filtros=[F_SIT, F_Q]),
    # ---- CEP / endereços
    ep("GET", "/api/cep/{cep}", "Endereços e CEP", "Consulta o ViaCEP",
       desc="Consome a API pública ViaCEP com timeout. Falhas: 404 CEP inexistente, 504 timeout, 503 serviço fora do ar, 502 resposta inválida. "
            "Em todas o frontend permite preencher o endereço manualmente.",
       ok=("200", "CepResposta"), erros=("404", "422", "502", "503", "504")),
    ep("POST", "/api/enderecos", "Endereços e CEP", "Cadastrar endereço", body="EnderecoNovo", ok=("201", "Endereco", "Criado.")),
    ep("GET", "/api/enderecos/{id}", "Endereços e CEP", "Consultar endereço", ok=("200", "Endereco")),
    ep("PUT", "/api/enderecos/{id}", "Endereços e CEP", "Alterar endereço", body="EnderecoNovo", ok=("200", "Endereco")),
    # ---- tutores
    *crud("tutores", "Tutores", "tutor", "Tutor", "TutorNovo", lista="TutorLista", filtros=[F_SIT, F_Q],
          extra_desc="CPF único (409 `CPF_DUPLICADO`). Aceita o endereço aninhado."),
    # ---- catálogos
    *crud("especies", "Espécies e raças", "espécie", "Especie", "EspecieNova", filtros=[F_SIT_CAT]),
    *crud("racas", "Espécies e raças", "raça", "Raca", "RacaNova", filtros=[q("especie_id", I_, "Filtra pela espécie."), F_SIT_CAT]),
    # ---- animais
    *crud("animais", "Animais", "animal", "Animal", "AnimalNovo", lista="AnimalLista",
          filtros=[F_SIT, F_Q, q("tutor_id", I_, "Animais de um tutor."), q("especie_id", I_, "Por espécie."), q("microchip", S_, "Por código de microchip.")],
          extra_desc="O animal nasce SEM microchip; vincule-o em `POST /api/animais/{id}/microchip`."),
    ep("POST", "/api/animais/{id}/microchip", "Microchip", "Vincular ou substituir o microchip RFID",
       desc="Código de 15 dígitos, **único e nunca reutilizável**. Um animal tem 1 microchip vigente; a troca exige `substituir=true` e o motivo, "
            "e o vínculo antigo é preservado no histórico. O cadastro é comunicado ao governo (se estiver fora do ar, fica PENDENTE).",
       body="MicrochipNovo", exemplo={"codigo": "900123456789012"}, ok=("201", "MicrochipResposta", "Vinculado."), erros=("409",)),
    ep("GET", "/api/animais/{id}/microchips", "Microchip", "Histórico de microchips do animal", ok=("200", arr(ref("VinculoMicrochip")))),
    ep("GET", "/api/animais/{id}/consultas", "Consultas", "Histórico de consultas do animal", params=PAGINA, ok=("200", arr(ref("Consulta")))),
    ep("GET", "/api/animais/{id}/vacinas", "Vacinas", "Histórico de vacinação (com status no governo)", ok=("200", arr(ref("Vacina")))),
    ep("GET", "/api/animais/{id}/vacinas/proximas-doses", "Vacinas", "Próximas doses e reforços", ok=("200", arr(ref("ProximaDose")))),
    ep("GET", "/api/animais/{id}/integracao-governo", "Integração com o governo", "Situação da integração do animal + operações",
       ok=("200", "AnimalIntegracaoGoverno")),
    ep("POST", "/api/animais/{id}/sincronizar", "Integração com o governo", "Sincronização manual com o governo",
       desc="Reenvia o cadastro pendente ou comunica a atualização dos dados.", ok=("200", "SincronizarResposta"), erros=("422",)),
    # ---- consultas
    ep("GET", "/api/consultas", "Consultas", "Listar consultas",
       params=[q("animal_id", I_, "Do animal."), q("situacao", enum("AGENDADA", "REALIZADA", "CANCELADA", "NAO_COMPARECEU"), "Por situação."), *PAGINA],
       ok=("200", arr(ref("Consulta")))),
    ep("POST", "/api/consultas", "Consultas", "Registrar consulta", body="ConsultaNova", ok=("201", "Consulta", "Criada."),
       exemplo={"animal_id": 1, "data_hora": "2026-11-05 14:30", "motivo": "Check-up", "diagnostico": "Saudável", "peso_kg": 12.8, "situacao": "REALIZADA"}),
    ep("GET", "/api/consultas/{id}", "Consultas", "Consultar consulta", ok=("200", "Consulta")),
    ep("PUT", "/api/consultas/{id}", "Consultas", "Alterar consulta", body="ConsultaNova", ok=("200", "Consulta"), erros=("409",)),
    ep("DELETE", "/api/consultas/{id}", "Consultas", "Cancelar consulta",
       desc="Consulta REALIZADA faz parte do histórico clínico e não pode ser cancelada (409).", ok=("200", "Consulta"), erros=("409",)),
    # ---- vacinas
    ep("POST", "/api/vacinas", "Vacinas", "Registrar vacina",
       desc="Se for **antirrábica aplicada**: exige microchip ativo (422 `ANIMAL_SEM_MICROCHIP`), grava o registro local junto com a solicitação PENDENTE "
            "(outbox, mesma transação) e só então comunica o governo. A resposta distingue *vacina registrada* de *governo confirmou*. "
            "Vacinas de outros tipos não geram comunicação.",
       body="VacinaNova", ok=("201", "VacinaResposta", "Registrada."), erros=("422",),
       exemplo={"animal_id": 1, "nome_vacina": "Antirrábica anual", "tipo_vacina": "ANTIRRABICA", "dose": "Dose única",
                "via_aplicacao": "SUBCUTANEA", "data_aplicacao": "2026-11-05", "fabricante": "Zoetis", "numero_lote": "L2026-0457",
                "validade_lote": "2027-08-31", "data_proxima_dose": "2027-11-05"}),
    ep("GET", "/api/vacinas/{id}", "Vacinas", "Consultar vacina", ok=("200", "Vacina")),
    ep("POST", "/api/vacinas/{id}/aplicar", "Vacinas", "Aplicar uma vacina agendada",
       desc="Informa lote e validade; se for antirrábica, comunica ao governo.", body="VacinaAplicar", ok=("200", "VacinaResposta"), erros=("409", "422")),
    ep("DELETE", "/api/vacinas/{id}", "Vacinas", "Cancelar vacina agendada", desc="Vacina já APLICADA não pode ser cancelada (409).",
       ok=("200", "Vacina"), erros=("409",)),
    ep("GET", "/api/vacinas/{id}/comunicacao-governo", "Vacinas", "Estado da comunicação ao governo",
       desc="Mostra separadamente o registro local e a confirmação externa (PENDENTE/ENVIADA/CONFIRMADA/FALHA/NAO_APLICAVEL).",
       ok=("200", "ComunicacaoGoverno")),
    # ---- integrações
    ep("GET", "/api/integracoes", "Integração com o governo", "Listar comunicações com o governo",
       params=[q("situacao", SIT_INTEG, "Por situação."), q("tipo_operacao", enum("CADASTRO_ANIMAL", "ATUALIZACAO_ANIMAL", "VACINACAO_ANTIRRABICA"), "Por tipo."),
               q("animal_id", I_, "Do animal.")], ok=("200", arr(ref("Integracao")))),
    ep("GET", "/api/integracoes/{id}", "Integração com o governo", "Detalhe de uma comunicação (com o payload enviado)", ok=("200", "Integracao")),
    ep("POST", "/api/integracoes/{id}/reenviar", "Integração com o governo", "Reenviar uma comunicação",
       desc="Reenvio manual. Uma operação já CONFIRMADA só é reenviada com `?forcar=true`, o que demonstra a **idempotência**: o governo "
            "reconhece a repetição e devolve o mesmo protocolo, sem duplicar.",
       params=[q("forcar", B_, "Reenvia mesmo uma operação já confirmada.")], ok=("200", "IntegracaoEnvio")),
    ep("POST", "/api/integracoes/reprocessar-pendentes", "Integração com o governo", "Reprocessar todas as pendências",
       desc="Reenvia PENDENTE/ENVIADA. Se o governo seguir fora do ar, não insiste nas demais.", ok=("200", "ReprocessarResumo")),
    # ---- demonstração
    ep("GET", "/api/demo/governo/simulacao", "Demonstração", "Ver o modo de falha do governo simulado",
       desc="Disponível só com `DEMO_SIMULACAO=1`. A chave da API governamental fica no servidor.", ok=("200", "Simulacao"), erros=("503",)),
    ep("PUT", "/api/demo/governo/simulacao", "Demonstração", "Provocar indisponibilidade / lentidão do governo simulado",
       body="SimulacaoNova", exemplo={"modo": "INDISPONIVEL"}, ok=("200", "Simulacao"), erros=("503",)),
]

TAGS_CLINICA = [{"name": n, "description": d} for n, d in [
    ("Sistema", "Saúde e indicadores."), ("Autenticação", "Login com hash + código de confirmação; JWT revogável."),
    ("Veterinários", "Profissionais com acesso ao sistema."), ("Endereços e CEP", "Endereços e consumo do ViaCEP."),
    ("Tutores", "Responsáveis pelos animais."), ("Espécies e raças", "Catálogos."), ("Animais", "Pacientes."),
    ("Microchip", "Vínculo e histórico do microchip RFID."), ("Consultas", "Histórico clínico."),
    ("Vacinas", "Vacinação; a antirrábica é comunicada obrigatoriamente ao governo."),
    ("Integração com o governo", "Controle de PENDENTE → ENVIADA → CONFIRMADA | FALHA, reenvio e idempotência."),
    ("Demonstração", "Apoio à apresentação (somente desenvolvimento).")]]

SPEC_CLINICA = montar_spec(
    {"title": "API da Clínica Veterinária (A3 – SDM)", "version": "1.0.0",
     "description": ("API REST **privada** do sistema de gestão da clínica veterinária (projeto acadêmico).\n\n"
                     "* Autenticação: `POST /api/auth/login` devolve um JWT; use **Authorize** com `Bearer <token>`.\n"
                     "* Erros seguem sempre `{\"erro\": {\"codigo\", \"mensagem\", \"detalhes\"}}`.\n"
                     "* Exclusão é **lógica** (DELETE inativa); listagens devolvem arrays e aceitam `limite`/`offset`.\n"
                     "* Dados e integrações governamentais são **fictícios/simulados**.")},
    [{"url": "http://localhost:5000", "description": "Execução local"}], TAGS_CLINICA, SCHEMAS_CLINICA, ENDPOINTS_CLINICA,
    ("bearerAuth", {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}))

# ============================================================================ API GOVERNAMENTAL
RESP_OP = obj({"protocolo": com(S_, ex="GOV-20261105-9D602A0D"), "status": enum("PROCESSADA", "REJEITADA"),
               "tipo": enum("CADASTRO_ANIMAL", "ATUALIZACAO_ANIMAL", "VACINACAO_ANTIRRABICA"), "microchip": S_, "mensagem": S_,
               "repetida": com(B_, "true quando é a repetição de uma operação já processada (mesma Idempotency-Key)."),
               "animal_cadastrado_no_governo": B_,
               "erro": obj({"codigo": S_, "mensagem": S_, "detalhes": {"type": "object"}})})

SCHEMAS_GOV = {
    "Erro": obj({"erro": obj({"codigo": S_, "mensagem": S_, "detalhes": {"type": "object"}}, ["codigo", "mensagem"])}),
    "AnimalGov": obj({
        "microchip": com(S_, "15 dígitos.", "900123456789012"), "nome": com(S_, ex="Thor"), "especie": com(S_, ex="Cão"), "raca": com(S_, ex="Labrador"),
        "sexo": enum("MACHO", "FEMEA"), "data_nascimento": D_, "situacao": enum("ATIVO", "INATIVO", "OBITO"),
        "tutor": obj({"nome_completo": com(S_, ex="Maria Oliveira"), "cpf": com(S_, "CPF válido (dígitos verificadores).", CPF_EX)},
                     ["nome_completo", "cpf"])}, ["microchip", "nome", "especie", "sexo", "tutor"]),
    "VacinacaoGov": obj({
        "microchip": com(S_, ex="900123456789012"),
        "animal": obj({"id": com(I_, "Id do animal na clínica."), "nome": S_}, ["id", "nome"]),
        "data_aplicacao": D_,
        "vacina": obj({"id_aplicacao": com(I_, "Id da vacina na clínica."), "nome": S_, "fabricante": S_, "numero_lote": S_},
                      ["id_aplicacao", "nome", "fabricante", "numero_lote"]),
        "veterinario": obj({"nome_completo": S_, "crmv": com(S_, ex="12345/SP")}, ["nome_completo", "crmv"])},
        ["microchip", "animal", "data_aplicacao", "vacina", "veterinario"]),
    "RespostaOperacao": RESP_OP,
    "AnimalRegistrado": obj({"id": I_, "microchip": S_, "nome": S_, "especie": S_, "raca": com(S_, nullable=True), "sexo": S_,
                             "data_nascimento": com(D_, nullable=True), "tutor_nome": S_, "tutor_cpf": S_, "situacao": S_,
                             "criado_em": S_, "atualizado_em": S_,
                             "vacinacoes_antirrabicas": arr(obj({"protocolo": S_, "data_aplicacao": D_, "vacina": S_, "fabricante": S_,
                                                                  "numero_lote": S_, "veterinario_nome": S_, "veterinario_crmv": S_}))}),
    "VacinacaoRegistrada": obj({"id": I_, "protocolo": S_, "microchip": S_, "id_aplicacao_origem": I_, "animal_origem_id": I_, "animal_nome": S_,
                                "data_aplicacao": D_, "vacina": S_, "fabricante": S_, "numero_lote": S_, "veterinario_nome": S_,
                                "veterinario_crmv": S_, "criada_em": S_}),
    "OperacaoGov": obj({"protocolo": S_, "tipo": S_, "status": enum("PROCESSADA", "REJEITADA"), "microchip": com(S_, nullable=True),
                        "codigo_http": I_, "criada_em": S_, "resposta": {"type": "object"}},
                       desc="Toda operação, inclusive as rejeitadas, recebe protocolo."),
    "Saude": obj({"servico": S_, "status": enum("ok", "indisponivel"), "modo": S_}),
    "Simulacao": obj({"modo": enum("NORMAL", "INDISPONIVEL", "RESPOSTA_LENTA"), "atraso_s": N_, "falhar_proximas": I_}),
    "SimulacaoNova": obj({"modo": enum("NORMAL", "INDISPONIVEL", "RESPOSTA_LENTA"),
                          "atraso_s": com(N_, "Só em RESPOSTA_LENTA: a operação é gravada e a resposta demora.", 6),
                          "falhar_proximas": com(I_, "As próximas N chamadas recebem 503.", 0)}),
}
H_IDEM = {"name": "Idempotency-Key", "in": "header", "schema": S_, "description": "Reenvios com a mesma chave devolvem a mesma resposta (campo `repetida: true`), sem duplicar."}
H_IDEM_OBR = {**H_IDEM, "required": True}

ENDPOINTS_GOV = [
    ep("GET", "/api/governo/health", "Sistema", "Saúde do serviço", auth=False,
       desc="Devolve 503 quando o modo de simulação é INDISPONIVEL.", ok=("200", "Saude"), erros=("503",)),
    ep("GET", "/api/governo/simulacao", "Simulação de falhas", "Ver o modo atual", ok=("200", "Simulacao")),
    ep("PUT", "/api/governo/simulacao", "Simulação de falhas", "Definir o modo (NORMAL / INDISPONIVEL / RESPOSTA_LENTA)",
       desc="`INDISPONIVEL`: 503 a tudo. `RESPOSTA_LENTA`: processa e grava, mas atrasa a resposta (o cliente pode dar timeout com a operação já gravada). "
            "`falhar_proximas=N`: as próximas N chamadas falham.", body="SimulacaoNova", exemplo={"modo": "INDISPONIVEL"}, ok=("200", "Simulacao")),
    ep("POST", "/api/governo/animais", "Animais", "Cadastrar animal por microchip",
       body="AnimalGov", headers=[H_IDEM], ok=("201", "RespostaOperacao", "Cadastrado."),
       desc="Cadastro idempotente por `Idempotency-Key`. Microchip repetido sem a chave → 409 `ANIMAL_JA_CADASTRADO`.",
       erros=("409", "503")),
    ep("GET", "/api/governo/animais/{microchip}", "Animais", "Consultar animal por microchip (inclui vacinações antirrábicas)",
       ok=("200", "AnimalRegistrado"), erros=("503",)),
    ep("PUT", "/api/governo/animais/{microchip}", "Animais", "Atualizar cadastro do animal", body="AnimalGov", headers=[H_IDEM],
       ok=("200", "RespostaOperacao"), erros=("503",)),
    ep("POST", "/api/governo/vacinacoes-antirrabicas", "Vacinações antirrábicas", "Receber vacinação antirrábica",
       desc="`Idempotency-Key` **obrigatório**. Mesma vacinação com outra chave → 409 `VACINACAO_DUPLICADA` (não duplica). Gera protocolo.",
       body="VacinacaoGov", headers=[H_IDEM_OBR], ok=("201", "RespostaOperacao", "Registrada."), erros=("400", "409", "503")),
    ep("GET", "/api/governo/vacinacoes-antirrabicas", "Vacinações antirrábicas", "Listar vacinações recebidas",
       params=[q("microchip", S_, "Filtra por microchip.")], ok=("200", arr(ref("VacinacaoRegistrada"))), erros=("503",)),
    ep("GET", "/api/governo/operacoes/{protocolo}", "Protocolos", "Consultar uma operação pelo protocolo", ok=("200", "OperacaoGov"), erros=("503",)),
]

SPEC_GOV = montar_spec(
    {"title": "API Governamental SIMULADA (A3 – SDM)", "version": "1.0.0",
     "description": ("**Serviço fictício**, criado só para o projeto acadêmico; não é integração com nenhum sistema oficial.\n\n"
                     "Recebe cadastro de animais por microchip e vacinações antirrábicas, devolve protocolos e permite **simular falhas** "
                     "(indisponibilidade, resposta lenta, erros de validação) para demonstrar pendência, reenvio e idempotência.\n\n"
                     "Autenticação: cabeçalho `X-API-Key` (chave de demonstração em `.env.example`).")},
    [{"url": "http://localhost:5001", "description": "Execução local"}],
    [{"name": n, "description": d} for n, d in [("Sistema", "Saúde."), ("Simulação de falhas", "Controle da demonstração."), ("Animais", "Cadastro por microchip."),
                                                ("Vacinações antirrábicas", "Comunicação obrigatória."), ("Protocolos", "Rastreio de operações.")]],
    SCHEMAS_GOV, ENDPOINTS_GOV,
    ("apiKey", {"apiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}}))
# o governo devolve também 401 com a chave errada e 503 simulado: já declarados por endpoint; 401 vem de `auth=True`.


# ============================================================================ saída
def gravar_yaml(spec, nome):
    pasta = os.path.join(RAIZ, "docs", "openapi")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        yaml.safe_dump(spec, f, sort_keys=False, allow_unicode=True, width=110)
    return caminho


def tabela(spec, titulo):
    linhas = [f"### {titulo}", ""]
    por_tag = {}
    for caminho, ops in spec["paths"].items():
        for metodo, op in ops.items():
            por_tag.setdefault(op["tags"][0], []).append((caminho, metodo.upper(), op))
    for tag in [t["name"] for t in spec["tags"]]:
        itens = por_tag.get(tag)
        if not itens:
            continue
        linhas += [f"**{tag}**", "", "| Método | Caminho | Auth | Resumo | Sucesso | Erros |", "|---|---|---|---|---|---|"]
        for caminho, metodo, op in itens:
            sucesso = next(c for c in op["responses"] if c.startswith("2"))
            erros = ", ".join(c for c in op["responses"] if not c.startswith("2"))
            auth = "sim" if op.get("security") else "não"
            linhas.append(f"| `{metodo}` | `{caminho}` | {auth} | {op['summary']} | {sucesso} | {erros or '—'} |")
        linhas.append("")
    return "\n".join(linhas)


EXEMPLOS = """## Exemplos de uso (curl)

> Com a pilha no ar (`python scripts/run_all.py`). O token vem do login; `jq` é opcional.

```bash
# 1) Login (contas de demonstração em README.md)
TOKEN=$(curl -s localhost:5000/api/auth/login -H 'Content-Type: application/json' \\
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
"""


def gerar_markdown():
    corpo = ["# 3. Documentação dos endpoints", "",
             "Gerado automaticamente por `scripts/gerar_openapi.py` a partir da mesma especificação OpenAPI usada pelo Swagger. "
             "O teste `tests/test_openapi.py` garante que **todo caminho do Flask está documentado e vice-versa**.", "",
             "* Swagger da clínica: <http://localhost:5000/docs> (arquivo: `docs/openapi/clinica.yaml`)",
             "* Swagger do governo simulado: <http://localhost:5001/docs> (arquivo: `docs/openapi/governo.yaml`)",
             "* Erros: sempre `{\"erro\": {\"codigo\", \"mensagem\", \"detalhes\"}}`. Exclusão é lógica. Listas aceitam `limite`/`offset`.", "",
             "## Endpoints", "", tabela(SPEC_CLINICA, "API privada da clínica (porta 5000)"), tabela(SPEC_GOV, "API governamental simulada (porta 5001)"),
             EXEMPLOS]
    caminho = os.path.join(RAIZ, "docs", "03-endpoints.md")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(corpo))
    return caminho


def caminhos_documentados(spec):
    """Conjunto {(METODO, caminho normalizado)} para comparar com o Flask."""
    return {(m.upper(), re.sub(r"\{\w+\}", "{}", c)) for c, ops in spec["paths"].items() for m in ops}


if __name__ == "__main__":
    for spec, nome in ((SPEC_CLINICA, "clinica.yaml"), (SPEC_GOV, "governo.yaml")):
        print("gerado:", gravar_yaml(spec, nome), f"({len(caminhos_documentados(spec))} operações)")
    print("gerado:", gerar_markdown())
