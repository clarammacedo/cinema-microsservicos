// banco.js — banco de dados próprio do Serviço de Usuários (db_usuarios).
// Usa o SQLite que já vem dentro do Node.js (módulo node:sqlite).
// O banco é um arquivo: usuarios-service/data/db_usuarios.db

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { DatabaseSync } = require("node:sqlite");

const arquivo = process.env.DB_PATH || path.join(__dirname, "data", "db_usuarios.db");
fs.mkdirSync(path.dirname(arquivo), { recursive: true });
const db = new DatabaseSync(arquivo);

// Tabelas (criadas só se ainda não existirem)
db.exec(`
  CREATE TABLE IF NOT EXISTS usuario (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    senha_hash      TEXT NOT NULL,
    telefone        TEXT,
    data_nascimento TEXT,
    data_cadastro   TEXT NOT NULL
  );

  -- Cada login gera um token. O logout apaga o token.
  CREATE TABLE IF NOT EXISTS sessao_login (
    token      TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id),
    criado_em  TEXT NOT NULL,
    expira_em  TEXT NOT NULL
  );
`);

// A senha nunca é guardada como texto: guardamos "sal:hash" (algoritmo scrypt).
function gerarHash(senha) {
  const sal = crypto.randomBytes(16).toString("hex");
  const hash = crypto.scryptSync(senha, sal, 64).toString("hex");
  return `${sal}:${hash}`;
}

function senhaConfere(senha, guardado) {
  const [sal, hash] = guardado.split(":");
  const tentativa = crypto.scryptSync(senha, sal, 64);
  return crypto.timingSafeEqual(tentativa, Buffer.from(hash, "hex"));
}

// Dados de exemplo na primeira execução
const total = db.prepare("SELECT COUNT(*) AS n FROM usuario").get().n;
if (total === 0) {
  db.prepare(`INSERT INTO usuario (nome, email, senha_hash, telefone, data_nascimento, data_cadastro)
              VALUES (?, ?, ?, ?, ?, ?)`)
    .run("Cliente Teste", "cliente@cinema.com", gerarHash("123456"), "85999990000", "2000-05-10",
         new Date().toISOString());
  console.log("Usuário de exemplo criado: cliente@cinema.com / 123456");
}

module.exports = { db, gerarHash, senhaConfere };
