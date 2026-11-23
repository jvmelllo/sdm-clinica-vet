"""Teste de fumaça da INTERFACE (navegador real) percorrendo o fluxo da demonstração.

Pré-requisito: a pilha no ar, por exemplo
    python scripts/run_all.py --sqlite --reset --viacep-falso
Execução:
    python scripts/smoke_ui.py            # grava capturas em docs/img/ui/

Fluxo: login (erro e sucesso) -> tutor com ViaCEP (ok, inexistente, timeout) -> animal -> microchip
-> antirrábica CONFIRMADA -> governo fora do ar -> antirrábica PENDENTE -> reenvio -> CONFIRMADA
-> reenvio idempotente -> telas de apoio e versão móvel.
Falha (exit 1) se algum passo não acontecer, se houver erro de JavaScript ou resposta HTTP 5xx.
"""
import os
import re
import sys
import time
from datetime import date, timedelta

from playwright.sync_api import expect, sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from database.seed import cpf_com_digitos  # noqa: E402

BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:5000")
PASTA = os.path.join(RAIZ, "docs", "img", "ui")
os.makedirs(PASTA, exist_ok=True)

problemas, passos = [], []


def passo(msg):
    passos.append(msg)
    print(f"  ok  {msg}")


def foto(page, nome):
    page.screenshot(path=os.path.join(PASTA, f"{nome}.png"))


def toast_contem(page, trecho, limite=8000):
    expect(page.locator("#toasts .toast").filter(has_text=trecho).first).to_be_visible(timeout=limite)


def main():
    sufixo = str(int(time.time()))
    cpf = cpf_com_digitos(sufixo[-9:])
    amanha_ano = (date.today() + timedelta(days=365)).isoformat()

    with sync_playwright() as p:
        navegador = p.chromium.launch(args=["--no-sandbox"])
        ctx = navegador.new_context(viewport={"width": 1280, "height": 800}, locale="pt-BR")
        page = ctx.new_page()
        page.set_default_timeout(8000)
        page.on("pageerror", lambda e: problemas.append(f"erro de JavaScript: {e}\n      {str(getattr(e, 'stack', '') or '')[:700]}"))
        page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text
                and problemas.append(f"console.error: {m.text}"))
        # o único 5xx esperado é o 504 que o próprio roteiro provoca com o CEP de timeout
        page.on("response", lambda r: r.status >= 500 and "/api/cep/11111111" not in r.url
                and problemas.append(f"HTTP {r.status} em {r.url}"))

        # ------------------------------------------------------------ login
        page.goto(BASE)
        expect(page.locator("#f-login")).to_be_visible()
        foto(page, "01-login")
        page.fill("#c_email", "ana.souza@clinicavet.example")
        page.fill("#c_senha", "senha-errada")
        page.click("#f-login button[type=submit]")
        expect(page.locator("#f-login .erro-caixa")).to_contain_text("inválidos")
        passo("login com senha errada mostra erro genérico")

        page.fill("#c_email", "bruno.lima@clinicavet.example")
        page.fill("#c_senha", "Senha@123")
        page.click("#f-login button[type=submit]")
        expect(page.locator("#f-login .erro-caixa")).to_contain_text("inativo")
        passo("veterinário inativo é bloqueado")

        page.fill("#c_email", "carla.mendes@clinicavet.example")
        page.fill("#c_senha", "Senha@123")
        page.click("#f-login button[type=submit]")
        toast_contem(page, "não confirmada")
        expect(page.locator("#f-conf")).to_be_visible()
        page.click("#reenviar")
        expect(page.locator("#aviso-codigo")).to_contain_text(re.compile(r"\d{6}"))   # e-mail simulado (modo dev)
        foto(page, "01b-confirmar-senha")
        passo("veterinário com senha não confirmada é bloqueado e levado à confirmação por código")
        page.click("#voltar")

        page.fill("#c_email", "ana.souza@clinicavet.example")
        page.fill("#c_senha", "Senha@123")
        page.click("#f-login button[type=submit]")
        expect(page.locator("#conteudo h1")).to_be_visible()
        expect(page.locator("#btn-sair")).to_be_visible()
        foto(page, "02-painel")
        passo("login válido abre o painel")

        # ------------------------------------------------------------ tutor + ViaCEP
        page.goto(f"{BASE}/#/tutores")
        page.get_by_role("button", name=re.compile("Novo tutor")).click()
        dlg = page.locator("dialog[open]")
        dlg.locator("#c_nome_completo").fill(f"Tutor Fumaça {sufixo}")
        dlg.locator("#c_cpf").fill(cpf)
        dlg.locator("#c_data_nascimento").fill("1990-05-10")
        dlg.locator("#c_email").fill(f"fumaca{sufixo}@example.com")
        dlg.locator("#c_telefone").fill("11912345678")

        dlg.locator("#c_cep").fill("99999999")
        dlg.locator("#buscar-cep").click()
        expect(dlg.locator("#cep-msg")).to_contain_text("CEP não encontrado")
        passo("ViaCEP: CEP inexistente tratado com mensagem")

        dlg.locator("#c_cep").fill("11111111")
        dlg.locator("#buscar-cep").click()
        expect(dlg.locator("#cep-msg")).to_contain_text("demorou a responder", timeout=12000)
        passo("ViaCEP: timeout tratado, com opção de preencher manualmente")

        dlg.locator("#c_cep").fill("01001000")
        dlg.locator("#buscar-cep").click()
        expect(dlg.locator("#c_logradouro")).to_have_value("Praça da Sé")
        expect(dlg.locator("#c_cidade")).to_have_value("São Paulo")
        dlg.locator("#c_numero").fill("100")
        foto(page, "03-tutor-viacep")
        passo("ViaCEP: CEP válido preenche o endereço")
        dlg.locator("button[type=submit]").click()
        expect(page.locator("dialog[open]")).to_have_count(0)
        expect(page.locator("#lista")).to_contain_text(f"Tutor Fumaça {sufixo}")
        passo("tutor cadastrado e listado")

        # CPF duplicado
        page.get_by_role("button", name=re.compile("Novo tutor")).click()
        dlg = page.locator("dialog[open]")
        dlg.locator("#c_nome_completo").fill("Outro Tutor")
        dlg.locator("#c_cpf").fill(cpf)
        dlg.locator("#c_data_nascimento").fill("1991-01-01")
        dlg.locator("#c_email").fill(f"outro{sufixo}@example.com")
        dlg.locator("#c_telefone").fill("11912345678")
        dlg.locator("#c_cep").fill("01001000")
        dlg.locator("#buscar-cep").click()
        expect(dlg.locator("#c_logradouro")).to_have_value("Praça da Sé")
        dlg.locator("#c_numero").fill("1")
        dlg.locator("button[type=submit]").click()
        expect(dlg.locator("[data-erro=cpf], .erro-caixa").filter(has_text=re.compile("já existe", re.I)).first).to_be_visible()
        passo("CPF duplicado é recusado")
        dlg.locator("[data-fechar]").click()

        # ------------------------------------------------------------ animal
        page.goto(f"{BASE}/#/animais")
        page.click("#novo")
        dlg = page.locator("dialog[open]")
        dlg.locator("#c_nome").fill(f"Rex{sufixo[-4:]}")
        dlg.locator("#c_tutor_id").select_option(label=f"Tutor Fumaça {sufixo}")
        dlg.locator("#c_cor").fill("Caramelo")
        dlg.locator("button[type=submit]").click()                                   # espécie vazia deve ser recusada
        expect(dlg.locator("[data-erro=especie_id]")).to_contain_text("Selecione")
        passo("animal novo: espécie não vem pré-selecionada e é obrigatória")
        dlg.locator("#c_especie_id").select_option(label="Cão")
        assert dlg.locator("#c_raca_id option").count() > 1, "raças da espécie não carregaram"
        dlg.locator("#c_raca_id").select_option(index=1)
        dlg.locator("#c_sexo").select_option("MACHO")
        dlg.locator("#c_peso_atual").fill("12.5")
        dlg.locator("#c_data_nascimento").fill("2022-03-01")
        dlg.locator("button[type=submit]").click()
        expect(page.locator("dialog[open]")).to_have_count(0)
        expect(page.locator("#cab h1")).to_contain_text(f"Rex{sufixo[-4:]}")      # o app abre a ficha do animal criado
        passo("animal cadastrado (sem microchip) e ficha aberta automaticamente")

        # ------------------------------------------------------------ vacina antirrábica sem microchip
        page.get_by_role("tab", name="Vacinas").click()
        page.get_by_role("button", name="Registrar vacina").click()
        dlg = page.locator("dialog[open]")
        dlg.locator("#c_nome_vacina").fill("Antirrábica anual")
        dlg.locator("#c_tipo_vacina").select_option("ANTIRRABICA")
        expect(dlg.locator("#avisos")).to_contain_text("não tem microchip")
        passo("antirrábica: tela avisa que falta microchip")
        dlg.locator("[data-fechar]").click()

        # ------------------------------------------------------------ microchip
        page.get_by_role("tab", name="Resumo e microchip").click()
        page.get_by_role("button", name="Vincular microchip").click()
        dlg = page.locator("dialog[open]")
        dlg.locator("#c_codigo").fill("123")
        dlg.locator("button[type=submit]").click()
        expect(dlg.locator("[data-erro=codigo]")).to_contain_text("15 dígitos")
        dlg.locator("[data-gerar]").click()
        dlg.locator("button[type=submit]").click()
        toast_contem(page, "confirmado pelo governo")
        expect(page.locator("#aba")).to_contain_text("Vigente")
        foto(page, "04-animal-microchip")
        passo("microchip vinculado e cadastro CONFIRMADO no governo")

        # ------------------------------------------------------------ antirrábica CONFIRMADA
        def registrar_antirrabica(lote):
            page.get_by_role("tab", name="Vacinas").click()
            page.get_by_role("button", name="Registrar vacina").click()
            d = page.locator("dialog[open]")
            d.locator("#c_nome_vacina").fill("Antirrábica anual")
            d.locator("#c_tipo_vacina").select_option("ANTIRRABICA")
            d.locator("#c_dose").fill("Dose única")
            d.locator("#c_via_aplicacao").select_option("SUBCUTANEA")
            d.locator("#c_fabricante").fill("Zoetis")
            d.locator("#c_numero_lote").fill(lote)
            d.locator("#c_validade_lote").fill(amanha_ano)
            d.locator("button[type=submit]").click()
            return page.locator("dialog[open]")

        res = registrar_antirrabica(f"L{sufixo[-6:]}A")
        expect(res).to_contain_text("confirmou")
        foto(page, "05-vacina-confirmada")
        passo("antirrábica registrada e CONFIRMADA pelo governo (com protocolo)")
        res.locator("[data-fechar]").click()

        # vacina não antirrábica: sem comunicação
        page.get_by_role("button", name="Registrar vacina").click()
        d = page.locator("dialog[open]")
        d.locator("#c_nome_vacina").fill("V10")
        d.locator("#c_tipo_vacina").select_option("POLIVALENTE")
        d.locator("#c_dose").fill("Reforço anual")
        d.locator("#c_via_aplicacao").select_option("SUBCUTANEA")
        d.locator("#c_fabricante").fill("MSD")
        d.locator("#c_numero_lote").fill(f"V{sufixo[-6:]}")
        d.locator("#c_validade_lote").fill(amanha_ano)
        d.locator("#c_data_proxima_dose").fill(amanha_ano)
        d.locator("button[type=submit]").click()
        expect(page.locator("dialog[open]")).to_contain_text("não é antirrábica")
        page.locator("dialog[open] [data-fechar]").click()
        passo("vacina não antirrábica: sem comunicação ao governo")

        # ------------------------------------------------------------ governo fora do ar -> PENDENTE
        page.goto(f"{BASE}/#/painel")
        page.get_by_role("button", name=re.compile("Indispon")).click()
        page.wait_for_timeout(600)
        page.goto(f"{BASE}/#/animais")
        page.fill("#q", f"Rex{sufixo[-4:]}")
        page.locator("#lista a", has_text=f"Rex{sufixo[-4:]}").first.click()
        expect(page.locator("#cab h1")).to_be_visible()
        res = registrar_antirrabica(f"L{sufixo[-6:]}B")
        expect(res).to_contain_text("PENDENTE")
        expect(res).to_contain_text("registrada na clínica")
        foto(page, "06-vacina-pendente")
        passo("governo indisponível: vacina registrada localmente e comunicação PENDENTE")
        res.locator("[data-fechar]").click()
        foto(page, "07-vacinas-historico")

        # ------------------------------------------------------------ reenvio -> CONFIRMADA
        page.goto(f"{BASE}/#/painel")
        page.get_by_role("button", name=re.compile("^Normal")).click()
        page.wait_for_timeout(600)
        page.reload()
        botao = page.locator("#reprocessar")
        expect(botao).to_be_visible()
        if botao.is_enabled():
            botao.click()
            toast_contem(page, "confirmada")
            passo("pendência reprocessada e CONFIRMADA após o governo voltar")
        else:
            passo("pendência já tinha sido confirmada pelo reenvio automático")

        page.goto(f"{BASE}/#/integracoes")
        expect(page.locator("#lista table")).to_be_visible()
        foto(page, "08-integracoes")
        linha = page.locator("#lista tbody tr", has=page.locator("button[data-forcar]")).first
        linha.locator("button[data-forcar]").click()
        toast_contem(page, "mesmo protocolo")
        passo("reenvio idempotente: o governo devolve o mesmo protocolo, sem duplicar")

        # ------------------------------------------------------------ demais telas
        for rota, nome in (("#/catalogos", "09-catalogos"), ("#/veterinarios", "10-veterinarios"), ("#/tutores", "11-tutores")):
            page.goto(f"{BASE}/{rota}")
            expect(page.locator("#conteudo h1")).to_be_visible()
            expect(page.locator("#conteudo .erro-caixa")).to_have_count(0)
            foto(page, nome)
        passo("catálogos, veterinários e tutores carregam sem erro")

        # ------------------------------------------------------------ governo da ficha + móvel
        page.goto(f"{BASE}/#/animais")
        page.fill("#q", f"Rex{sufixo[-4:]}")
        page.locator("#lista a", has_text=f"Rex{sufixo[-4:]}").first.click()
        page.get_by_role("tab", name="Governo").click()
        expect(page.locator("#aba table")).to_be_visible()
        foto(page, "12-animal-governo")
        page.get_by_role("tab", name="Consultas").click()
        page.get_by_role("button", name="Nova consulta").click()
        d = page.locator("dialog[open]")
        d.locator("#c_motivo").fill("Check-up de rotina")
        d.locator("#c_peso_kg").fill("13.1")
        d.locator("#c_diagnostico").fill("Saudável")
        d.locator("button[type=submit]").click()
        expect(page.locator("#aba")).to_contain_text("Check-up de rotina")
        foto(page, "13-animal-consultas")
        passo("consulta registrada e exibida no histórico")

        # consulta agendada -> atendida (REALIZADA); outra agendada -> não compareceu; edição de uma realizada
        futuro = (date.today() + timedelta(days=3)).isoformat() + "T10:00"
        for motivo in ("Retorno agendado", "Consulta que faltou"):
            page.get_by_role("button", name="Nova consulta").click()
            d = page.locator("dialog[open]")
            d.locator("#c_data_hora").fill(futuro)
            d.locator("#c_situacao").select_option("AGENDADA")
            d.locator("#c_motivo").fill(motivo)
            d.locator("button[type=submit]").click()
            expect(page.locator("#aba tr", has_text=motivo).locator(".badge")).to_have_text("Agendada")
        passo("duas consultas agendadas aparecem no histórico")

        page.locator("#aba tr", has_text="Retorno agendado").get_by_role("button", name="Atender").click()
        d = page.locator("dialog[open]")
        expect(d.locator("#c_situacao")).to_have_value("REALIZADA")
        d.locator("#c_peso_kg").fill("13.4")
        d.locator("#c_diagnostico").fill("Evolução ótima")
        d.locator("button[type=submit]").click()
        toast_contem(page, "Atendimento registrado")
        linha = page.locator("#aba tr", has_text="Retorno agendado")
        expect(linha.locator(".badge")).to_have_text("Realizada")
        expect(linha).to_contain_text("Evolução ótima")
        expect(linha.get_by_role("button", name="Atender")).to_have_count(0)
        foto(page, "15-consulta-atendida")
        passo("consulta agendada atendida pela tela (vira Realizada com diagnóstico e peso)")

        page.locator("#aba tr", has_text="Consulta que faltou").get_by_role("button", name="Faltou").click()
        page.locator("dialog[open] [data-s]").click()
        expect(page.locator("#aba tr", has_text="Consulta que faltou").locator(".badge")).to_have_text("Não compareceu")
        passo("consulta marcada como Não compareceu pela tela")

        page.locator("#aba tr", has_text="Check-up de rotina").get_by_role("button", name="Editar").click()
        d = page.locator("dialog[open]")
        d.locator("#c_diagnostico").fill("Saudável, sem alterações")
        d.locator("button[type=submit]").click()
        expect(page.locator("#aba tr", has_text="Check-up de rotina")).to_contain_text("Saudável, sem alterações")
        passo("consulta realizada editada pela tela")

        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("tab", name="Consultas").click()
        expect(page.locator("#aba table")).to_be_visible()
        expect(page.locator("#toasts .toast")).to_have_count(0, timeout=20000)     # espera os avisos sumirem
        page.screenshot(path=os.path.join(PASTA, "16-movel-consultas.png"), full_page=True)
        page.get_by_role("tab", name="Vacinas").click()
        expect(page.locator("#aba table")).to_be_visible()
        foto(page, "14-movel-vacinas")
        passo("layout móvel renderiza")

        # sair
        page.set_viewport_size({"width": 1280, "height": 800})
        page.click("#btn-sair")
        expect(page.locator("#f-login")).to_be_visible()
        passo("logout volta para o login")

        navegador.close()

    print()
    if problemas:
        print("PROBLEMAS ENCONTRADOS:")
        for x in dict.fromkeys(problemas):
            print("  -", x)
        sys.exit(1)
    print(f"Fumaça da interface: {len(passos)} verificações OK, sem erros de JavaScript nem HTTP 5xx.")
    print(f"Capturas em {PASTA}")


if __name__ == "__main__":
    main()
