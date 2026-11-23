import { api } from "../api.js";
import { abrirModal, badge, campo, carregando, confirmar, enviarForm, esc, obrigatorio, toast, toastErro, vazio } from "../ui.js";

export async function catalogos(el) {
  el.innerHTML = `<div class="cabecalho"><div><h1>Espécies e raças</h1><p class="suave">Catálogos usados no cadastro de animais.</p></div></div>
    <div class="grade-2"><div class="card"><div class="cabecalho" style="margin:0 0 .5rem"><h2>Espécies</h2><button class="btn primario mini" id="nova-esp">Nova espécie</button></div><div id="esp">${carregando()}</div></div>
    <div class="card"><div class="cabecalho" style="margin:0 0 .5rem"><h2>Raças</h2><span class="acoes"><select id="filtro-esp" aria-label="Filtrar por espécie"></select><button class="btn primario mini" id="nova-raca">Nova raça</button></span></div><div id="racas">${carregando()}</div></div></div>`;
  let especies = [];

  async function carregarEspecies() {
    especies = await api.get("/especies");
    const alvoEsp = el.querySelector("#esp");
    if (!alvoEsp) return;   // a tela já foi trocada
    alvoEsp.innerHTML = especies.length ? `<div class="tabela-wrap"><table><tbody>${especies.map((e) => `<tr><td><strong>${esc(e.nome)}</strong><br><span class="suave pequeno">${esc(e.descricao || "")}</span></td><td>${badge(e.situacao)}</td>
      <td class="acoes-cel"><button class="btn mini" data-esp-editar="${e.id}">Editar</button>${e.situacao === "ATIVA" ? `<button class="btn mini perigo" data-esp-inativar="${e.id}">Inativar</button>` : `<button class="btn mini" data-esp-reativar="${e.id}">Reativar</button>`}</td></tr>`).join("")}</tbody></table></div>` : vazio();
    const sel = el.querySelector("#filtro-esp");
    const atual = sel.value;
    sel.innerHTML = `<option value="">Todas as espécies</option>${especies.map((e) => `<option value="${e.id}">${esc(e.nome)}</option>`).join("")}`;
    sel.value = atual;
  }
  async function carregarRacas() {
    const filtroEsp = el.querySelector("#filtro-esp");
    if (!filtroEsp) return;
    const esp = filtroEsp.value;
    const racas = await api.get(`/racas${esp ? `?especie_id=${esp}` : ""}`);
    const alvoRacas = el.querySelector("#racas");
    if (!alvoRacas) return;   // a tela já foi trocada
    alvoRacas.innerHTML = racas.length ? `<div class="tabela-wrap"><table><tbody>${racas.map((r) => `<tr><td><strong>${esc(r.nome)}</strong><br><span class="suave pequeno">${esc(r.especie_nome)}</span></td><td>${badge(r.situacao)}</td>
      <td class="acoes-cel"><button class="btn mini" data-raca-editar="${r.id}">Editar</button>${r.situacao === "ATIVA" ? `<button class="btn mini perigo" data-raca-inativar="${r.id}">Inativar</button>` : `<button class="btn mini" data-raca-reativar="${r.id}">Reativar</button>`}</td></tr>`).join("")}</tbody></table></div>` : vazio("Nenhuma raça nesta espécie.");
  }
  const tudo = async () => { try { await carregarEspecies(); await carregarRacas(); } catch (e) { toastErro(e); } };

  function formEspecie(esp) {
    abrirModal(esp ? "Editar espécie" : "Nova espécie", `<form novalidate>${campo({ nome: "nome", rotulo: "Nome", valor: esp?.nome, obrig: true })}${campo({ nome: "descricao", rotulo: "Descrição", valor: esp?.descricao })}
      <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">Salvar</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      form.onsubmit = (ev) => { ev.preventDefault(); enviarForm(form, { regras: { nome: obrigatorio() }, enviar: async (d) => {
        if (esp) await api.put(`/especies/${esp.id}`, d); else await api.post("/especies", d);
        toast("Espécie salva."); dlg.close(); tudo(); } }); };
    });
  }
  function formRaca(raca) {
    abrirModal(raca ? "Editar raça" : "Nova raça", `<form novalidate>${campo({ nome: "nome", rotulo: "Nome", valor: raca?.nome, obrig: true })}
      ${campo({ nome: "especie_id", rotulo: "Espécie", valor: raca?.especie_id ?? el.querySelector("#filtro-esp").value, obrig: true, opcoes: [["", "Selecione"], ...especies.filter((e) => e.situacao === "ATIVA").map((e) => [e.id, e.nome])] })}
      ${campo({ nome: "descricao", rotulo: "Descrição", valor: raca?.descricao })}
      <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">Salvar</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      form.onsubmit = (ev) => { ev.preventDefault(); enviarForm(form, { regras: { nome: obrigatorio(), especie_id: obrigatorio("Selecione a espécie.") }, enviar: async (d) => {
        if (raca) await api.put(`/racas/${raca.id}`, d); else await api.post("/racas", d);
        toast("Raça salva."); dlg.close(); tudo(); } }); };
    });
  }

  el.querySelector("#nova-esp").onclick = () => formEspecie(null);
  el.querySelector("#nova-raca").onclick = () => formRaca(null);
  el.querySelector("#filtro-esp").onchange = () => carregarRacas().catch(toastErro);
  el.onclick = async (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    const d = b.dataset;
    try {
      if (d.espEditar) formEspecie(await api.get(`/especies/${d.espEditar}`));
      if (d.espInativar && await confirmar("Inativar espécie", "As raças desta espécie também serão inativadas. Continuar?", "Inativar", true)) { await api.del(`/especies/${d.espInativar}`); tudo(); }
      if (d.espReativar) { await api.post(`/especies/${d.espReativar}/reativar`); tudo(); }
      if (d.racaEditar) formRaca(await api.get(`/racas/${d.racaEditar}`));
      if (d.racaInativar) { await api.del(`/racas/${d.racaInativar}`); tudo(); }
      if (d.racaReativar) { await api.post(`/racas/${d.racaReativar}/reativar`); tudo(); }
    } catch (e) { toastErro(e); }
  };
  await tudo();
}
