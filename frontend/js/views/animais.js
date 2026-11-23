import { api, qs } from "../api.js";
import { abrirModal, badge, campo, carregando, enviarForm, esc, obrigatorio, toast, toastErro, vazio } from "../ui.js";

export async function animais(el) {
  const params = new URLSearchParams((location.hash.split("?")[1]) || "");
  const filtro = { q: "", situacao: "ATIVO", tutor_id: params.get("tutor") || "" };
  el.innerHTML = `<div class="cabecalho"><div><h1>Animais</h1><p class="suave">Pacientes da clínica${filtro.tutor_id ? " (filtrado por tutor)" : ""}.</p></div>
    <button class="btn primario" id="novo">Novo animal</button></div>
    <div class="card"><div class="filtros">
      <input type="search" id="q" placeholder="Buscar por nome do animal ou do tutor" aria-label="Buscar animais" style="flex:1;min-width:200px">
      <select id="sit" aria-label="Situação"><option value="ATIVO">Ativos</option><option value="INATIVO">Inativos</option><option value="">Todos</option></select>
      ${filtro.tutor_id ? '<a class="btn" href="#/animais">Limpar filtro de tutor</a>' : ""}</div>
      <div id="lista">${carregando()}</div></div>`;

  async function carregar() {
    const caixa = el.querySelector("#lista");
    if (!caixa) return;   // a tela já foi trocada (ex.: busca com atraso ou resposta tardia)
    try {
      const dados = await api.get(`/animais${qs(filtro)}`);
      caixa.innerHTML = dados.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Animal</th><th>Espécie / raça</th><th>Tutor</th><th>Peso</th><th>Microchip</th><th>Situação</th><th></th></tr></thead><tbody>
        ${dados.map((a) => `<tr><td data-label="Animal"><a href="#/animais/${a.id}"><strong>${esc(a.nome)}</strong></a><br><span class="suave pequeno">${esc(a.sexo === "MACHO" ? "Macho" : "Fêmea")} · ${esc(a.cor)}</span></td>
          <td data-label="Espécie / raça">${esc(a.especie_nome)}<br><span class="suave pequeno">${esc(a.raca_nome || "Sem raça definida")}</span></td>
          <td data-label="Tutor">${esc(a.tutor_nome)}</td><td data-label="Peso">${a.peso_atual} kg</td>
          <td data-label="Microchip" class="mono pequeno">${a.microchip ? esc(a.microchip) : '<span class="badge aviso">Sem microchip</span>'}</td>
          <td data-label="Situação">${badge(a.situacao)}</td>
          <td class="acoes-cel"><a class="btn mini" href="#/animais/${a.id}">Abrir</a></td></tr>`).join("")}</tbody></table></div>` : vazio("Nenhum animal encontrado.");
    } catch (e) { caixa.innerHTML = `<div class="erro-caixa">${esc(e.message)}</div>`; }
  }
  let t0;
  el.querySelector("#q").oninput = (e) => { clearTimeout(t0); t0 = setTimeout(() => { filtro.q = e.target.value.trim(); carregar(); }, 300); };
  el.querySelector("#sit").onchange = (e) => { filtro.situacao = e.target.value; carregar(); };
  el.querySelector("#novo").onclick = () => formularioAnimal(null, (a) => { location.hash = `#/animais/${a.id}`; }, filtro.tutor_id);
  carregar();
}

export async function formularioAnimal(animal, aoSalvar, tutorPadrao = "") {
  let tutores, especies, racas;
  try {
    [tutores, especies, racas] = await Promise.all([api.get("/tutores?situacao=ATIVO&limite=500"), api.get("/especies?situacao=ATIVA"), api.get("/racas?situacao=ATIVA&limite=500")]);
  } catch (e) { return toastErro(e); }
  if (!tutores.length) return toast("Cadastre um tutor antes de cadastrar o animal.", "aviso");
  const opcoesRaca = (espId, atual) => [["", "Sem raça definida"], ...racas.filter((r) => String(r.especie_id) === String(espId)).map((r) => [r.id, r.nome])]
    .map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(atual ?? "") ? "selected" : ""}>${esc(t)}</option>`).join("");
  const espInicial = animal?.especie_id ?? "";   // animal novo: sem pré-seleção, para não cadastrar a espécie errada sem perceber
  const html = `<form id="f" novalidate>
    <div class="form-grade">
      ${campo({ nome: "nome", rotulo: "Nome", valor: animal?.nome, obrig: true, attrs: 'maxlength="80"' })}
      ${campo({ nome: "tutor_id", rotulo: "Tutor responsável", valor: animal?.tutor_id ?? tutorPadrao, obrig: true, opcoes: [["", "Selecione"], ...tutores.map((t) => [t.id, t.nome_completo])] })}
      ${campo({ nome: "especie_id", rotulo: "Espécie", valor: espInicial, obrig: true, opcoes: [["", "Selecione"], ...especies.map((e) => [e.id, e.nome])] })}
      <div class="campo"><label for="c_raca_id">Raça</label><select id="c_raca_id" name="raca_id">${opcoesRaca(espInicial, animal?.raca_id)}</select>
        <span class="ajuda">Somente raças da espécie escolhida.</span><span class="msg-erro" data-erro="raca_id"></span></div>
      ${campo({ nome: "sexo", rotulo: "Sexo", valor: animal?.sexo || "", obrig: true, opcoes: [["", "Selecione"], ["MACHO", "Macho"], ["FEMEA", "Fêmea"]] })}
      ${campo({ nome: "cor", rotulo: "Cor", valor: animal?.cor, obrig: true })}
      ${campo({ nome: "peso_atual", rotulo: "Peso atual (kg)", tipo: "number", valor: animal?.peso_atual, obrig: true, attrs: 'step="0.01" min="0.01"' })}
      ${campo({ nome: "data_nascimento", rotulo: "Data de nascimento", tipo: "date", valor: animal?.data_nascimento, ajuda: "Informe a data ou a idade estimada." })}
      ${campo({ nome: "idade_estimada_meses", rotulo: "Idade estimada (meses)", tipo: "number", valor: animal?.idade_estimada_meses, attrs: 'min="0" max="600"' })}
      ${animal ? campo({ nome: "situacao", rotulo: "Situação", valor: animal.situacao, opcoes: [["ATIVO", "Ativo"], ["INATIVO", "Inativo"], ["OBITO", "Óbito"]] }) : ""}
    </div>
    <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">${animal ? "Salvar alterações" : "Cadastrar animal"}</button></div></form>`;

  abrirModal(animal ? "Editar animal" : "Novo animal", html, (dlg) => {
    const form = dlg.querySelector("form");
    dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
    form.elements.especie_id.onchange = () => { form.elements.raca_id.innerHTML = opcoesRaca(form.elements.especie_id.value, ""); };
    form.onsubmit = async (ev) => {
      ev.preventDefault();
      await enviarForm(form, {
        regras: {
          nome: obrigatorio(), tutor_id: obrigatorio("Selecione o tutor."), especie_id: obrigatorio("Selecione a espécie."),
          sexo: obrigatorio("Selecione o sexo."), cor: obrigatorio(),
          peso_atual: (v) => (Number(v) > 0 ? null : "Informe um peso maior que zero."),
          data_nascimento: (v, d) => (!v && !d.idade_estimada_meses ? "Informe a data de nascimento ou a idade estimada." : null),
        },
        enviar: async (d) => {
          const corpo = { ...d, raca_id: d.raca_id || null, data_nascimento: d.data_nascimento || null, idade_estimada_meses: d.idade_estimada_meses || null };
          const r = animal ? await api.put(`/animais/${animal.id}`, corpo) : await api.post("/animais", corpo);
          toast(animal ? "Animal atualizado." : "Animal cadastrado. Próximo passo: vincular o microchip.");
          if (r.atualizacao_governo) toast(`Atualização enviada ao governo: ${r.atualizacao_governo.situacao}.`, r.atualizacao_governo.situacao === "CONFIRMADA" ? "ok" : "aviso");
          dlg.close();
          aoSalvar?.(r);
        },
      });
    };
  });
}
