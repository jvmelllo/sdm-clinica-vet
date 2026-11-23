// Ponto de entrada: roteamento por hash (#/painel, #/animais/3 ...) e "casca" da aplicação.
import { ApiErro, api, sessao } from "./api.js";
import { esc, erroCaixa, carregando, toast } from "./ui.js";
import { renderLogin } from "./views/login.js";
import { painel } from "./views/painel.js";
import { tutores } from "./views/tutores.js";
import { animais } from "./views/animais.js";
import { animalDetalhe } from "./views/animal.js";
import { catalogos } from "./views/catalogos.js";
import { integracoes } from "./views/integracoes.js";
import { veterinarios } from "./views/veterinarios.js";

const raiz = document.getElementById("raiz");
const ROTAS = [
  [/^#\/painel$/, painel], [/^#\/tutores$/, tutores], [/^#\/animais$/, animais],
  [/^#\/animais\/(\d+)$/, animalDetalhe], [/^#\/catalogos$/, catalogos],
  [/^#\/integracoes$/, integracoes], [/^#\/veterinarios$/, veterinarios],
];
const MENU = [["#/painel", "Painel"], ["#/tutores", "Tutores"], ["#/animais", "Animais"],
  ["#/catalogos", "Espécies e raças"], ["#/integracoes", "Governo (integração)"], ["#/veterinarios", "Veterinários"]];

let shellMontado = false;
let temporizadorStatus = null;

function montarShell() {
  const vet = sessao.vet;
  raiz.innerHTML = `<div class="app">
    <nav class="lateral" aria-label="Menu principal">
      <div class="marca"><span aria-hidden="true">🐾</span> Clínica Vet</div>
      ${MENU.map(([h, t]) => `<a href="${h}" data-menu="${h}">${t}</a>`).join("")}
      <div class="rodape">Projeto A3 · SDM<br>Dados fictícios</div>
    </nav>
    <div class="principal">
      <header class="topo">
        <span class="pilula" id="pilula-gov" title="Estado da API governamental simulada"><i></i><span>Governo…</span></span>
        <span class="pequeno suave">${esc(vet?.nome_completo || "")} · CRMV ${esc(vet?.crmv_numero || "")}/${esc(vet?.crmv_uf || "")}</span>
        <button class="btn mini" id="btn-sair">Sair</button>
      </header>
      <main class="conteudo" id="conteudo" tabindex="-1"></main>
    </div></div>`;
  document.getElementById("btn-sair").onclick = sair;
  shellMontado = true;
  atualizarStatus();
  clearInterval(temporizadorStatus);
  temporizadorStatus = setInterval(atualizarStatus, 15000);
}

async function atualizarStatus() {
  const pilula = document.getElementById("pilula-gov");
  if (!pilula) return;
  try {
    const r = await fetch("/api/status").then((x) => x.json());
    const ok = r.governo === "ok";
    pilula.className = `pilula ${ok ? "ok" : "erro"}`;
    pilula.querySelector("span").textContent = ok ? "Governo: no ar" : "Governo: indisponível";
  } catch {
    pilula.className = "pilula erro";
    pilula.querySelector("span").textContent = "API fora do ar";
  }
}

async function sair() {
  try { await api.post("/auth/logout"); } catch { /* sessão já encerrada */ }
  sessao.limpar();
  shellMontado = false;
  clearInterval(temporizadorStatus);
  location.hash = "#/login";
}

async function navegar() {
  const hash = location.hash || "#/painel";
  if (!sessao.token) {
    shellMontado = false;
    renderLogin(raiz);
    return;
  }
  if (hash === "#/login" || hash === "#/" || hash === "") { location.hash = "#/painel"; return; }
  if (!shellMontado) montarShell();
  document.querySelectorAll("[data-menu]").forEach((a) => a.classList.toggle("ativo", hash.startsWith(a.dataset.menu)));
  const conteudo = document.getElementById("conteudo");
  // Cada navegação ganha o SEU contêiner. Se o usuário trocar de página antes de a anterior terminar de carregar,
  // a resposta tardia da página antiga escreve num elemento já descartado e não sobrescreve a tela atual.
  const pagina = document.createElement("div");
  conteudo.replaceChildren(pagina);
  const caminho = hash.split("?")[0];            // "#/animais?tutor=3" casa com a rota "#/animais"
  const rota = ROTAS.map(([re, fn]) => [re.exec(caminho), fn]).find(([m]) => m);
  if (!rota) { pagina.innerHTML = '<div class="card vazio">Página não encontrada.</div>'; return; }
  pagina.innerHTML = carregando();
  atualizarStatus();
  try {
    await rota[1](pagina, rota[0].slice(1));
  } catch (e) {
    if (e instanceof ApiErro && e.status === 401) return;       // api.js já mandou para o login
    pagina.innerHTML = erroCaixa(e instanceof ApiErro ? e : new Error("Falha ao carregar a página."));
    if (!(e instanceof ApiErro)) console.error(e);
  }
  if (pagina.parentNode !== conteudo) return;                    // outra navegação já assumiu a tela
  conteudo.focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", navegar);
window.addEventListener("unhandledrejection", (ev) => {
  if (ev.reason instanceof ApiErro) { toast(ev.reason.message, "erro", 7000); ev.preventDefault(); }
});
navegar();
