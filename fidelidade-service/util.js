// util.js — funções de apoio para o servidor HTTP.
// Usa só módulos que já vêm com o Node.js (nenhuma biblioteca externa).

// Erro com código HTTP (400, 404, 409...). O roteador transforma em resposta JSON.
class ErroHttp extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// Envia uma resposta JSON com os cabeçalhos de CORS
// (sem CORS o navegador bloqueia as chamadas feitas pelo index.html).
function enviar(res, status, dados) {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  });
  res.end(dados === undefined ? "" : JSON.stringify(dados));
}

// Lê o corpo da requisição e converte de JSON para objeto.
function lerCorpo(req) {
  return new Promise((resolve, reject) => {
    let texto = "";
    req.on("data", (parte) => {
      texto += parte;
      if (texto.length > 1_000_000) reject(new ErroHttp(413, "Corpo da requisição muito grande"));
    });
    req.on("end", () => {
      if (!texto) return resolve({});
      try {
        resolve(JSON.parse(texto));
      } catch {
        reject(new ErroHttp(400, "JSON inválido no corpo da requisição"));
      }
    });
    req.on("error", reject);
  });
}

// Roteador simples: rota.add("GET", "/usuarios/:id", funcao)
function criarRoteador() {
  const rotas = [];

  function add(metodo, caminho, funcao) {
    const nomes = [];
    const padrao = caminho.replace(/:(\w+)/g, (_, nome) => {
      nomes.push(nome);
      return "([^/]+)";
    });
    rotas.push({ metodo, regex: new RegExp("^" + padrao + "/?$"), nomes, funcao });
  }

  async function tratar(req, res) {
    const url = new URL(req.url, "http://localhost");
    if (req.method === "OPTIONS") return enviar(res, 204); // pré-verificação do CORS

    try {
      for (const rota of rotas) {
        const achou = url.pathname.match(rota.regex);
        if (!achou || rota.metodo !== req.method) continue;
        const params = {};
        rota.nomes.forEach((nome, i) => (params[nome] = decodeURIComponent(achou[i + 1])));
        const corpo = ["POST", "PUT"].includes(req.method) ? await lerCorpo(req) : {};
        const resultado = await rota.funcao({ req, params, query: url.searchParams, corpo });
        // a função devolve { status, dados }
        return enviar(res, resultado.status ?? 200, resultado.dados);
      }
      enviar(res, 404, { message: `Rota ${req.method} ${url.pathname} não existe` });
    } catch (erro) {
      if (erro instanceof ErroHttp) return enviar(res, erro.status, { message: erro.message });
      console.error(erro);
      enviar(res, 500, { message: "Erro interno no servidor" });
    }
  }

  return { add, tratar };
}

// Converte um texto de id em número inteiro positivo, ou devolve 400.
function idValido(texto, nome = "id") {
  const n = Number(texto);
  if (!Number.isInteger(n) || n <= 0) throw new ErroHttp(400, `${nome} inválido: ${texto}`);
  return n;
}

module.exports = { ErroHttp, enviar, lerCorpo, criarRoteador, idValido };
