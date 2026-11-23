import { api, qs } from "../api.js";
import { abrirModal, badge, carregando, esc, fmtDataHora, toast, toastErro, vazio } from "../ui.js";

const TIPOS = { CADASTRO_ANIMAL: "Cadastro de animal", ATUALIZACAO_ANIMAL: "Atualização de animal", VACINACAO_ANTIRRABICA: "Vacinação antirrábica" };

export function tabelaIntegracoes(lista, { mostrarAnimal = true } = {}) {
  if (!lista.length) return vazio("Nenhuma operação de integração registrada.");
  return `<div class="tabela-wrap"><table class="responsiva"><thead><tr><th>#</th><th>Operação</th>${mostrarAnimal ? "<th>Animal</th>" : ""}<th>Situação</th><th>Protocolo</th><th>Datas</th><th></th></tr></thead><tbody>
    ${lista.map((i) => `<tr><td data-label="#">${i.id}</td><td data-label="Operação">${esc(TIPOS[i.tipo_operacao] || i.tipo_operacao)}${i.vacina_id ? `<br><span class="pequeno suave">vacina #${i.vacina_id}</span>` : ""}</td>
      ${mostrarAnimal ? `<td data-label="Animal"><a href="#/animais/${i.animal_id}">${esc(i.animal_nome)}</a><br><span class="mono pequeno suave">${esc(i.microchip || "")}</span></td>` : ""}
      <td data-label="Situação">${badge(i.situacao)}<br><span class="pequeno suave">${i.tentativas} tentativa${i.tentativas === 1 ? "" : "s"}</span>${i.mensagem_erro ? `<br><span class="pequeno suave">${esc(i.mensagem_erro).slice(0, 90)}${i.mensagem_erro.length > 90 ? "…" : ""}</span>` : ""}</td>
      <td data-label="Protocolo" class="mono pequeno" style="word-break:break-all;min-width:9rem">${esc(i.protocolo_externo || "—")}</td>
      <td data-label="Datas" class="pequeno">Enviada: ${fmtDataHora(i.solicitada_em)}<br>Resposta: ${fmtDataHora(i.respondida_em)}</td>
      <td class="acoes-cel"><button class="btn mini" data-int-ver="${i.id}">Detalhes</button>
        ${i.situacao === "CONFIRMADA" ? `<button class="btn mini" data-int-reenviar="${i.id}" data-forcar="1" title="Reenvia a mesma operação: o governo deve devolver o mesmo protocolo, sem duplicar">Testar idempotência</button>`
          : `<button class="btn mini primario" data-int-reenviar="${i.id}">Reenviar</button>`}</td></tr>`).join("")}</tbody></table></div>`;
}

/** Liga os botões da tabela acima. `aoMudar` é chamado depois de qualquer reenvio. */
export function ligarIntegracoes(container, aoMudar) {
  container.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-int-ver],[data-int-reenviar]");
    if (!b) return;
    try {
      if (b.dataset.intVer) return detalhe(await api.get(`/integracoes/${b.dataset.intVer}`));
      b.disabled = true;
      const forcar = b.dataset.forcar ? "?forcar=true" : "";
      const r = await api.post(`/integracoes/${b.dataset.intReenviar}/reenviar${forcar}`);
      if (forcar) {
        const rep = r.ultima_resposta?.repeticao_idempotente;
        toast(rep ? `O governo reconheceu a repetição e devolveu o mesmo protocolo (${r.protocolo_externo}). Nada foi duplicado.` : "Reenvio concluído.", "ok", 8000);
      } else if (r.situacao === "CONFIRMADA") toast(`Confirmada pelo governo. Protocolo ${r.protocolo_externo}.`);
      else toast(`Continua ${r.situacao.toLowerCase()}: ${r.mensagem_erro || ""}`, r.situacao === "FALHA" ? "erro" : "aviso", 8000);
      aoMudar?.();
    } catch (e) { toastErro(e); b.disabled = false; }
  });
}

function detalhe(i) {
  abrirModal(`Integração #${i.id}`, `<dl class="kv">
    <dt>Operação</dt><dd>${esc(TIPOS[i.tipo_operacao] || i.tipo_operacao)}</dd><dt>Animal</dt><dd>${esc(i.animal_nome)} <span class="mono pequeno">${esc(i.microchip || "")}</span></dd>
    <dt>Situação</dt><dd>${badge(i.situacao)}</dd><dt>Protocolo externo</dt><dd class="mono">${esc(i.protocolo_externo || "—")}</dd>
    <dt>Chave de idempotência</dt><dd class="mono pequeno">${esc(i.chave_idempotencia)}</dd><dt>Tentativas</dt><dd>${i.tentativas}</dd>
    <dt>Solicitada em</dt><dd>${fmtDataHora(i.solicitada_em)}</dd><dt>Última tentativa</dt><dd>${fmtDataHora(i.ultima_tentativa_em)}</dd>
    <dt>Resposta em</dt><dd>${fmtDataHora(i.respondida_em)}</dd></dl>
    ${i.mensagem_erro ? `<div class="aviso-caixa"><strong>Mensagem:</strong> ${esc(i.mensagem_erro)}</div>` : ""}
    <h3>Último payload enviado</h3><pre class="json">${esc(JSON.stringify(i.payload_enviado, null, 2) || "—")}</pre>`);
}

export async function integracoes(el) {
  const filtro = { situacao: "", tipo_operacao: "" };
  el.innerHTML = `<div class="cabecalho"><div><h1>Integração com o governo</h1>
    <p class="suave">Registro de cada comunicação com a API governamental simulada: pendências, protocolos e reenvios.</p></div>
    <button class="btn primario" id="lote">Reprocessar pendências</button></div>
    <div class="card"><div class="filtros">
      <select id="sit" aria-label="Situação"><option value="">Todas as situações</option><option>PENDENTE</option><option>ENVIADA</option><option>CONFIRMADA</option><option>FALHA</option></select>
      <select id="tipo" aria-label="Tipo"><option value="">Todos os tipos</option>${Object.entries(TIPOS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></div>
      <div id="lista">${carregando()}</div></div>`;
  async function carregar() {
    const caixa = el.querySelector("#lista");
    if (!caixa) return;   // a tela já foi trocada (ex.: busca com atraso ou resposta tardia)
    try { caixa.innerHTML = tabelaIntegracoes(await api.get(`/integracoes${qs(filtro)}`)); }
    catch (e) { caixa.innerHTML = `<div class="erro-caixa">${esc(e.message)}</div>`; }
  }
  el.querySelector("#sit").onchange = (e) => { filtro.situacao = e.target.value; carregar(); };
  el.querySelector("#tipo").onchange = (e) => { filtro.tipo_operacao = e.target.value; carregar(); };
  el.querySelector("#lote").onclick = async (ev) => {
    ev.target.disabled = true;
    try {
      const s = await api.post("/integracoes/reprocessar-pendentes");
      toast(`Analisadas ${s.analisadas}: ${s.confirmadas} confirmada(s), ${s.ainda_pendentes} ainda pendente(s), ${s.falhas} falha(s).`, s.ainda_pendentes ? "aviso" : "ok", 7000);
      carregar();
    } catch (e) { toastErro(e); } finally { ev.target.disabled = false; }
  };
  ligarIntegracoes(el.querySelector("#lista"), carregar);
  carregar();
}
