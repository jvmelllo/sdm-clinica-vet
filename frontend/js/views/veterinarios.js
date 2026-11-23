import { api, sessao } from "../api.js";
import { abrirModal, badge, campo, carregando, confirmar, enviarForm, esc, fmtCpf, fmtDataHora, obrigatorio, toast, toastErro, vazio, ativarMascaras } from "../ui.js";
import { cpfValido, emailValido, senhaForte, telefoneValido } from "../validacao.js";

const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

export async function veterinarios(el) {
  el.innerHTML = `<div class="cabecalho"><div><h1>Veterinários</h1><p class="suave">Profissionais autorizados a acessar o sistema. O acesso exige cadastro ativo e senha confirmada.</p></div>
    <button class="btn primario" id="novo">Novo veterinário</button></div><div class="card" id="lista">${carregando()}</div>`;
  async function carregar() {
    const caixa = el.querySelector("#lista");
    if (!caixa) return;   // a tela já foi trocada (ex.: busca com atraso ou resposta tardia)
    try {
      const dados = await api.get("/veterinarios");
      caixa.innerHTML = dados.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Nome</th><th>CRMV</th><th>Contato</th><th>Senha</th><th>Último acesso</th><th>Situação</th><th></th></tr></thead><tbody>
        ${dados.map((v) => `<tr><td data-label="Nome"><strong>${esc(v.nome_completo)}</strong><br><span class="suave pequeno mono">${fmtCpf(v.cpf)}</span></td>
          <td data-label="CRMV">${esc(v.crmv_numero)}/${esc(v.crmv_uf)}</td><td data-label="Contato">${esc(v.email)}</td>
          <td data-label="Senha">${v.senha_confirmada ? '<span class="badge ok">Confirmada</span>' : '<span class="badge aviso">Não confirmada</span>'}</td>
          <td data-label="Último acesso" class="pequeno">${fmtDataHora(v.ultimo_acesso_em)}</td><td data-label="Situação">${badge(v.situacao)}</td>
          <td class="acoes-cel">${!v.senha_confirmada ? `<button class="btn mini" data-codigo="${esc(v.email)}">Reenviar código</button>` : ""}
          ${v.id === sessao.vet?.id ? '<span class="pequeno suave">você</span>' : v.situacao === "ATIVO" ? `<button class="btn mini perigo" data-inativar="${v.id}">Inativar</button>` : `<button class="btn mini" data-reativar="${v.id}">Reativar</button>`}</td></tr>`).join("")}</tbody></table></div>` : vazio();
    } catch (e) { caixa.innerHTML = `<div class="erro-caixa">${esc(e.message)}</div>`; }
  }
  el.querySelector("#novo").onclick = () => formulario(carregar);
  el.querySelector("#lista").onclick = async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    try {
      if (b.dataset.inativar && await confirmar("Inativar veterinário", "Ele perderá o acesso imediatamente e as sessões abertas serão encerradas.", "Inativar", true)) { await api.del(`/veterinarios/${b.dataset.inativar}`); toast("Veterinário inativado."); carregar(); }
      if (b.dataset.reativar) { await api.post(`/veterinarios/${b.dataset.reativar}/reativar`); toast("Veterinário reativado."); carregar(); }
      if (b.dataset.codigo) {
        const r = await api.post("/auth/reenviar-codigo", { email: b.dataset.codigo });
        toast(r.codigo_simulado ? `E-mail simulado enviado. Código (demo): ${r.codigo_simulado}` : r.mensagem, "ok", 12000);
      }
    } catch (e) { toastErro(e); }
  };
  carregar();
}

function formulario(aoSalvar) {
  abrirModal("Novo veterinário", `<form novalidate><div class="form-grade">
    ${campo({ nome: "nome_completo", rotulo: "Nome completo", obrig: true, largo: true })}
    ${campo({ nome: "cpf", rotulo: "CPF", obrig: true, mascara: "cpf" })}
    ${campo({ nome: "crmv_numero", rotulo: "Nº do CRMV", obrig: true, attrs: 'inputmode="numeric" maxlength="10"' })}
    ${campo({ nome: "crmv_uf", rotulo: "UF do CRMV", obrig: true, opcoes: [["", "Selecione"], ...UFS.map((u) => [u, u])] })}
    ${campo({ nome: "email", rotulo: "E-mail", tipo: "email", obrig: true })}
    ${campo({ nome: "telefone", rotulo: "Telefone", obrig: true, mascara: "telefone" })}
    ${campo({ nome: "senha", rotulo: "Senha inicial", tipo: "password", obrig: true, ajuda: "Mínimo de 8 caracteres, com letras e números. Guardada apenas como hash.", attrs: 'autocomplete="new-password"' })}
  </div><div class="info-caixa">Após o cadastro um código de confirmação é enviado ao e-mail (simulado). O veterinário só consegue entrar depois de confirmar a senha.</div>
  <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">Cadastrar</button></div></form>`, (dlg) => {
    const form = dlg.querySelector("form");
    ativarMascaras(form);
    dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
    form.onsubmit = (ev) => { ev.preventDefault(); enviarForm(form, {
      regras: { nome_completo: obrigatorio(), cpf: (v) => (cpfValido(v) ? null : "CPF inválido."), crmv_numero: (v) => (/^\d{3,10}$/.test(v) ? null : "Somente dígitos."),
        crmv_uf: obrigatorio("Selecione a UF."), email: (v) => (emailValido(v) ? null : "E-mail inválido."), telefone: (v) => (telefoneValido(v) ? null : "Informe DDD + número."),
        senha: (v) => (senhaForte(v) ? null : "Mínimo de 8 caracteres, com letras e números.") },
      enviar: async (d) => {
        const r = await api.post("/veterinarios", d);
        toast(r.codigo_simulado ? `Cadastrado. E-mail simulado enviado. Código (demo): ${r.codigo_simulado}` : "Cadastrado. Código de confirmação enviado por e-mail.", "ok", 15000);
        dlg.close(); aoSalvar();
      } }); };
  });
}
