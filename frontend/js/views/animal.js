// Ficha do animal: resumo + microchip, consultas, vacinas e comunicação com o governo.
// É a tela central da demonstração: microchip -> vacina antirrábica -> governo (confirmada ou pendente).
import { api } from "../api.js";
import {
  abrirModal, badge, campo, carregando, confirmar, enviarForm, erroCaixa, esc, fmtData, fmtDataHora,
  hojeISO, obrigatorio, toast, toastErro, vazio,
} from "../ui.js";
import { microchipValido } from "../validacao.js";
import { formularioAnimal } from "./animais.js";
import { ligarIntegracoes, tabelaIntegracoes } from "./integracoes.js";

const TIPOS_VACINA = [["ANTIRRABICA", "Antirrábica"], ["POLIVALENTE", "Polivalente (V8/V10)"], ["TRIPLICE_FELINA", "Tríplice felina"],
  ["GRIPE_CANINA", "Gripe canina"], ["GIARDIA", "Giárdia"], ["LEISHMANIOSE", "Leishmaniose"], ["OUTRA", "Outra"]];
const ROTULO_TIPO = Object.fromEntries(TIPOS_VACINA);
const VIAS = [["SUBCUTANEA", "Subcutânea"], ["INTRAMUSCULAR", "Intramuscular"], ["INTRANASAL", "Intranasal"], ["ORAL", "Oral"]];
const PRAZO = { ATRASADA: ["erro", "Atrasada"], HOJE: ["aviso", "Hoje"], NO_PRAZO: ["info", "No prazo"] };

const agoraLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const gerarMicrochip = () => "900" + Array.from({ length: 12 }, () => Math.floor(Math.random() * 10)).join("");
const cortar = (s, n) => (s && s.length > n ? `${esc(s.slice(0, n))}…` : esc(s || "—"));

/** Avisa o resultado de uma operação de integração (CONFIRMADA / PENDENTE / ENVIADA / FALHA). */
function avisoGoverno(op, rotulo) {
  if (!op) return;
  if (op.situacao === "CONFIRMADA") toast(`${rotulo}: confirmado pelo governo. Protocolo ${op.protocolo_externo}.`, "ok", 8000);
  else if (op.situacao === "FALHA") toast(`${rotulo}: rejeitado pelo governo. ${op.mensagem_erro || ""}`, "erro", 12000);
  else if (op.situacao === "ENVIADA") toast(`${rotulo}: sem resposta conclusiva do governo (ENVIADA). O reenvio é seguro.`, "aviso", 12000);
  else toast(`${rotulo}: governo indisponível. Ficou PENDENTE e pode ser reenviado depois.`, "aviso", 12000);
}

export async function animalDetalhe(el, [idTexto]) {
  const id = Number(idTexto);
  let animal = await api.get(`/animais/${id}`);
  let aba = "resumo";
  let versao = 0;
  let consultasPorId = {};
  let vacinasPorId = {};
  const ABAS = [["resumo", "Resumo e microchip"], ["consultas", "Consultas"], ["vacinas", "Vacinas"], ["governo", "Governo"]];

  el.innerHTML = `<p class="pequeno"><a href="#/animais">← Voltar para animais</a></p><div id="cab"></div>
    <div class="abas" role="tablist">${ABAS.map(([k, t]) => `<button role="tab" data-aba="${k}">${t}</button>`).join("")}</div>
    <div id="aba"></div>`;
  const caixa = el.querySelector("#aba");

  // ------------------------------------------------------------------ cabeçalho
  function cabecalho() {
    el.querySelector("#cab").innerHTML = `<div class="cabecalho"><div>
      <h1>${esc(animal.nome)} ${badge(animal.situacao)}</h1>
      <p class="suave">${esc(animal.especie_nome)} · ${esc(animal.raca_nome || "Sem raça definida")} · Tutor: ${esc(animal.tutor_nome)}</p></div>
      <div class="acoes"><button class="btn" id="editar">Editar dados</button>
      ${animal.situacao === "ATIVO" ? '<button class="btn perigo" id="inativar">Inativar</button>' : '<button class="btn" id="reativar">Reativar</button>'}</div></div>`;
    el.querySelector("#editar").onclick = () => formularioAnimal(animal, recarregar);
    const inativar = el.querySelector("#inativar");
    if (inativar) {
      inativar.onclick = async () => {
        if (!(await confirmar("Inativar animal", `${animal.nome} deixará de aparecer entre os ativos. O histórico clínico é mantido.`, "Inativar", true))) return;
        try { await api.del(`/animais/${id}`); toast("Animal inativado."); await recarregar(); } catch (e) { toastErro(e); }
      };
    }
    const reativar = el.querySelector("#reativar");
    if (reativar) {
      reativar.onclick = async () => {
        try { await api.post(`/animais/${id}/reativar`); toast("Animal reativado."); await recarregar(); } catch (e) { toastErro(e); }
      };
    }
  }

  async function recarregar() {
    animal = await api.get(`/animais/${id}`);
    cabecalho();
    await mostrarAba();
  }

  async function mostrarAba() {
    el.querySelectorAll("[data-aba]").forEach((b) => {
      const ativa = b.dataset.aba === aba;
      b.classList.toggle("ativa", ativa);
      b.setAttribute("aria-selected", String(ativa));
    });
    const minha = ++versao;
    caixa.innerHTML = carregando();
    try {
      const html = await RENDER[aba]();
      if (minha === versao) caixa.innerHTML = html;      // ignora respostas de abas que já não estão na tela
    } catch (e) {
      if (minha === versao) caixa.innerHTML = erroCaixa(e);
    }
  }

  // ------------------------------------------------------------------ aba: resumo
  async function abaResumo() {
    const chips = await api.get(`/animais/${id}/microchips`);
    const mc = animal.microchip_atual;
    const gov = animal.integracao_governo;
    const idade = animal.data_nascimento ? fmtData(animal.data_nascimento) : `${animal.idade_estimada_meses} meses (estimada)`;
    return `<div class="grade-2">
      <div class="card"><h2>Dados do animal</h2><dl class="kv">
        <dt>Espécie</dt><dd>${esc(animal.especie_nome)}</dd>
        <dt>Raça</dt><dd>${animal.raca_nome ? esc(animal.raca_nome) : '<span class="badge neutro">Sem raça definida</span>'}</dd>
        <dt>Sexo</dt><dd>${animal.sexo === "MACHO" ? "Macho" : "Fêmea"}</dd><dt>Cor</dt><dd>${esc(animal.cor)}</dd>
        <dt>Nascimento</dt><dd>${esc(idade)}</dd><dt>Peso atual</dt><dd>${esc(animal.peso_atual)} kg</dd>
        <dt>Tutor</dt><dd>${esc(animal.tutor_nome)}</dd><dt>Cadastrado em</dt><dd>${fmtData(animal.data_cadastro)}</dd></dl></div>

      <div class="card"><h2>Microchip RFID</h2>
        ${mc ? `<dl class="kv"><dt>Código</dt><dd class="mono"><strong>${esc(mc.codigo)}</strong></dd>
            <dt>Vinculado em</dt><dd>${fmtDataHora(mc.data_vinculo)}</dd><dt>Por</dt><dd>${esc(mc.veterinario_nome)}</dd></dl>`
          : '<div class="aviso-caixa">Este animal ainda não tem microchip. Sem ele não é possível comunicar o animal nem a vacina antirrábica ao governo.</div>'}
        ${animal.situacao === "ATIVO" ? `<div class="acoes" style="margin-top:.6rem"><button class="btn primario" data-act="${mc ? "trocar-chip" : "novo-chip"}">${mc ? "Substituir microchip" : "Vincular microchip"}</button></div>` : ""}
        <h3>Situação no governo</h3>
        <dl class="kv"><dt>Cadastro</dt><dd>${badge(gov.situacao_cadastro)}</dd>
          <dt>Protocolo</dt><dd class="mono">${esc(gov.protocolo_cadastro || "—")}</dd>
          <dt>Pendências</dt><dd>${gov.pendencias ? `<span class="badge aviso">${gov.pendencias}</span>` : "Nenhuma"}</dd></dl>
        ${mc ? `<div class="acoes" style="margin-top:.6rem"><button class="btn" data-act="sincronizar">${gov.sincronizado ? "Reenviar dados atuais" : "Sincronizar agora"}</button></div>` : ""}
      </div></div>

      <div class="card"><h2>Histórico de microchips</h2>
        ${chips.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Código</th><th>Vinculado em</th><th>Veterinário</th><th>Situação</th><th>Substituição</th></tr></thead><tbody>
          ${chips.map((c) => `<tr><td data-label="Código" class="mono">${esc(c.codigo_microchip)}</td><td data-label="Vinculado em">${fmtDataHora(c.data_vinculo)}</td>
            <td data-label="Veterinário">${esc(c.veterinario_nome)}<br><span class="pequeno suave">CRMV ${esc(c.crmv_numero)}/${esc(c.crmv_uf)}</span></td>
            <td data-label="Situação">${c.situacao === "ATIVO" ? badge("ATIVO", "ok", "Vigente") : badge("SUBSTITUIDO", "neutro", "Substituído")}</td>
            <td data-label="Substituição" class="pequeno">${c.data_substituicao ? `${fmtDataHora(c.data_substituicao)}<br>${esc(c.motivo_substituicao || "")}` : "—"}</td></tr>`).join("")}
        </tbody></table></div><p class="pequeno suave">Um código de microchip nunca é reutilizado, mesmo depois de substituído.</p>` : vazio("Nenhum microchip vinculado até agora.")}</div></div>`;
  }

  function formMicrochip() {
    const troca = !!animal.microchip_atual;
    abrirModal(troca ? "Substituir microchip" : "Vincular microchip", `<form novalidate>
      ${troca ? `<div class="aviso-caixa">Microchip atual: <strong class="mono">${esc(animal.microchip_atual.codigo)}</strong>. Ele continua no histórico e não poderá ser reutilizado.</div>` : ""}
      ${campo({ nome: "codigo", rotulo: "Código do microchip (15 dígitos)", obrig: true, attrs: 'inputmode="numeric" maxlength="15" autocomplete="off"', ajuda: "Padrão ISO 11784/11785: somente números." })}
      <p><button type="button" class="btn mini" data-gerar>Gerar código simulado</button></p>
      ${troca ? campo({ nome: "motivo_substituicao", rotulo: "Motivo da substituição", tipo: "textarea", obrig: true, attrs: 'maxlength="255"' }) : ""}
      <div class="info-caixa">Ao vincular, o cadastro do animal é comunicado ao governo. Se o governo estiver fora do ar, a comunicação fica pendente e pode ser reenviada.</div>
      <div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">${troca ? "Substituir" : "Vincular"}</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      dlg.querySelector("[data-gerar]").onclick = () => { form.elements.codigo.value = gerarMicrochip(); };
      form.onsubmit = (ev) => {
        ev.preventDefault();
        enviarForm(form, {
          regras: {
            codigo: (v) => (microchipValido(v) ? null : "O microchip deve ter exatamente 15 dígitos numéricos."),
            ...(troca ? { motivo_substituicao: obrigatorio("Informe o motivo da substituição.") } : {}),
          },
          enviar: async (d) => {
            const r = await api.post(`/animais/${id}/microchip`, { codigo: d.codigo, substituir: troca, motivo_substituicao: d.motivo_substituicao || null });
            dlg.close();
            toast(troca ? "Microchip substituído." : "Microchip vinculado.");
            avisoGoverno(r.integracao_governo, "Cadastro no governo");
            await recarregar();
          },
        });
      };
    });
  }

  async function sincronizar(botao) {
    botao.disabled = true;
    try {
      const r = await api.post(`/animais/${id}/sincronizar`);
      avisoGoverno(r.operacao, "Sincronização");
      await recarregar();
    } finally { botao.disabled = false; }
  }

  // ------------------------------------------------------------------ aba: consultas
  async function abaConsultas() {
    const lista = await api.get(`/animais/${id}/consultas`);
    consultasPorId = Object.fromEntries(lista.map((c) => [c.id, c]));
    return `<div class="cabecalho" style="margin:0 0 .75rem"><div><h2>Histórico de consultas</h2></div>
      ${animal.situacao === "ATIVO" ? '<button class="btn primario" data-act="nova-consulta">Nova consulta</button>' : ""}</div>
      <div class="card">${lista.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Data / hora</th><th>Motivo</th><th>Diagnóstico</th><th>Peso</th><th>Veterinário</th><th>Situação</th><th></th></tr></thead><tbody>
        ${lista.map((c) => `<tr><td data-label="Data / hora">${fmtDataHora(c.data_hora)}</td><td data-label="Motivo">${esc(c.motivo)}</td>
          <td data-label="Diagnóstico">${cortar(c.diagnostico, 70)}</td><td data-label="Peso">${c.peso_kg ? `${esc(c.peso_kg)} kg` : "—"}</td>
          <td data-label="Veterinário">${esc(c.veterinario_nome)}</td><td data-label="Situação">${badge(c.situacao)}</td>
          <td class="acoes-cel">${c.situacao === "AGENDADA" ? `<button class="btn mini primario" data-act="atender-consulta" data-alvo="${c.id}">Atender</button> ` : ""}<button class="btn mini" data-act="ver-consulta" data-alvo="${c.id}">Ver</button>
            ${c.situacao !== "CANCELADA" ? `<button class="btn mini" data-act="editar-consulta" data-alvo="${c.id}">Editar</button>` : ""}
            ${c.situacao === "AGENDADA" ? `<button class="btn mini" data-act="faltou-consulta" data-alvo="${c.id}">Faltou</button>
            <button class="btn mini perigo" data-act="cancelar-consulta" data-alvo="${c.id}">Cancelar</button>` : ""}</td></tr>`).join("")}
        </tbody></table></div>` : vazio("Nenhuma consulta registrada para este animal.")}</div>`;
  }

  function verConsulta(c) {
    const bloco = (t, v) => (v ? `<h3>${t}</h3><p style="white-space:pre-wrap;margin:.2rem 0">${esc(v)}</p>` : "");
    abrirModal(`Consulta de ${fmtDataHora(c.data_hora)}`, `<dl class="kv"><dt>Motivo</dt><dd>${esc(c.motivo)}</dd>
      <dt>Situação</dt><dd>${badge(c.situacao)}</dd><dt>Veterinário</dt><dd>${esc(c.veterinario_nome)}</dd>
      <dt>Peso</dt><dd>${c.peso_kg ? `${esc(c.peso_kg)} kg` : "—"}</dd><dt>Temperatura</dt><dd>${c.temperatura_c ? `${esc(c.temperatura_c)} °C` : "—"}</dd></dl>
      ${bloco("Anamnese", c.anamnese)}${bloco("Sintomas", c.sintomas)}${bloco("Diagnóstico", c.diagnostico)}
      ${bloco("Tratamento", c.tratamento)}${bloco("Prescrição de medicamentos", c.prescricao_medicamentos)}${bloco("Observações", c.observacoes)}`);
  }

  const SITUACAO_CONSULTA = { REALIZADA: "Realizada", AGENDADA: "Agendada", NAO_COMPARECEU: "Não compareceu" };
  const paraInputLocal = (dh) => String(dh).replace(" ", "T").slice(0, 16);

  /**
   * Formulário de consulta. Sem `c`: nova consulta. Com `c`: edição de uma consulta existente (PUT).
   * `atender`: conclui uma consulta AGENDADA (vira REALIZADA) registrando o atendimento clínico.
   */
  function formConsulta(c = null, { atender = false } = {}) {
    const agora = agoraLocal();
    let opcoes = [["REALIZADA", "Realizada"], ["AGENDADA", "Agendada"]];
    if (c) opcoes = c.situacao === "REALIZADA" || atender ? [["REALIZADA", "Realizada"]]
      : ["AGENDADA", "REALIZADA", "NAO_COMPARECEU"].map((s) => [s, SITUACAO_CONSULTA[s]]);
    // ao atender uma consulta marcada para o futuro, o atendimento acontece "agora"
    const quando = !c ? agora : atender && paraInputLocal(c.data_hora) > agora ? agora : paraInputLocal(c.data_hora);
    const titulo = atender ? "Registrar atendimento" : c ? "Editar consulta" : "Nova consulta";
    const rotuloBotao = atender ? "Concluir consulta" : c ? "Salvar alterações" : "Registrar consulta";
    abrirModal(titulo, `<form novalidate>${atender ? '<p class="pequeno suave">O atendimento ficará registrado em nome do veterinário logado.</p>' : ""}<div class="form-grade">
      ${campo({ nome: "data_hora", rotulo: "Data e hora", tipo: "datetime-local", valor: quando, obrig: true })}
      ${campo({ nome: "situacao", rotulo: "Situação", valor: atender ? "REALIZADA" : c ? c.situacao : "REALIZADA", obrig: true, opcoes })}
      ${campo({ nome: "motivo", rotulo: "Motivo da consulta", obrig: true, largo: true, valor: c?.motivo, attrs: 'maxlength="255"' })}
      ${campo({ nome: "peso_kg", rotulo: "Peso na consulta (kg)", tipo: "number", valor: c?.peso_kg ?? "", attrs: 'step="0.01" min="0.01"', ajuda: "Atualiza o peso atual do animal (se for a consulta mais recente com peso)." })}
      ${campo({ nome: "temperatura_c", rotulo: "Temperatura (°C)", tipo: "number", valor: c?.temperatura_c ?? "", attrs: 'step="0.1" min="30" max="45"' })}
      ${campo({ nome: "anamnese", rotulo: "Anamnese", tipo: "textarea", largo: true, valor: c?.anamnese })}
      ${campo({ nome: "sintomas", rotulo: "Sintomas", tipo: "textarea", largo: true, valor: c?.sintomas })}
      ${campo({ nome: "diagnostico", rotulo: "Diagnóstico", tipo: "textarea", largo: true, valor: c?.diagnostico })}
      ${campo({ nome: "tratamento", rotulo: "Tratamento", tipo: "textarea", largo: true, valor: c?.tratamento })}
      ${campo({ nome: "prescricao_medicamentos", rotulo: "Prescrição de medicamentos", tipo: "textarea", largo: true, valor: c?.prescricao_medicamentos })}
      ${campo({ nome: "observacoes", rotulo: "Observações", tipo: "textarea", largo: true, valor: c?.observacoes })}
    </div><div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">${rotuloBotao}</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      form.onsubmit = (ev) => {
        ev.preventDefault();
        enviarForm(form, {
          regras: {
            data_hora: (v, d) => {
              if (!v) return "Informe a data e a hora.";
              return d.situacao === "REALIZADA" && v > agoraLocal() ? "Uma consulta realizada não pode estar no futuro." : null;
            },
            motivo: obrigatorio("Informe o motivo da consulta."),
            temperatura_c: (v) => (v && (Number(v) < 30 || Number(v) > 45) ? "Temperatura entre 30 e 45 °C." : null),
          },
          enviar: async (d) => {
            if (c) {
              // na edição o responsável original é mantido; ao atender, vale o veterinário logado
              await api.put(`/consultas/${c.id}`, atender ? d : { ...d, veterinario_id: c.veterinario_id });
            } else {
              await api.post("/consultas", { ...d, animal_id: id });
            }
            dlg.close();
            toast(atender ? "Atendimento registrado. Consulta realizada." : c ? "Consulta atualizada." : "Consulta registrada.");
            await recarregar();
          },
        });
      };
    });
  }

  // ------------------------------------------------------------------ aba: vacinas
  function colunaGoverno(v) {
    const g = v.comunicacao_governo;
    if (v.situacao === "AGENDADA") return v.antirrabica ? '<span class="pequeno suave">Será comunicada ao aplicar</span>' : badge("NAO_APLICAVEL");
    if (v.situacao !== "APLICADA" || !g.obrigatoria) return badge("NAO_APLICAVEL");
    return `${badge(g.situacao)}${g.protocolo ? `<br><span class="mono pequeno">${esc(g.protocolo)}</span>` : ""}
      ${g.situacao !== "CONFIRMADA" && g.integracao_id ? `<br><button class="btn mini primario" data-int-reenviar="${g.integracao_id}">Reenviar</button>` : ""}`;
  }

  async function abaVacinas() {
    const [lista, proximas] = await Promise.all([api.get(`/animais/${id}/vacinas`), api.get(`/animais/${id}/vacinas/proximas-doses`)]);
    vacinasPorId = Object.fromEntries(lista.map((v) => [v.id, v]));
    return `<div class="cabecalho" style="margin:0 0 .75rem"><div><h2>Vacinas</h2></div>
      ${animal.situacao === "ATIVO" ? '<button class="btn primario" data-act="nova-vacina">Registrar vacina</button>' : ""}</div>
      <div class="card"><h3 style="margin-top:0">Próximas doses</h3>
        ${proximas.length ? `<ul class="lista-simples">${proximas.map((p) => {
          const [cor, rot] = PRAZO[p.situacao_prazo];
          const quando = p.dias_para_a_data < 0 ? `${-p.dias_para_a_data} dia(s) de atraso` : p.dias_para_a_data === 0 ? "hoje" : `em ${p.dias_para_a_data} dia(s)`;
          return `<li><strong>${esc(p.nome_vacina)}</strong> <span class="suave pequeno">${p.origem === "AGENDADA" ? "agendada" : "reforço previsto"}</span> · ${fmtData(p.data_prevista)} (${quando}) ${badge(p.situacao_prazo, cor, rot)}</li>`;
        }).join("")}</ul>` : '<p class="suave">Nenhuma dose futura prevista.</p>'}</div>
      <div class="card"><h3 style="margin-top:0">Histórico de vacinação</h3>
        ${lista.length ? `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>Vacina</th><th>Dose</th><th>Data</th><th>Lote</th><th>Próx. dose</th><th>Situação</th><th>Governo</th><th></th></tr></thead><tbody>
          ${lista.map((v) => `<tr><td data-label="Vacina"><strong>${esc(v.nome_vacina)}</strong>${v.antirrabica ? ' <span class="badge info">Antirrábica</span>' : ""}<br><span class="pequeno suave">${esc(ROTULO_TIPO[v.tipo_vacina] || v.tipo_vacina)}</span></td>
            <td data-label="Dose">${esc(v.dose)}</td><td data-label="Data">${fmtData(v.data_aplicacao)}</td>
            <td data-label="Lote" class="pequeno">${v.numero_lote ? `${esc(v.numero_lote)}<br>val. ${fmtData(v.validade_lote)}` : "—"}</td>
            <td data-label="Próx. dose">${fmtData(v.data_proxima_dose)}</td><td data-label="Situação">${badge(v.situacao)}</td>
            <td data-label="Governo">${colunaGoverno(v)}</td>
            <td class="acoes-cel">${v.situacao === "AGENDADA" ? `<button class="btn mini primario" data-act="aplicar-vacina" data-alvo="${v.id}">Aplicar</button>
              <button class="btn mini perigo" data-act="cancelar-vacina" data-alvo="${v.id}">Cancelar</button>` : ""}</td></tr>`).join("")}
        </tbody></table></div>` : vazio("Nenhuma vacina registrada para este animal.")}</div>`;
  }

  /** Mostra o resultado separando "registro local" de "confirmação do governo": são fatos distintos. */
  function resultadoVacina(r) {
    const v = r.vacina;
    const g = r.comunicacao_governo;
    let caixaGov;
    if (v.situacao === "AGENDADA") {
      caixaGov = `<div class="info-caixa">Vacina agendada.${v.antirrabica ? " A comunicação obrigatória ao governo será feita quando a aplicação for registrada." : ""}</div>`;
    } else if (!g) {
      caixaGov = '<div class="info-caixa">Esta vacina não é antirrábica, portanto <strong>não há comunicação obrigatória</strong> ao governo.</div>';
    } else if (g.situacao === "CONFIRMADA") {
      caixaGov = `<div class="ok-caixa">O governo <strong>confirmou</strong> a comunicação. Protocolo <span class="mono">${esc(g.protocolo_externo)}</span>.</div>`;
    } else if (g.situacao === "FALHA") {
      caixaGov = `<div class="erro-caixa">O governo <strong>não aceitou</strong> a comunicação. ${esc(g.mensagem_erro || "")}</div>`;
    } else if (g.situacao === "ENVIADA") {
      caixaGov = `<div class="aviso-caixa">O envio foi feito, mas <strong>não houve resposta conclusiva</strong> (tempo esgotado ou erro do servidor). A vacina está registrada e o reenvio é seguro: o governo não duplica a mesma vacinação.</div>`;
    } else {
      caixaGov = `<div class="aviso-caixa">O <strong>governo está indisponível</strong>. A vacina foi registrada na clínica e a comunicação ficou <strong>PENDENTE</strong>; ela pode ser reenviada depois, sem perder dados.</div>`;
    }
    const dlg = abrirModal(v.situacao === "AGENDADA" ? "Vacina agendada" : "Vacina registrada", `<dl class="kv">
      <dt>Registro na clínica</dt><dd>${badge(v.situacao)} ${esc(v.nome_vacina)} (${esc(v.dose)})</dd>
      <dt>Comunicação ao governo</dt><dd>${g ? badge(g.situacao) : badge("NAO_APLICAVEL")}</dd></dl>${caixaGov}
      <div class="modal-rodape"><button class="btn primario" data-fechar>Entendi</button></div>`);
    dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
  }

  function formVacina() {
    abrirModal("Registrar vacina", `<form novalidate><div id="avisos" aria-live="polite"></div><div class="form-grade">
      ${campo({ nome: "nome_vacina", rotulo: "Nome da vacina", obrig: true, attrs: 'maxlength="100"' })}
      ${campo({ nome: "tipo_vacina", rotulo: "Tipo", obrig: true, opcoes: [["", "Selecione"], ...TIPOS_VACINA] })}
      ${campo({ nome: "situacao", rotulo: "Registro", valor: "APLICADA", obrig: true, opcoes: [["APLICADA", "Aplicada agora"], ["AGENDADA", "Agendar para depois"]] })}
      ${campo({ nome: "data_aplicacao", rotulo: "Data da aplicação / agendamento", tipo: "date", valor: hojeISO(), obrig: true })}
      ${campo({ nome: "dose", rotulo: "Dose", obrig: true, attrs: 'maxlength="40" placeholder="Ex.: 1ª dose, reforço anual"' })}
      ${campo({ nome: "via_aplicacao", rotulo: "Via de aplicação", obrig: true, opcoes: [["", "Selecione"], ...VIAS] })}
      ${campo({ nome: "fabricante", rotulo: "Fabricante", ajuda: "Obrigatório para vacina aplicada.", attrs: 'maxlength="100"' })}
      ${campo({ nome: "numero_lote", rotulo: "Número do lote", ajuda: "Obrigatório para vacina aplicada.", attrs: 'maxlength="50"' })}
      ${campo({ nome: "validade_lote", rotulo: "Validade do lote", tipo: "date", ajuda: "Obrigatória para vacina aplicada." })}
      ${campo({ nome: "data_proxima_dose", rotulo: "Próxima dose (reforço)", tipo: "date" })}
      ${campo({ nome: "observacoes", rotulo: "Observações", tipo: "textarea", largo: true })}
    </div><div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">Registrar</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      const avisos = dlg.querySelector("#avisos");
      const atualizarAvisos = () => {
        const antirrabica = form.elements.tipo_vacina.value === "ANTIRRABICA";
        const aplicada = form.elements.situacao.value === "APLICADA";
        let html = "";
        if (antirrabica && aplicada) {
          html = '<div class="info-caixa"><strong>Vacina antirrábica:</strong> a aplicação é comunicada obrigatoriamente ao governo, identificada pelo microchip do animal.</div>';
          if (!animal.microchip_atual) html += '<div class="erro-caixa">Este animal não tem microchip. Vincule o microchip antes de registrar a antirrábica aplicada.</div>';
        }
        avisos.innerHTML = html;
      };
      form.elements.tipo_vacina.onchange = atualizarAvisos;
      form.elements.situacao.onchange = atualizarAvisos;
      const exigeSeAplicada = (msg) => (v, d) => (d.situacao === "APLICADA" && !v ? msg : null);
      form.onsubmit = (ev) => {
        ev.preventDefault();
        enviarForm(form, {
          regras: {
            nome_vacina: obrigatorio(), tipo_vacina: obrigatorio("Selecione o tipo da vacina."),
            dose: obrigatorio(), via_aplicacao: obrigatorio("Selecione a via de aplicação."),
            data_aplicacao: (v, d) => {
              if (!v) return "Informe a data.";
              if (d.situacao === "APLICADA" && v > hojeISO()) return "Vacina aplicada não pode ter data futura.";
              return d.situacao === "AGENDADA" && v < hojeISO() ? "Vacina agendada deve ser de hoje em diante." : null;
            },
            fabricante: exigeSeAplicada("Informe o fabricante."), numero_lote: exigeSeAplicada("Informe o lote."),
            validade_lote: (v, d) => {
              if (d.situacao === "APLICADA" && !v) return "Informe a validade do lote.";
              return v && d.situacao === "APLICADA" && d.data_aplicacao && v < d.data_aplicacao ? "O lote estava vencido na data da aplicação." : null;
            },
            data_proxima_dose: (v, d) => (v && d.data_aplicacao && v <= d.data_aplicacao ? "Deve ser posterior à data de aplicação." : null),
          },
          enviar: async (d) => {
            const r = await api.post("/vacinas", { ...d, animal_id: id });
            dlg.close();
            resultadoVacina(r);
            await recarregar();
          },
        });
      };
    });
  }

  function formAplicar(v) {
    abrirModal(`Aplicar: ${v.nome_vacina}`, `<form novalidate>
      ${v.antirrabica ? '<div class="info-caixa">Vacina antirrábica: a aplicação será comunicada ao governo.</div>' : ""}
      ${!animal.microchip_atual && v.antirrabica ? '<div class="erro-caixa">Este animal não tem microchip. Vincule-o antes de aplicar a antirrábica.</div>' : ""}
      <div class="form-grade">
      ${campo({ nome: "data_aplicacao", rotulo: "Data da aplicação", tipo: "date", valor: hojeISO(), obrig: true })}
      ${campo({ nome: "fabricante", rotulo: "Fabricante", obrig: true })}
      ${campo({ nome: "numero_lote", rotulo: "Número do lote", obrig: true })}
      ${campo({ nome: "validade_lote", rotulo: "Validade do lote", tipo: "date", obrig: true })}
      ${campo({ nome: "data_proxima_dose", rotulo: "Próxima dose (reforço)", tipo: "date", valor: v.data_proxima_dose })}
      </div><div class="modal-rodape"><button type="button" class="btn" data-fechar>Cancelar</button><button type="submit" class="btn primario">Registrar aplicação</button></div></form>`, (dlg) => {
      const form = dlg.querySelector("form");
      dlg.querySelector("[data-fechar]").onclick = () => dlg.close();
      form.onsubmit = (ev) => {
        ev.preventDefault();
        enviarForm(form, {
          regras: {
            data_aplicacao: (val) => (!val ? "Informe a data." : val > hojeISO() ? "Vacina aplicada não pode ter data futura." : null),
            fabricante: obrigatorio(), numero_lote: obrigatorio(),
            validade_lote: (val, d) => (!val ? "Informe a validade do lote." : d.data_aplicacao && val < d.data_aplicacao ? "O lote estava vencido na data da aplicação." : null),
            data_proxima_dose: (val, d) => (val && d.data_aplicacao && val <= d.data_aplicacao ? "Deve ser posterior à data de aplicação." : null),
          },
          enviar: async (d) => {
            const r = await api.post(`/vacinas/${v.id}/aplicar`, d);
            dlg.close();
            resultadoVacina(r);
            await recarregar();
          },
        });
      };
    });
  }

  // ------------------------------------------------------------------ aba: governo
  async function abaGoverno() {
    const g = await api.get(`/animais/${id}/integracao-governo`);
    return `<div class="card"><div class="cabecalho" style="margin:0 0 .5rem"><div><h2>Comunicação com o governo</h2>
        <p class="suave">Cadastro do animal, atualizações e vacinação antirrábica enviados à API governamental simulada.</p></div>
        ${animal.microchip_atual ? '<button class="btn primario" data-act="sincronizar">Sincronizar agora</button>' : ""}</div>
      ${animal.microchip_atual ? "" : '<div class="aviso-caixa">Sem microchip: o animal ainda não pode ser registrado no governo.</div>'}
      <dl class="kv"><dt>Cadastro</dt><dd>${badge(g.situacao_cadastro)}</dd><dt>Protocolo</dt><dd class="mono">${esc(g.protocolo_cadastro || "—")}</dd>
        <dt>Sincronizado</dt><dd>${g.sincronizado ? '<span class="badge ok">Sim</span>' : '<span class="badge aviso">Não</span>'}</dd>
        <dt>Pendências</dt><dd>${g.pendencias}</dd></dl>
      <h3>Operações</h3>${tabelaIntegracoes(g.operacoes, { mostrarAnimal: false })}</div>`;
  }

  const RENDER = { resumo: abaResumo, consultas: abaConsultas, vacinas: abaVacinas, governo: abaGoverno };

  // ------------------------------------------------------------------ eventos (delegados, ligados uma única vez)
  el.querySelector(".abas").onclick = (ev) => {
    const b = ev.target.closest("[data-aba]");
    if (b && b.dataset.aba !== aba) { aba = b.dataset.aba; mostrarAba(); }
  };
  ligarIntegracoes(caixa, recarregar);                       // botões Detalhes / Reenviar das tabelas de integração
  caixa.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-act]");
    if (!b) return;
    const alvo = Number(b.dataset.alvo);
    try {
      switch (b.dataset.act) {
        case "novo-chip": case "trocar-chip": formMicrochip(); break;
        case "sincronizar": await sincronizar(b); break;
        case "nova-consulta": formConsulta(); break;
        case "ver-consulta": verConsulta(consultasPorId[alvo]); break;
        case "atender-consulta": formConsulta(consultasPorId[alvo], { atender: true }); break;
        case "editar-consulta": formConsulta(consultasPorId[alvo]); break;
        case "faltou-consulta": {
          const c = consultasPorId[alvo];
          if (await confirmar("Não compareceu", `Registrar que o tutor não compareceu à consulta de ${fmtDataHora(c.data_hora)}?`, "Registrar falta")) {
            await api.put(`/consultas/${alvo}`, {
              data_hora: paraInputLocal(c.data_hora), motivo: c.motivo, veterinario_id: c.veterinario_id,
              peso_kg: c.peso_kg, temperatura_c: c.temperatura_c, situacao: "NAO_COMPARECEU",
              anamnese: c.anamnese, sintomas: c.sintomas, diagnostico: c.diagnostico, tratamento: c.tratamento,
              prescricao_medicamentos: c.prescricao_medicamentos, observacoes: c.observacoes,
            });
            toast("Falta registrada: consulta marcada como Não compareceu."); await mostrarAba();
          }
          break;
        }
        case "cancelar-consulta":
          if (await confirmar("Cancelar consulta", "A consulta agendada será cancelada.", "Cancelar consulta", true)) {
            await api.del(`/consultas/${alvo}`); toast("Consulta cancelada."); await mostrarAba();
          }
          break;
        case "nova-vacina": formVacina(); break;
        case "aplicar-vacina": formAplicar(vacinasPorId[alvo]); break;
        case "cancelar-vacina":
          if (await confirmar("Cancelar vacina", "O agendamento será cancelado.", "Cancelar vacina", true)) {
            await api.del(`/vacinas/${alvo}`); toast("Vacina cancelada."); await mostrarAba();
          }
          break;
        default: break;
      }
    } catch (e) { toastErro(e); }
  });

  cabecalho();
  await mostrarAba();
}
