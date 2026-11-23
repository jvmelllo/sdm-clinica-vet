// Cliente da API REST da clínica. Toda a comunicação frontend <-> backend passa por aqui.
const CHAVE = "sdm_sessao";

export class ApiErro extends Error {
  constructor(status, corpo) {
    super(corpo?.erro?.mensagem || "Erro inesperado.");
    this.status = status;
    this.codigo = corpo?.erro?.codigo || "ERRO";
    this.detalhes = corpo?.erro?.detalhes || null;
    this.corpo = corpo;
  }
}

export const sessao = {
  get dados() { try { return JSON.parse(sessionStorage.getItem(CHAVE)); } catch { return null; } },
  get token() { return this.dados?.token || null; },
  get vet() { return this.dados?.veterinario || null; },
  salvar(token, veterinario) { sessionStorage.setItem(CHAVE, JSON.stringify({ token, veterinario })); },
  limpar() { sessionStorage.removeItem(CHAVE); },
};

async function chamar(metodo, caminho, corpo) {
  const headers = { Accept: "application/json" };
  if (corpo !== undefined) headers["Content-Type"] = "application/json";
  if (sessao.token) headers.Authorization = `Bearer ${sessao.token}`;
  let resposta;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: metodo, headers, body: corpo !== undefined ? JSON.stringify(corpo) : undefined,
    });
  } catch {
    throw new ApiErro(0, { erro: { codigo: "REDE", mensagem: "Não foi possível falar com o servidor. Verifique se a API está no ar." } });
  }
  let dados = null;
  try { dados = await resposta.json(); } catch { /* sem corpo */ }
  if (!resposta.ok) {
    const sessaoPerdida = resposta.status === 401 && sessao.token && !caminho.startsWith("/auth/");
    if (sessaoPerdida) { sessao.limpar(); location.hash = "#/login"; }
    throw new ApiErro(resposta.status, dados);
  }
  return dados;
}

export const api = {
  get: (c) => chamar("GET", c),
  post: (c, b = {}) => chamar("POST", c, b),
  put: (c, b) => chamar("PUT", c, b),
  del: (c) => chamar("DELETE", c),
};

export const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj).forEach(([k, v]) => { if (v !== "" && v != null) p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
};
