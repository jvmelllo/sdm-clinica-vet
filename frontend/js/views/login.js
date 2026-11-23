import { ApiErro, api, sessao } from "../api.js";
import { campo, enviarForm, esc, obrigatorio, toast } from "../ui.js";
import { emailValido } from "../validacao.js";

export function renderLogin(raiz) {
  raiz.innerHTML = `<div class="login-pagina"><div class="login-card">
    <h1><span aria-hidden="true">🐾</span> Clínica Veterinária</h1>
    <p class="suave">Acesso restrito a veterinários cadastrados, ativos e com senha confirmada.</p>
    <div id="area"></div>
    <div class="contas-demo"><strong>Contas de demonstração</strong> (senha <span class="mono">Senha@123</span>)<br>
      <span class="mono">ana.souza@clinicavet.example</span> — ativa<br>
      <span class="mono">bruno.lima@clinicavet.example</span> — inativo (bloqueado)<br>
      <span class="mono">carla.mendes@clinicavet.example</span> — senha não confirmada (bloqueada)</div>
  </div></div>`;
  mostrarLogin(raiz.querySelector("#area"));
}

function mostrarLogin(area, emailInicial = "") {
  area.innerHTML = `<form id="f-login" novalidate>
    <div class="form-grade" style="grid-template-columns:1fr">
      ${campo({ nome: "email", rotulo: "E-mail", tipo: "email", valor: emailInicial, obrig: true, attrs: 'autocomplete="username" autofocus' })}
      ${campo({ nome: "senha", rotulo: "Senha", tipo: "password", obrig: true, attrs: 'autocomplete="current-password"' })}
    </div>
    <div class="modal-rodape" style="justify-content:space-between;align-items:center">
      <a href="#" id="ir-confirmar" class="pequeno">Confirmar senha com código</a>
      <button type="submit" class="btn primario">Entrar</button>
    </div></form>`;
  const form = area.querySelector("form");
  area.querySelector("#ir-confirmar").onclick = (e) => { e.preventDefault(); mostrarConfirmacao(area, form.elements.email.value); };
  form.onsubmit = async (e) => {
    e.preventDefault();
    const ok = await enviarForm(form, {
      regras: { email: (v) => (emailValido(v) ? null : "Informe um e-mail válido."), senha: obrigatorio("Informe a senha.") },
      enviar: async (d) => {
        try {
          const r = await api.post("/auth/login", d);
          sessao.salvar(r.token, r.veterinario);
          location.hash = "#/painel";
          location.reload();
        } catch (err) {
          if (err instanceof ApiErro && err.codigo === "SENHA_NAO_CONFIRMADA") {
            toast("Senha ainda não confirmada: informe o código enviado ao seu e-mail.", "aviso", 7000);
            mostrarConfirmacao(area, d.email);
            return;
          }
          throw err;
        }
      },
    });
    if (!ok) form.elements.senha.value = "";
  };
}

function mostrarConfirmacao(area, email = "") {
  area.innerHTML = `<form id="f-conf" novalidate>
    <h2>Confirmar senha</h2>
    <p class="pequeno suave">Digite o código de 6 dígitos enviado ao seu e-mail (nesta versão acadêmica o envio é simulado).</p>
    <div class="form-grade" style="grid-template-columns:1fr">
      ${campo({ nome: "email", rotulo: "E-mail", tipo: "email", valor: email, obrig: true })}
      ${campo({ nome: "codigo", rotulo: "Código", obrig: true, attrs: 'inputmode="numeric" maxlength="6" autocomplete="one-time-code"' })}
    </div>
    <div id="aviso-codigo"></div>
    <div class="modal-rodape" style="justify-content:space-between;align-items:center">
      <a href="#" id="voltar" class="pequeno">Voltar ao login</a>
      <span class="acoes"><button type="button" class="btn" id="reenviar">Reenviar código</button>
      <button type="submit" class="btn primario">Confirmar</button></span>
    </div></form>`;
  const form = area.querySelector("form");
  area.querySelector("#voltar").onclick = (e) => { e.preventDefault(); mostrarLogin(area, form.elements.email.value); };
  area.querySelector("#reenviar").onclick = async () => {
    const mail = form.elements.email.value.trim();
    if (!emailValido(mail)) return toast("Informe o e-mail para reenviar o código.", "aviso");
    try {
      const r = await api.post("/auth/reenviar-codigo", { email: mail });
      toast(r.mensagem, "ok", 6000);
      if (r.codigo_simulado) area.querySelector("#aviso-codigo").innerHTML =
        `<div class="info-caixa">E-mail simulado. Código (visível só em modo demonstração): <strong class="mono">${esc(r.codigo_simulado)}</strong></div>`;
    } catch (err) { toast(err.message, "erro"); }
  };
  form.onsubmit = async (e) => {
    e.preventDefault();
    await enviarForm(form, {
      regras: { email: (v) => (emailValido(v) ? null : "Informe um e-mail válido."),
        codigo: (v) => (/^\d{6}$/.test(v) ? null : "O código tem 6 dígitos.") },
      enviar: async (d) => {
        const r = await api.post("/auth/confirmar-senha", d);
        toast(r.mensagem, "ok", 6000);
        mostrarLogin(area, d.email);
      },
    });
  };
}
