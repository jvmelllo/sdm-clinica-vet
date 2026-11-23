import { api, qs } from "../api.js";
import { abrirModal, ativarMascaras, badge, campo, carregando, confirmar, enviarForm, esc, fmtCpf, fmtData, fmtTel,
  obrigatorio, toast, toastErro, vazio } from "../ui.js";
import { cepValido, cpfValido, digitos, emailValido, telefoneValido } from "../validacao.js";

const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

export async function tutores(el) {
  const filtro = { q: "", situacao: "ATIVO" };
  el.innerHTML = `<div class="cabecalho"><div><h1>Tutores</h1><p class="suave">Responsáveis pelos animais.</p></div>
    <button class="btn primario" id="novo">Novo tutor</button></div>
    <div class="card"><div class="filtros">
      <input type="search" id="q" placeholder="Buscar por nome, CPF ou e-mail" aria-label="Buscar tutores" style="flex:1;min-width:200px">
      <select id="sit" aria-label="Situação"><option value="ATIVO">Ativos</option><option value="INATIVO">Inativos</option><option value="">Todos</option></select></div>
      <div id="lista">${carregando()}</div></div>`;

  async function carregar() {
    const caixa = el.querySelector("#lista");
    if (!caixa) return;   // a tela já foi trocada (ex.: busca com atraso ou resposta tardia)
    try {
      const dados = await api.get(`/tutores${qs(filtro)}`);
      caixa.innerHTML = dados.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Nome</th><th>CPF</th><th>Contato</th><th>Cidade</th><th>Animais</th><th>Situação</th><th></th></tr></thead><tbody>
        ${dados.map((t) => `<tr><td data-label="Nome"><strong>${esc(t.nome_completo)}</strong></td><td data-label="CPF" class="mono">${fmtCpf(t.cpf)}</td>
          <td data-label="Contato">${esc(t.email)}<br><span class="suave pequeno">${fmtTel(t.telefone)}</span></td>
          <td data-label="Cidade">${esc(t.cidade)}/${esc(t.uf)}</td><td data-label="Animais"><a href="#/animais?tutor=${t.id}">${t.total_animais}</a></td>
          <td data-label="Situação">${badge(t.situacao)}</td>
          <td class="acoes-cel"><button class="btn mini" data-editar="${t.id}">Editar</button>
          ${t.situacao === "ATIVO" ? `<button class="btn mini perigo" data-inativar="${t.id}">Inativar</button>` : `<button class="btn mini" data-reativar="${t.id}">Reativar</button>`}</td></tr>`).join("")}
        </tbody></table></div>` : vazio("Nenhum tutor encontrado.");
    } catch (e) { caixa.innerHTML = `<div class="erro-caixa">${esc(e.message)}</div>`; }
  }

  let t0;
  el.querySelector("#q").oninput = (e) => { clearTimeout(t0); t0 = setTimeout(() => { filtro.q = e.target.value.trim(); carregar(); }, 300); };
  el.querySelector("#sit").onchange = (e) => { filtro.situacao = e.target.value; carregar(); };
  el.querySelector("#novo").onclick = () => formularioTutor(null, carregar);
  el.querySelector("#lista").onclick = async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    try {
      if (b.dataset.editar) formularioTutor(await api.get(`/tutores/${b.dataset.editar}`), carregar);
      if (b.dataset.inativar && await confirmar("Inativar tutor", "O tutor deixará de aparecer nos cadastros ativos. Continuar?", "Inativar", true)) {
        await api.del(`/tutores/${b.dataset.inativar}`); toast("Tutor inativado."); carregar();
      }
      if (b.dataset.reativar) { await api.post(`/tutores/${b.dataset.reativar}/reativar`); toast("Tutor reativado."); carregar(); }
    } catch (e) { toastErro(e); }
  };
  carregar();
}

export function formularioTutor(t, aoSalvar) {
  const e = t?.endereco || {};
  const html = `<form id="f" novalidate>
    <div class="form-grade">
      ${campo({ nome: "nome_completo", rotulo: "Nome completo", valor: t?.nome_completo, obrig: true, largo: true, attrs: 'maxlength="150"' })}
      ${campo({ nome: "cpf", rotulo: "CPF", valor: t?.cpf, obrig: true, mascara: "cpf", attrs: 'inputmode="numeric"' })}
      ${campo({ nome: "data_nascimento", rotulo: "Data de nascimento", tipo: "date", valor: t?.data_nascimento, obrig: true })}
      ${campo({ nome: "email", rotulo: "E-mail", tipo: "email", valor: t?.email, obrig: true })}
      ${campo({ nome: "telefone", rotulo: "Telefone (com DDD)", valor: t?.telefone, obrig: true, mascara: "telefone", attrs: 'inputmode="tel"' })}
    </div>
    <fieldset><legend>Endereço</legend>
      <div class="form-grade">
        <div class="campo"><label for="c_cep" class="obrig">CEP</label>
          <div class="campo-linha"><input id="c_cep" name="cep" value="${esc(e.cep || "")}" data-mascara="cep" inputmode="numeric" placeholder="00000-000">
          <button type="button" class="btn" id="buscar-cep">Buscar CEP</button></div>
          <span class="ajuda">Ao informar o CEP os campos são preenchidos pelo ViaCEP; você pode editar qualquer um.</span>
          <span class="msg-erro" data-erro="cep"></span></div>
        ${campo({ nome: "logradouro", rotulo: "Logradouro", valor: e.logradouro, obrig: true })}
        ${campo({ nome: "numero", rotulo: "Número", valor: e.numero, obrig: true, attrs: 'maxlength="10"' })}
        ${campo({ nome: "complemento", rotulo: "Complemento", valor: e.complemento })}
        ${campo({ nome: "bairro", rotulo: "Bairro", valor: e.bairro, obrig: true })}
        ${campo({ nome: "cidade", rotulo: "Cidade", valor: e.cidade, obrig: true })}
        ${campo({ nome: "uf", rotulo: "UF", valor: e.uf || "", obrig: true, opcoes: [["", "Selecione"], ...UFS.map((u) => [u, u])] })}
        ${campo({ nome: "codigo_ibge", rotulo: "Código IBGE", valor: e.codigo_ibge, attrs: 'maxlength="7" inputmode="numeric"', ajuda: "Preenchido quando disponível." })}
      </div>
      <div id="cep-msg"></div>
    </fieldset>
    <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">${t ? "Salvar alterações" : "Cadastrar tutor"}</button></div></form>`;

  abrirModal(t ? "Editar tutor" : "Novo tutor", html, (dlg) => {
    const form = dlg.querySelector("form");
    ativarMascaras(form);
    dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
    const msg = dlg.querySelector("#cep-msg");
    let ultimoCep = digitos(e.cep);

    let buscando = false;   // o "blur" do campo e o clique no botão não podem disparar duas consultas ao ViaCEP
    async function buscarCep() {
      if (buscando) return;
      const cep = digitos(form.elements.cep.value);
      if (!cepValido(cep)) { msg.innerHTML = '<div class="aviso-caixa">Informe um CEP com 8 dígitos.</div>'; return; }
      buscando = true;
      msg.innerHTML = '<div class="info-caixa">Consultando CEP…</div>';
      try {
        const r = await api.get(`/cep/${cep}`);
        ultimoCep = cep;
        form.elements.logradouro.value = r.logradouro || form.elements.logradouro.value;
        form.elements.bairro.value = r.bairro || form.elements.bairro.value;
        form.elements.cidade.value = r.cidade || form.elements.cidade.value;
        form.elements.uf.value = r.uf || form.elements.uf.value;
        form.elements.codigo_ibge.value = r.codigo_ibge || "";
        if (r.complemento && !form.elements.complemento.value) form.elements.complemento.value = r.complemento;
        const faltou = !r.logradouro || !r.bairro;
        msg.innerHTML = faltou ? '<div class="info-caixa">CEP genérico da cidade: complete logradouro e bairro manualmente.</div>'
          : '<div class="ok-caixa">Endereço preenchido pelo ViaCEP. Informe o número.</div>';
        form.elements[faltou ? "logradouro" : "numero"].focus();
      } catch (err) {
        const textos = { CEP_NAO_ENCONTRADO: "CEP não encontrado. Confira o número ou preencha o endereço manualmente.",
          CEP_TIMEOUT: "O serviço de CEP demorou a responder. Tente de novo ou preencha manualmente.",
          CEP_INDISPONIVEL: "O serviço de CEP está indisponível. Preencha o endereço manualmente." };
        msg.innerHTML = `<div class="aviso-caixa">${esc(textos[err.codigo] || err.message)}</div>`;
      } finally {
        buscando = false;
      }
    }
    dlg.querySelector("#buscar-cep").onclick = buscarCep;
    form.elements.cep.addEventListener("blur", () => { const c = digitos(form.elements.cep.value); if (cepValido(c) && c !== ultimoCep) buscarCep(); });

    form.onsubmit = async (ev) => {
      ev.preventDefault();
      const ok = await enviarForm(form, {
        regras: {
          nome_completo: (v) => (v.length >= 5 ? null : "Informe o nome completo."),
          cpf: (v) => (cpfValido(v) ? null : "CPF inválido."),
          data_nascimento: (v) => (!v ? "Campo obrigatório." : v > new Date().toISOString().slice(0, 10) ? "A data não pode estar no futuro." : null),
          email: (v) => (emailValido(v) ? null : "E-mail inválido."),
          telefone: (v) => (telefoneValido(v) ? null : "Informe DDD + número (10 ou 11 dígitos)."),
          cep: (v) => (cepValido(v) ? null : "CEP deve ter 8 dígitos."),
          logradouro: obrigatorio(), numero: obrigatorio(), bairro: obrigatorio(), cidade: obrigatorio(), uf: obrigatorio("Selecione a UF."),
        },
        enviar: async (d) => {
          const { cep, logradouro, numero, complemento, bairro, cidade, uf, codigo_ibge, ...tutor } = d;
          const corpo = { ...tutor, endereco: { cep, logradouro, numero, complemento, bairro, cidade, uf, codigo_ibge } };
          if (t) await api.put(`/tutores/${t.id}`, corpo); else await api.post("/tutores", corpo);
          toast(t ? "Tutor atualizado." : "Tutor cadastrado.");
          dlg.close();
          aoSalvar?.();
        },
      });
      return ok;
    };
  });
}
