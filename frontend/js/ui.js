// Componentes de interface reutilizáveis (sem frameworks).
import { ApiErro } from "./api.js";
import { mascaraCep, mascaraCpf, mascaraTelefone } from "./validacao.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export const fmtData = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "—");
export const fmtDataHora = (iso) => (iso ? `${fmtData(iso)} ${String(iso).slice(11, 16)}` : "—");
export const fmtCpf = (v) => mascaraCpf(v);
export const fmtTel = (v) => mascaraTelefone(v);
export const hojeISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

const COR_SITUACAO = {
  ATIVO: "ok", ATIVA: "ok", INATIVO: "neutro", INATIVA: "neutro", OBITO: "neutro",
  CONFIRMADA: "ok", PENDENTE: "aviso", ENVIADA: "info", FALHA: "erro",
  AGENDADA: "info", REALIZADA: "ok", CANCELADA: "neutro", NAO_COMPARECEU: "aviso", APLICADA: "ok",
  NAO_APLICAVEL: "neutro", SEM_MICROCHIP: "neutro", NAO_SOLICITADO: "aviso", NAO_SOLICITADA: "aviso",
};
const ROTULO = { NAO_COMPARECEU: "Não compareceu", SEM_MICROCHIP: "Sem microchip", NAO_APLICAVEL: "Não se aplica",
  NAO_SOLICITADO: "Não solicitado", NAO_SOLICITADA: "Não solicitada", OBITO: "Óbito" };
export const badge = (valor, cor, rotulo) => {
  if (valor == null) return '<span class="badge neutro">—</span>';
  const texto = rotulo || ROTULO[valor] || valor.charAt(0) + valor.slice(1).toLowerCase().replaceAll("_", " ");
  return `<span class="badge ${cor || COR_SITUACAO[valor] || "neutro"}">${esc(texto)}</span>`;
};

// ---------------------------------------------------------------- toasts
export function toast(msg, tipo = "ok", ms = 5000) {
  const el = document.createElement("div");
  el.className = `toast ${tipo}`;
  el.textContent = msg;
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), ms);
}
export const toastErro = (e) => toast(e instanceof ApiErro ? e.message : "Erro inesperado.", "erro", 7000);

// ---------------------------------------------------------------- modal
export function abrirModal(titulo, html, aoMontar) {
  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  // O cabeçalho NÃO pode ser um <form>: as views usam dlg.querySelector("form") para achar o formulário do conteúdo.
  dlg.innerHTML = `<div class="modal-cab"><h2>${esc(titulo)}</h2>
    <button type="button" class="btn icone" aria-label="Fechar" data-x>×</button></div><div class="modal-corpo">${html}</div>`;
  document.body.append(dlg);
  dlg.querySelector("[data-x]").onclick = () => dlg.close();
  dlg.addEventListener("close", () => dlg.remove());
  dlg.showModal();
  aoMontar?.(dlg);
  return dlg;
}
export function confirmar(titulo, mensagem, rotulo = "Confirmar", perigo = false) {
  return new Promise((resolve) => {
    const dlg = abrirModal(titulo, `<p>${esc(mensagem)}</p><div class="modal-rodape">
      <button class="btn" data-n>Cancelar</button><button class="btn ${perigo ? "perigo" : "primario"}" data-s>${esc(rotulo)}</button></div>`);
    dlg.querySelector("[data-n]").onclick = () => { resolve(false); dlg.close(); };
    dlg.querySelector("[data-s]").onclick = () => { resolve(true); dlg.close(); };
    dlg.addEventListener("close", () => resolve(false));
  });
}

// ---------------------------------------------------------------- formulários
export function campo({ nome, rotulo, tipo = "text", valor = "", obrig = false, ajuda = "", largo = false, attrs = "", opcoes = null, mascara = "" }) {
  const id = `c_${nome}`;
  const rot = `<label for="${id}" class="${obrig ? "obrig" : ""}">${esc(rotulo)}</label>`;
  let ctl;
  if (opcoes) {
    ctl = `<select id="${id}" name="${nome}" ${attrs}>${opcoes.map(([v, t]) =>
      `<option value="${esc(v)}" ${String(v) === String(valor ?? "") ? "selected" : ""}>${esc(t)}</option>`).join("")}</select>`;
  } else if (tipo === "textarea") {
    ctl = `<textarea id="${id}" name="${nome}" rows="2" ${attrs}>${esc(valor)}</textarea>`;
  } else {
    ctl = `<input id="${id}" name="${nome}" type="${tipo}" value="${esc(valor)}" ${mascara ? `data-mascara="${mascara}"` : ""} ${attrs}>`;
  }
  return `<div class="campo ${largo ? "largo" : ""}">${rot}${ctl}${ajuda ? `<span class="ajuda">${esc(ajuda)}</span>` : ""}<span class="msg-erro" data-erro="${nome}"></span></div>`;
}

const MASCARAS = { cpf: mascaraCpf, cep: mascaraCep, telefone: mascaraTelefone };
export function ativarMascaras(raiz) {
  raiz.querySelectorAll("[data-mascara]").forEach((el) => {
    const fn = MASCARAS[el.dataset.mascara];
    el.addEventListener("input", () => { el.value = fn(el.value); });
    el.value = fn(el.value);
  });
}

export function lerForm(form) {
  const d = {};
  for (const el of form.elements) {
    if (!el.name || el.disabled) continue;
    d[el.name] = el.type === "checkbox" ? el.checked : el.value.trim();
  }
  return d;
}
export function limparErros(form) {
  form.querySelectorAll("[data-erro]").forEach((e) => { e.textContent = ""; });
  form.querySelectorAll("[aria-invalid]").forEach((e) => e.removeAttribute("aria-invalid"));
  form.querySelector(".erro-caixa")?.remove();
}
export function mostrarErros(form, detalhes) {
  let sobra = false;
  Object.entries(detalhes || {}).forEach(([nome, msg]) => {
    const alvo = form.querySelector(`[data-erro="${nome}"]`);
    if (alvo) {
      alvo.textContent = msg;
      form.elements[nome]?.setAttribute("aria-invalid", "true");
    } else sobra = true;
  });
  form.querySelector("[aria-invalid]")?.focus();
  return sobra;
}
export function bannerErro(form, msg) {
  form.querySelector(".erro-caixa")?.remove();
  const div = document.createElement("div");
  div.className = "erro-caixa";
  div.setAttribute("role", "alert");
  div.textContent = msg;
  form.prepend(div);
}

/** Valida no cliente (regras: {campo: (valor, dados) => mensagem|null}) e depois chama a API. */
export async function enviarForm(form, { regras = {}, enviar }) {
  limparErros(form);
  const dados = lerForm(form);
  const erros = {};
  Object.entries(regras).forEach(([nome, fn]) => { const m = fn(dados[nome], dados); if (m) erros[nome] = m; });
  if (Object.keys(erros).length) { mostrarErros(form, erros); return false; }
  const botoes = form.querySelectorAll("button[type=submit]");
  botoes.forEach((b) => { b.disabled = true; });
  try {
    await enviar(dados);
    return true;
  } catch (e) {
    if (!(e instanceof ApiErro)) throw e;
    const sobra = e.detalhes ? mostrarErros(form, e.detalhes) : true;
    if (sobra || !e.detalhes) bannerErro(form, e.message + (e.detalhes && sobra ? ` ${JSON.stringify(e.detalhes)}` : ""));
    return false;
  } finally {
    botoes.forEach((b) => { b.disabled = false; });
  }
}

export const obrigatorio = (msg = "Campo obrigatório.") => (v) => (v ? null : msg);
export const vazio = (html = "Nada por aqui ainda.") => `<div class="vazio">${html}</div>`;
export const carregando = () => '<div class="vazio">Carregando…</div>';
export const erroCaixa = (e) => `<div class="erro-caixa" role="alert">${esc(e.message || e)}</div>`;
