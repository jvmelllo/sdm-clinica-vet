#!/usr/bin/env node
/**
 * Mini-runtime de Postman: executa a coleção (docs/postman/*.postman_collection.json) contra a pilha no ar,
 * rodando os scripts de pré-requisição e de teste EXATAMENTE como exportados (sem Newman, sem dependências).
 *
 * Uso:  node scripts/executar_colecao.js [colecao.json] [--json saida.json] [--ambiente "MySQL 8.4 + ViaCEP real"]
 *       --ambiente descreve onde a pilha estava rodando; fica gravado no --json e aparece no relatório de testes.
 * Variáveis opcionais: SDM_BASE (padrão http://localhost:5000), SDM_GOV (padrão http://localhost:5001)
 * Saída: código 0 se todas as asserções passaram; 1 caso contrário.
 *
 * Suporta o subconjunto de `pm` usado pela coleção: pm.test, pm.expect(...).to[.be|.have|.not].{eql,a,oneOf,include,above,
 * lengthOf,null,true,ok}, pm.response.{json(),to.have.status(n)} e pm.collectionVariables.{get,set}.
 */
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const iJson = args.indexOf("--json");
const arquivoSaida = iJson >= 0 ? args.splice(iJson, 2)[1] : null;
const iAmb = args.indexOf("--ambiente");
const ambiente = iAmb >= 0 ? args.splice(iAmb, 2)[1] : null;
const arquivo = args[0] || path.join(__dirname, "..", "docs", "postman", "SDM_Clinica_Vet.postman_collection.json");
const colecao = JSON.parse(fs.readFileSync(arquivo, "utf8"));

const vars = {};
(colecao.variable || []).forEach((v) => { vars[v.key] = v.value; });
if (process.env.SDM_BASE) vars.base = process.env.SDM_BASE;
if (process.env.SDM_GOV) vars.gov = process.env.SDM_GOV;

const subst = (s) => String(s).replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] === undefined || vars[k] === null ? "" : vars[k]));

function igual(a, b) { return JSON.stringify(a) === JSON.stringify(b); }

function expect(real) {
  let negar = false;
  const checa = (ok, msg) => { if (negar ? ok : !ok) throw new Error((negar ? "NÃO " : "") + msg); };
  const c = {
    get to() { return c; }, get be() { return c; }, get have() { return c; },
    get not() { negar = !negar; return c; },
    eql: (v) => checa(igual(real, v), `esperava ${JSON.stringify(v)} e veio ${JSON.stringify(real)}`),
    equal: (v) => checa(real === v, `esperava ${JSON.stringify(v)} e veio ${JSON.stringify(real)}`),
    include: (v) => checa(String(real).includes(v), `${JSON.stringify(real)} deveria conter ${JSON.stringify(v)}`),
    a: (t) => checa(typeof real === t && real !== "", `deveria ser ${t} (veio ${JSON.stringify(real)})`),
    oneOf: (lista) => checa(lista.some((x) => igual(x, real)), `${JSON.stringify(real)} deveria estar em ${JSON.stringify(lista)}`),
    above: (n) => checa(Number(real) > n, `${JSON.stringify(real)} deveria ser maior que ${n}`),
    lengthOf: (n) => checa(real != null && real.length === n, `tamanho esperado ${n}, veio ${real && real.length} (${JSON.stringify(real).slice(0, 120)})`),
    get null() { checa(real === null, `deveria ser null (veio ${JSON.stringify(real)})`); return c; },
    get true() { checa(real === true, `deveria ser true (veio ${JSON.stringify(real)})`); return c; },
    get ok() { checa(!!real, `deveria ser verdadeiro (veio ${JSON.stringify(real)})`); return c; },
  };
  return c;
}

function criarPm(resposta, resultados) {
  const variaveis = { get: (k) => vars[k], set: (k, v) => { vars[k] = v; } };
  return {
    collectionVariables: variaveis, environment: variaveis, variables: variaveis, expect,
    test(nome, fn) {
      try { fn(); resultados.push({ nome, ok: true }); } catch (e) { resultados.push({ nome, ok: false, erro: e.message }); }
    },
    response: resposta && {
      code: resposta.status, text: () => resposta.texto, json: () => JSON.parse(resposta.texto),
      to: { have: { status(n) { if (resposta.status !== n) throw new Error(`esperava HTTP ${n} e recebeu ${resposta.status}: ${resposta.texto.slice(0, 160)}`); } } },
    },
  };
}

const rodarScript = (linhas, pm) => new Function("pm", linhas.join("\n"))(pm);

async function main() {
  const resumo = { requisicoes: 0, asserções: 0, falhas: [] };
  const relatorio = [];
  const t0 = Date.now();
  for (const pasta of colecao.item) {
    console.log(`\n▸ ${pasta.name}`);
    for (const item of pasta.item) {
      resumo.requisicoes++;
      const resultados = [];
      const req = item.request;
      const ev = (tipo) => (item.event || []).filter((e) => e.listen === tipo);
      try {
        ev("prerequest").forEach((e) => rodarScript(e.script.exec, criarPm(null, resultados)));
        const headers = {};
        req.header.forEach((h) => { headers[h.key] = subst(h.value); });
        const init = { method: req.method, headers };
        if (req.body) init.body = subst(req.body.raw);
        const controle = new AbortController();
        const timer = setTimeout(() => controle.abort(), 20000);
        init.signal = controle.signal;
        const url = subst(req.url.raw);
        const r = await fetch(url, init).finally(() => clearTimeout(timer));
        const resposta = { status: r.status, texto: await r.text() };
        ev("test").forEach((e) => rodarScript(e.script.exec, criarPm(resposta, resultados)));
      } catch (e) {
        resultados.push({ nome: "execução da requisição", ok: false, erro: String(e.message || e) });
      }
      const falhou = resultados.filter((r) => !r.ok);
      resumo.asserções += resultados.length;
      console.log(`  ${falhou.length ? "✗" : "✓"} ${item.name}  (${resultados.length - falhou.length}/${resultados.length})`);
      falhou.forEach((f) => { console.log(`      ✗ ${f.nome}: ${f.erro}`); resumo.falhas.push({ pasta: pasta.name, requisicao: item.name, ...f }); });
      relatorio.push({ pasta: pasta.name, requisicao: item.name, metodo: req.method, resultados });
    }
  }
  const ok = resumo.asserções - resumo.falhas.length;
  console.log(`\n${resumo.falhas.length ? "FALHOU" : "OK"}: ${resumo.requisicoes} requisições, ${ok}/${resumo.asserções} asserções passaram em ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  if (arquivoSaida) {
    fs.mkdirSync(path.dirname(path.resolve(arquivoSaida)), { recursive: true });
    fs.writeFileSync(arquivoSaida, JSON.stringify({ ambiente, executado_em: new Date().toLocaleString("sv-SE").slice(0, 16), resumo, relatorio }, null, 2));
  }
  process.exit(resumo.falhas.length ? 1 : 0);
}
main();
