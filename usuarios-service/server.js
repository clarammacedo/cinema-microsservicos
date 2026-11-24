// Serviço de Usuários — PROVEDOR
// Funcionalidades: cadastrar usuário, realizar login/logout, atualizar cadastro, consultar dados.
// Outros serviços (Fidelidade, Pedidos) chamam GET /usuarios/{id} para saber se o usuário existe.

const http = require("node:http");
const crypto = require("node:crypto");
const { db, gerarHash, senhaConfere } = require("./banco");
const { ErroHttp, criarRoteador, idValido } = require("./util");

const PORTA = process.env.PORT || 8085;
const HORAS_LOGIN = 8; // validade do token
const rota = criarRoteador();

// ---------------------------------------------------------------- funções de apoio

// Converte a linha do banco no JSON devolvido (NUNCA devolve a senha)
function paraJson(u) {
  return {
    id: u.id,
    nome: u.nome,
    email: u.email,
    telefone: u.telefone,
    dataNascimento: u.data_nascimento,
    dataCadastro: u.data_cadastro,
  };
}

// Valida os campos. "parcial" = atualização (só confere os campos enviados).
function validar(d, parcial = false) {
  const erros = [];
  const veio = (campo) => !parcial || d[campo] !== undefined;

  if (veio("nome") && (typeof d.nome !== "string" || d.nome.trim().length < 3))
    erros.push("nome deve ter pelo menos 3 letras");
  if (veio("email") && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email ?? ""))
    erros.push("email inválido");
  if (!parcial && (typeof d.senha !== "string" || d.senha.length < 6))
    erros.push("senha deve ter pelo menos 6 caracteres");
  if (d.telefone && !/^\d{10,11}$/.test(String(d.telefone).replace(/\D/g, "")))
    erros.push("telefone deve ter DDD + número (10 ou 11 dígitos)");
  if (d.dataNascimento) {
    const data = new Date(d.dataNascimento + "T00:00:00");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d.dataNascimento) || isNaN(data) || data > new Date())
      erros.push("dataNascimento deve estar no formato AAAA-MM-DD e não pode ser no futuro");
  }
  if (erros.length) throw new ErroHttp(400, erros.join("; "));
}

const soDigitos = (t) => (t ? String(t).replace(/\D/g, "") : null);

// Lê o cabeçalho "Authorization: Bearer <token>" e devolve o usuário logado
function usuarioLogado(req) {
  const token = (req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!token) throw new ErroHttp(401, "Faça login primeiro (token não enviado)");
  const s = db.prepare("SELECT * FROM sessao_login WHERE token = ?").get(token);
  if (!s || new Date(s.expira_em) < new Date()) throw new ErroHttp(401, "Sessão inválida ou expirada, faça login de novo");
  return { usuario: db.prepare("SELECT * FROM usuario WHERE id = ?").get(s.usuario_id), token };
}

function emailEmUso(email, ignorarId = 0) {
  return db.prepare("SELECT id FROM usuario WHERE email = ? AND id <> ?").get(email, ignorarId);
}

// ---------------------------------------------------------------- rotas

// Cadastrar usuário
rota.add("POST", "/usuarios", ({ corpo }) => {
  validar(corpo);
  const email = corpo.email.trim().toLowerCase();
  if (emailEmUso(email)) throw new ErroHttp(409, "Já existe um usuário com esse email");

  const r = db.prepare(`INSERT INTO usuario (nome, email, senha_hash, telefone, data_nascimento, data_cadastro)
                        VALUES (?, ?, ?, ?, ?, ?)`)
    .run(corpo.nome.trim(), email, gerarHash(corpo.senha), soDigitos(corpo.telefone),
         corpo.dataNascimento || null, new Date().toISOString());
  const novo = db.prepare("SELECT * FROM usuario WHERE id = ?").get(r.lastInsertRowid);
  return { status: 201, dados: paraJson(novo) };
});

// Realizar login: confere email e senha e devolve um token
rota.add("POST", "/login", ({ corpo }) => {
  const email = String(corpo.email ?? "").trim().toLowerCase();
  const u = db.prepare("SELECT * FROM usuario WHERE email = ?").get(email);
  if (!u || !senhaConfere(String(corpo.senha ?? ""), u.senha_hash))
    throw new ErroHttp(401, "Email ou senha incorretos");

  const token = crypto.randomBytes(24).toString("hex");
  const agora = new Date();
  const expira = new Date(agora.getTime() + HORAS_LOGIN * 3600 * 1000);
  db.prepare("INSERT INTO sessao_login (token, usuario_id, criado_em, expira_em) VALUES (?, ?, ?, ?)")
    .run(token, u.id, agora.toISOString(), expira.toISOString());
  return { dados: { token, expiraEm: expira.toISOString(), usuario: paraJson(u) } };
});

// Realizar logout: apaga o token, que deixa de funcionar
rota.add("POST", "/logout", ({ req }) => {
  const { token } = usuarioLogado(req);
  db.prepare("DELETE FROM sessao_login WHERE token = ?").run(token);
  return { status: 204 };
});

// Consultar os próprios dados (precisa estar logado)
rota.add("GET", "/usuarios/me", ({ req }) => {
  return { dados: paraJson(usuarioLogado(req).usuario) };
});

// Atualizar cadastro (precisa estar logado; só altera o próprio cadastro)
rota.add("PUT", "/usuarios/me", ({ req, corpo }) => {
  const { usuario } = usuarioLogado(req);
  validar(corpo, true);

  const email = corpo.email !== undefined ? corpo.email.trim().toLowerCase() : usuario.email;
  if (emailEmUso(email, usuario.id)) throw new ErroHttp(409, "Já existe um usuário com esse email");

  let senhaHash = usuario.senha_hash;
  if (corpo.novaSenha) {
    if (!senhaConfere(String(corpo.senhaAtual ?? ""), usuario.senha_hash))
      throw new ErroHttp(400, "Para trocar a senha, informe a senha atual correta");
    if (String(corpo.novaSenha).length < 6) throw new ErroHttp(400, "nova senha deve ter pelo menos 6 caracteres");
    senhaHash = gerarHash(corpo.novaSenha);
  }

  db.prepare(`UPDATE usuario SET nome = ?, email = ?, telefone = ?, data_nascimento = ?, senha_hash = ?
              WHERE id = ?`)
    .run(corpo.nome !== undefined ? corpo.nome.trim() : usuario.nome,
         email,
         corpo.telefone !== undefined ? soDigitos(corpo.telefone) : usuario.telefone,
         corpo.dataNascimento !== undefined ? corpo.dataNascimento || null : usuario.data_nascimento,
         senhaHash,
         usuario.id);
  return { dados: paraJson(db.prepare("SELECT * FROM usuario WHERE id = ?").get(usuario.id)) };
});

// Consultar dados públicos de um usuário pelo id.
// É a rota que os OUTROS SERVIÇOS chamam (Fidelidade e Pedidos) para validar o usuário.
// Devolve só id, nome e data de cadastro (email e telefone ficam protegidos em /usuarios/me).
rota.add("GET", "/usuarios/:id", ({ params }) => {
  const u = db.prepare("SELECT * FROM usuario WHERE id = ?").get(idValido(params.id));
  if (!u) throw new ErroHttp(404, `Usuário ${params.id} não encontrado`);
  return { dados: { id: u.id, nome: u.nome, dataCadastro: u.data_cadastro } };
});

// Para conferir se o serviço está no ar (útil no Render)
rota.add("GET", "/", () => ({ dados: { servico: "usuarios", status: "ok" } }));

http.createServer(rota.tratar).listen(PORTA, () => {
  console.log(`Serviço de Usuários rodando em http://localhost:${PORTA}`);
});
