// Serviço de Fidelidade — CONSUMIDOR do Serviço de Usuários
// Funcionalidades: aderir ao programa, ver número de pontos, acumular pontos, usar pontos.
// Ao aderir, este serviço chama GET /usuarios/{id} no Serviço de Usuários para confirmar
// que o usuário existe (ele não pode ler o banco de outro serviço).

const http = require("node:http");
const { db } = require("./banco");
const { ErroHttp, criarRoteador, idValido } = require("./util");

const PORTA = process.env.PORT || 8086;
const USUARIOS_URL = (process.env.USUARIOS_SERVICE_URL || "http://localhost:8085").replace(/\/$/, "");

// Regras do programa
const PONTOS_POR_REAL = 1;   // cada R$ 1,00 gasto vira 1 ponto
const VALOR_DO_PONTO = 0.10; // cada ponto vale R$ 0,10 de desconto (100 pontos = R$ 10,00)

const rota = criarRoteador();

// ---------------------------------------------------------------- comunicação com o Serviço de Usuários

async function buscarUsuario(usuarioId) {
  let resposta;
  try {
    // timeout alto porque no plano gratuito do Render o serviço pode estar "dormindo"
    resposta = await fetch(`${USUARIOS_URL}/usuarios/${usuarioId}`, { signal: AbortSignal.timeout(60000) });
  } catch {
    throw new ErroHttp(503, "Serviço de Usuários indisponível, tente de novo em instantes");
  }
  if (resposta.status === 404) throw new ErroHttp(404, `Usuário ${usuarioId} não existe no Serviço de Usuários`);
  if (!resposta.ok) throw new ErroHttp(502, `Serviço de Usuários respondeu com erro ${resposta.status}`);
  return resposta.json(); // { id, nome, dataCadastro }
}

// ---------------------------------------------------------------- funções de apoio

function buscarConta(usuarioId) {
  const conta = db.prepare("SELECT * FROM conta_fidelidade WHERE usuario_id = ?").get(usuarioId);
  if (!conta) throw new ErroHttp(404, `Usuário ${usuarioId} não participa do programa de fidelidade`);
  return conta;
}

function paraJson(c) {
  return {
    usuarioId: c.usuario_id,
    nomeUsuario: c.nome_usuario,
    pontos: c.pontos,
    valorEmReais: Number((c.pontos * VALOR_DO_PONTO).toFixed(2)),
    dataAdesao: c.data_adesao,
  };
}

// Atualiza o saldo e grava a movimentação juntos (transação: ou faz os dois, ou nenhum)
function movimentar(conta, tipo, pontos, pedidoId, descricao) {
  const sinal = tipo === "ACUMULO" ? 1 : -1;
  db.exec("BEGIN");
  try {
    db.prepare("UPDATE conta_fidelidade SET pontos = pontos + ? WHERE id = ?").run(sinal * pontos, conta.id);
    db.prepare(`INSERT INTO movimentacao (conta_id, tipo, pontos, pedido_id, descricao, data)
                VALUES (?, ?, ?, ?, ?, ?)`)
      .run(conta.id, tipo, pontos, pedidoId, descricao, new Date().toISOString());
    db.exec("COMMIT");
  } catch (erro) {
    db.exec("ROLLBACK");
    if (String(erro.message).includes("UNIQUE"))
      throw new ErroHttp(409, `O pedido ${pedidoId} já teve pontos ${tipo === "ACUMULO" ? "creditados" : "usados"}`);
    throw erro;
  }
  return db.prepare("SELECT * FROM conta_fidelidade WHERE id = ?").get(conta.id);
}

const reais = (n) => n.toFixed(2).replace(".", ",");
const pedidoOuNulo = (p) => (p === undefined || p === null || p === "" ? null : String(p));

// ---------------------------------------------------------------- rotas

// Aderir ao programa
rota.add("POST", "/fidelidade", async ({ corpo }) => {
  const usuarioId = idValido(corpo.usuarioId, "usuarioId");
  if (db.prepare("SELECT id FROM conta_fidelidade WHERE usuario_id = ?").get(usuarioId))
    throw new ErroHttp(409, "Esse usuário já participa do programa de fidelidade");

  const usuario = await buscarUsuario(usuarioId); // ← chamada ao outro microsserviço

  try {
    db.prepare("INSERT INTO conta_fidelidade (usuario_id, nome_usuario, pontos, data_adesao) VALUES (?, ?, 0, ?)")
      .run(usuario.id, usuario.nome, new Date().toISOString());
  } catch (erro) {
    if (String(erro.message).includes("UNIQUE")) throw new ErroHttp(409, "Esse usuário já participa do programa de fidelidade");
    throw erro;
  }
  return { status: 201, dados: paraJson(buscarConta(usuarioId)) };
});

// Ver número de pontos
rota.add("GET", "/fidelidade/:usuarioId", ({ params }) => {
  return { dados: paraJson(buscarConta(idValido(params.usuarioId, "usuarioId"))) };
});

// Extrato: de onde vieram e para onde foram os pontos
rota.add("GET", "/fidelidade/:usuarioId/extrato", ({ params }) => {
  const conta = buscarConta(idValido(params.usuarioId, "usuarioId"));
  const lista = db.prepare("SELECT * FROM movimentacao WHERE conta_id = ? ORDER BY id DESC").all(conta.id);
  return {
    dados: lista.map((m) => ({
      id: m.id, tipo: m.tipo, pontos: m.pontos, pedidoId: m.pedido_id, descricao: m.descricao, data: m.data,
    })),
  };
});

// Acumular pontos — chamada pelo Serviço de Pedidos/Pagamentos quando uma compra é paga
// Corpo: { "pedidoId": "123", "valor": 60.00 }
rota.add("POST", "/fidelidade/:usuarioId/acumular", ({ params, corpo }) => {
  const conta = buscarConta(idValido(params.usuarioId, "usuarioId"));
  const valor = Number(corpo.valor);
  if (!(valor > 0)) throw new ErroHttp(400, "valor da compra deve ser maior que zero");
  const pedidoId = pedidoOuNulo(corpo.pedidoId);
  if (!pedidoId) throw new ErroHttp(400, "pedidoId é obrigatório para acumular pontos");

  const pontos = Math.floor(valor * PONTOS_POR_REAL);
  if (pontos === 0) throw new ErroHttp(400, "compra abaixo de R$ 1,00 não gera pontos");

  const atualizada = movimentar(conta, "ACUMULO", pontos, pedidoId,
    `Compra de R$ ${reais(valor)} no pedido ${pedidoId}`);
  return { status: 201, dados: { pontosGanhos: pontos, ...paraJson(atualizada) } };
});

// Usar pontos — troca pontos por desconto em uma compra
// Corpo: { "pontos": 100, "pedidoId": "124" }  (pedidoId é opcional)
rota.add("POST", "/fidelidade/:usuarioId/usar", ({ params, corpo }) => {
  const conta = buscarConta(idValido(params.usuarioId, "usuarioId"));
  const pontos = Number(corpo.pontos);
  if (!Number.isInteger(pontos) || pontos <= 0) throw new ErroHttp(400, "pontos deve ser um número inteiro maior que zero");
  if (pontos > conta.pontos) throw new ErroHttp(422, `Saldo insuficiente: o usuário tem ${conta.pontos} pontos`);

  const desconto = Number((pontos * VALOR_DO_PONTO).toFixed(2));
  const pedidoId = pedidoOuNulo(corpo.pedidoId);
  const atualizada = movimentar(conta, "USO", pontos, pedidoId,
    `Desconto de R$ ${reais(desconto)}` + (pedidoId ? ` no pedido ${pedidoId}` : ""));
  return { dados: { pontosUsados: pontos, valorDesconto: desconto, ...paraJson(atualizada) } };
});

rota.add("GET", "/", () => ({ dados: { servico: "fidelidade", status: "ok", usuariosService: USUARIOS_URL } }));

http.createServer(rota.tratar).listen(PORTA, () => {
  console.log(`Serviço de Fidelidade rodando em http://localhost:${PORTA}`);
  console.log(`Consumindo o Serviço de Usuários em ${USUARIOS_URL}`);
});
