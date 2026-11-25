# banco.py — banco de dados próprio do Serviço de Pagamentos (db_pagamentos).
# Usa o SQLite que já vem com o Python (módulo sqlite3).
# O banco é um arquivo: pagamentos-service/data/db_pagamentos.db

import os
import sqlite3

from flask import g

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.environ.get("DB_PATH", os.path.join(PASTA, "data", "db_pagamentos.db"))


def criar_tabelas():
    os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
    con = sqlite3.connect(ARQUIVO)
    con.executescript("""
        -- Dados comuns a qualquer forma de pagamento.
        -- pedido_id e usuario_id NÃO são chaves estrangeiras: pedidos ficam no db_pedidos
        -- e usuários no db_usuarios (outros microsserviços).
        CREATE TABLE IF NOT EXISTS pagamento (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id      INTEGER NOT NULL,
            usuario_id     INTEGER NOT NULL,
            valor          REAL    NOT NULL,
            metodo         TEXT    NOT NULL,   -- PIX ou CARTAO
            status         TEXT    NOT NULL,   -- PENDENTE, CONFIRMADO, RECUSADO, ESTORNADO
            motivo         TEXT,               -- por que foi recusado
            pontos_ganhos  INTEGER NOT NULL DEFAULT 0,
            data_criacao   TEXT    NOT NULL,
            data_pagamento TEXT,
            data_estorno   TEXT
        );

        -- Dados específicos do Pix (uma tabela por forma de pagamento, como as subclasses
        -- Pix e Cartao da classe abstrata Pagamento no diagrama de classes).
        CREATE TABLE IF NOT EXISTS pix (
            pagamento_id INTEGER PRIMARY KEY REFERENCES pagamento(id),
            chave_pix    TEXT NOT NULL,
            qr_code      TEXT NOT NULL,
            expira_em    TEXT NOT NULL
        );

        -- Do cartão guardamos só os 4 últimos dígitos: o número completo e o CVV NUNCA são salvos.
        CREATE TABLE IF NOT EXISTS cartao (
            pagamento_id       INTEGER PRIMARY KEY REFERENCES pagamento(id),
            nome_titular       TEXT    NOT NULL,
            final_cartao       TEXT    NOT NULL,
            bandeira           TEXT    NOT NULL,
            parcelas           INTEGER NOT NULL,
            valor_parcela      REAL    NOT NULL,
            codigo_autorizacao TEXT
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
