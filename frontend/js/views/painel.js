import { api } from "../api.js";
import { badge, esc, toast, toastErro } from "../ui.js";

export async function painel(el) {
  const r = await api.get("/resumo");
  const i = r.integracoes;
  const pend = i.PENDENTE + i.ENVIADA;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Painel</h1><p class="suave">Visão geral da clínica e das comunicações com o governo.</p></div></div>
    ${r.governo_disponivel ? "" : '<div class="aviso-caixa"><strong>API governamental indisponível.</strong> Registros locais continuam funcionando; comunicações obrigatórias ficam pendentes e serão reenviadas.</div>'}
    <div class="grade">
      <div class="card"><div class="numero">${r.tutores_ativos}</div>Tutores ativos</div>
      <div class="card"><div class="numero">${r.animais_ativos}</div>Animais ativos</div>
      <div class="card"><div class="numero">${r.consultas_hoje}</div>Consultas hoje</div>
      <div class="card"><div class="numero">${r.consultas_agendadas}</div>Consultas agendadas</div>
      <div class="card"><div class="numero">${r.vacinas_com_reforco_atrasado}</div>Reforços de vacina atrasados</div>
    </div>
    <div class="grade-2">
      <div class="card"><h2>Comunicações ao governo</h2>
        <div class="grade" style="grid-template-columns:repeat(4,1fr)">
          <div><div class="numero">${i.CONFIRMADA}</div>${badge("CONFIRMADA")}</div>
          <div><div class="numero">${i.PENDENTE}</div>${badge("PENDENTE")}</div>
          <div><div class="numero">${i.ENVIADA}</div>${badge("ENVIADA")}</div>
          <div><div class="numero">${i.FALHA}</div>${badge("FALHA")}</div>
        </div>
        <p class="pequeno suave">Pendente: governo fora do ar, será reenviada. Enviada: sem resposta conclusiva (reenvio é seguro). Falha: rejeitada ou limite de tentativas.</p>
        <div class="acoes"><button class="btn primario" id="reprocessar" ${pend ? "" : "disabled"}>Reprocessar pendências (${pend})</button>
        <a class="btn" href="#/integracoes">Ver todas</a></div>
      </div>
      <div class="card" id="demo"></div>
    </div>`;

  el.querySelector("#reprocessar").onclick = async (ev) => {
    ev.target.disabled = true;
    try {
      const s = await api.post("/integracoes/reprocessar-pendentes");
      toast(`Analisadas ${s.analisadas}: ${s.confirmadas} confirmada(s), ${s.ainda_pendentes} ainda pendente(s), ${s.falhas} falha(s).`,
        s.ainda_pendentes ? "aviso" : "ok", 7000);
      painel(el);
    } catch (e) { toastErro(e); ev.target.disabled = false; }
  };
  montarDemo(el.querySelector("#demo"), painel, el);
}

async function montarDemo(card, recarregar, el) {
  let sim;
  try { sim = await api.get("/demo/governo/simulacao"); } catch (e) {
    card.innerHTML = e.status === 404 ? "" : `<h2>Simulação do governo</h2><div class="aviso-caixa">${esc(e.message)}</div>`;
    if (e.status === 404) card.remove();
    return;
  }
  card.innerHTML = `<h2>Simulação de falhas do governo <span class="badge info">demonstração</span></h2>
    <p class="pequeno suave">Controla a API governamental simulada para demonstrar indisponibilidade, pendência e reenvio.</p>
    <p>Modo atual: <strong>${esc(sim.modo)}</strong>${sim.modo === "RESPOSTA_LENTA" ? ` (atraso ${sim.atraso_s}s)` : ""}${sim.falhar_proximas ? ` · falhará nas próximas ${sim.falhar_proximas} chamadas` : ""}</p>
    <div class="acoes">
      <button class="btn" data-sim='{"modo":"NORMAL","falhar_proximas":0}'>Normal</button>
      <button class="btn perigo" data-sim='{"modo":"INDISPONIVEL"}'>Indisponível (503)</button>
      <button class="btn" data-sim='{"modo":"RESPOSTA_LENTA","atraso_s":6}'>Resposta lenta (timeout)</button>
      <button class="btn" data-sim='{"falhar_proximas":1}'>Falhar só a próxima</button>
    </div>`;
  card.querySelectorAll("[data-sim]").forEach((b) => {
    b.onclick = async () => {
      try { await api.put("/demo/governo/simulacao", JSON.parse(b.dataset.sim)); toast("Simulação atualizada.", "ok", 2500); recarregar(el); }
      catch (e) { toastErro(e); }
    };
  });
}
