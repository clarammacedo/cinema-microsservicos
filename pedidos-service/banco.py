# banco.py — banco de dados próprio do Serviço de Pedidos (db_pedidos).
# Usa o SQLite que já vem com o Python (módulo sqlite3).
# O banco é um arquivo: pedidos-service/data/db_pedidos.db

import os
import sqlite3

from flask import g

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.environ.get("DB_PATH", os.path.join(PASTA, "data", "db_pedidos.db"))


def criar_tabelas():
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    con = sqlite3.connect(ARQUIVO)
    con.executescript("""
        -- Um pedido = uma compra de ingressos para UMA sessão.
        -- usuario_id e sessao_id NÃO são chaves estrangeiras: usuários e sessões
        -- ficam em outros bancos (db_usuarios e db_sessoes). Guardamos o id e uma cópia
        -- dos dados que precisamos mostrar (nome, filme, horário, sala).
        CREATE TABLE IF NOT EXISTS pedido (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id        INTEGER NOT NULL,
            nome_usuario      TEXT    NOT NULL,
            sessao_id         INTEGER NOT NULL,
            titulo_filme      TEXT    NOT NULL,
            data_hora_sessao  TEXT    NOT NULL,
            fim_sessao        TEXT,
            local_sessao      TEXT,
            subtotal          REAL    NOT NULL,
            pontos_usados     INTEGER NOT NULL DEFAULT 0,
            desconto          REAL    NOT NULL DEFAULT 0,
            valor_total       REAL    NOT NULL,
            status            TEXT    NOT NULL,   -- ABERTO, PAGO, CANCELADO, FINALIZADO
            pagamento_id      TEXT,               -- id no Serviço de Pagamentos
            data_pedido       TEXT    NOT NULL,
            data_pagamento    TEXT,
            data_cancelamento TEXT
        );

        -- Cada assento comprado vira um ingresso com um código único (apresentado na entrada).
        CREATE TABLE IF NOT EXISTS ingresso (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id    INTEGER NOT NULL REFERENCES pedido(id),
            codigo       TEXT    NOT NULL UNIQUE,
            assento      TEXT    NOT NULL,
            tipo         TEXT    NOT NULL,        -- INTEIRA ou MEIA
            valor        REAL    NOT NULL,
            utilizado_em TEXT                     -- preenchido quando o ingresso é validado
        );
    """)
    con.commit()
    con.close()


def conexao():
    """Uma conexão por requisição (o Flask guarda em g e fecha no final)."""
    if "db" not in g:
        g.db = sqlite3.connect(ARQUIVO)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def fechar(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
