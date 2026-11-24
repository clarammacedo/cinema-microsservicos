// banco.js — banco de dados próprio do Serviço de Fidelidade (db_fidelidade).
// Usa o SQLite que já vem dentro do Node.js (módulo node:sqlite).
// O banco é um arquivo: fidelidade-service/data/db_fidelidade.db
// Este serviço NÃO acessa o banco de usuários: guarda só o usuario_id e uma cópia do nome.

const fs = require("node:fs");
const path = require("node:path");
const { DatabaseSync } = require("node:sqlite");

const arquivo = process.env.DB_PATH || path.join(__dirname, "data", "db_fidelidade.db");
fs.mkdirSync(path.dirname(arquivo), { recursive: true });
const db = new DatabaseSync(arquivo);

db.exec(`
  -- Uma conta por usuário que aderiu ao programa
  CREATE TABLE IF NOT EXISTS conta_fidelidade (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id   INTEGER NOT NULL UNIQUE,
    nome_usuario TEXT,
    pontos       INTEGER NOT NULL DEFAULT 0 CHECK (pontos >= 0),
    data_adesao  TEXT NOT NULL
  );

  -- Histórico: cada vez que pontos entram (ACUMULO) ou saem (USO)
  CREATE TABLE IF NOT EXISTS movimentacao (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    conta_id  INTEGER NOT NULL REFERENCES conta_fidelidade(id),
    tipo      TEXT NOT NULL CHECK (tipo IN ('ACUMULO', 'USO')),
    pontos    INTEGER NOT NULL,
    pedido_id TEXT,
    descricao TEXT,
    data      TEXT NOT NULL
  );

  -- Impede creditar (ou debitar) pontos duas vezes para o mesmo pedido
  CREATE UNIQUE INDEX IF NOT EXISTS ux_movimentacao_pedido
    ON movimentacao (tipo, pedido_id) WHERE pedido_id IS NOT NULL;
`);

module.exports = { db };
