# Serviço de Pagamentos — CONSUMIDOR (do Serviço de Pedidos e do Serviço de Fidelidade)
# Funcionalidades: pagar com Pix, pagar com cartão, listar pagamentos, estornar pagamento.
#
#   POST /pagamentos/pix              -> gera o Pix (QR Code) de um pedido  [status PENDENTE]
#   POST /pagamentos/{id}/confirmar   -> confirma o Pix (simula o aviso do banco)
#   POST /pagamentos/cartao           -> paga com cartão (aprovado ou recusado na hora)
#   GET  /pagamentos                  -> listar pagamentos (?usuarioId= &pedidoId= &status=)
#   GET  /pagamentos/{id}             -> detalhes / status de um pagamento
#   POST /pagamentos/{id}/estornar    -> estornar (o Serviço de Pedidos cancela o pedido e libera os assentos)

import os

from flask import Flask, jsonify, request

import banco
from formas import Cartao, Pix
from util import (ErroHttp, agora_iso, chamar_servico, configurar, inteiro_positivo,
                  ler_json, mensagem_de)

PEDIDOS_URL = os.environ.get("PEDIDOS_SERVICE_URL", "http://localhost:8083").rstrip("/")
FIDELIDADE_URL = os.environ.get("FIDELIDADE_SERVICE_URL", "http://localhost:8086").rstrip("/")

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False
configurar(app)
banco.criar_tabelas()
app.teardown_appcontext(banco.fechar)


# ------------------------------------------------------------------ funções de apoio

def para_json(p):
    """Converte a linha do banco no JSON devolvido pela API (junta os dados do Pix ou do cartão)."""
    db = banco.conexao()
    dados = {
        "id": p["id"],
        "pedidoId": p["pedido_id"],
        "usuarioId": p["usuario_id"],
        "valor": p["valor"],
        "metodo": p["metodo"],
        "status": p["status"],
        "motivo": p["motivo"],
        "pontosGanhos": p["pontos_ganhos"],
        "dataCriacao": p["data_criacao"],
        "dataPagamento": p["data_pagamento"],
        "dataEstorno": p["data_estorno"],
    }
    if p["metodo"] == "PIX":
        x = db.execute("SELECT * FROM pix WHERE pagamento_id = ?", (p["id"],)).fetchone()
        dados["pix"] = {"chavePix": x["chave_pix"], "qrCode": x["qr_code"], "expiraEm": x["expira_em"]}
    else:
        c = db.execute("SELECT * FROM cartao WHERE pagamento_id = ?", (p["id"],)).fetchone()
        dados["cartao"] = {"nomeTitular": c["nome_titular"], "final": c["final_cartao"],
                           "bandeira": c["bandeira"], "parcelas": c["parcelas"],
                           "valorParcela": c["valor_parcela"], "codigoAutorizacao": c["codigo_autorizacao"]}
    return dados


def buscar_pagamento(pagamento_id):
    p = banco.conexao().execute("SELECT * FROM pagamento WHERE id = ?", (pagamento_id,)).fetchone()
    if p is None:
        raise ErroHttp(404, f"Pagamento {pagamento_id} não encontrado")
    return p


def buscar_pedido_aberto(pedido_id):
    """Pergunta ao Serviço de Pedidos o valor e o status do pedido. Só pedidos ABERTOS podem ser pagos."""
    status, pedido = chamar_servico("Pedidos", "GET", f"{PEDIDOS_URL}/pedidos/{pedido_id}")
    if status == 404:
        raise ErroHttp(404, f"Pedido {pedido_id} não existe no Serviço de Pedidos")
    if status != 200:
        raise ErroHttp(502, mensagem_de(pedido, f"Serviço de Pedidos respondeu com erro {status}"))
    if pedido["status"] != "ABERTO":
        raise ErroHttp(409, f"O pedido {pedido_id} está {pedido['status']} e não pode ser pago")
    confirmado = banco.conexao().execute(
        "SELECT id FROM pagamento WHERE pedido_id = ? AND status = 'CONFIRMADO'", (pedido_id,)).fetchone()
    if confirmado:
        raise ErroHttp(409, f"O pedido {pedido_id} já foi pago (pagamento {confirmado['id']})")
    return pedido


def criar_pagamento(pedido, metodo):
    cur = banco.conexao().execute("""
        INSERT INTO pagamento (pedido_id, usuario_id, valor, metodo, status, data_criacao)
        VALUES (?, ?, ?, ?, 'PENDENTE', ?)""",
        (pedido["id"], pedido["usuarioId"], pedido["valorTotal"], metodo, agora_iso()))
    return cur.lastrowid


def recusar(pagamento_id, motivo):
    db = banco.conexao()
    db.execute("UPDATE pagamento SET status = 'RECUSADO', motivo = ? WHERE id = ?", (motivo, pagamento_id))
    db.commit()


def acumular_pontos(usuario_id, pedido_id, valor):
    """Avisa o Serviço de Fidelidade. Se o cliente não participa (404) ou o serviço caiu, o pagamento segue."""
    try:
        status, dados = chamar_servico("Fidelidade", "POST", f"{FIDELIDADE_URL}/fidelidade/{usuario_id}/acumular",
                                       {"pedidoId": str(pedido_id), "valor": valor})
    except ErroHttp:
        return 0
    return int(dados.get("pontosGanhos", 0)) if status == 201 and dados else 0


def concluir(pagamento_id, forma):
    """
    Passos finais, iguais para Pix e cartão (aqui entra o polimorfismo: forma.autorizar()
    roda a regra do Pix ou do cartão sem este código precisar saber qual é):
      1) a forma de pagamento autoriza;  2) o Serviço de Pedidos marca o pedido como PAGO;
      3) o Serviço de Fidelidade credita os pontos.
    """
    p = buscar_pagamento(pagamento_id)
    aprovado, motivo = forma.autorizar()
    if not aprovado:
        recusar(pagamento_id, motivo)
        return

    status, dados = chamar_servico("Pedidos", "POST", f"{PEDIDOS_URL}/pedidos/{p['pedido_id']}/confirmar-pagamento",
                                   {"pagamentoId": str(pagamento_id)})
    if status != 200:
        # ex.: o pedido foi cancelado enquanto o Pix estava pendente
        recusar(pagamento_id, mensagem_de(dados, f"Serviço de Pedidos recusou a confirmação (erro {status})"))
        return

    db = banco.conexao()
    db.execute("UPDATE pagamento SET status = 'CONFIRMADO', data_pagamento = ? WHERE id = ?",
               (agora_iso(), pagamento_id))
    if isinstance(forma, Cartao):
        db.execute("UPDATE cartao SET codigo_autorizacao = ? WHERE pagamento_id = ?",
                   (forma.codigo_autorizacao, pagamento_id))
    db.commit()

    pontos = acumular_pontos(p["usuario_id"], p["pedido_id"], p["valor"])
    db.execute("UPDATE pagamento SET pontos_ganhos = ? WHERE id = ?", (pontos, pagamento_id))
    db.commit()


# ------------------------------------------------------------------ rotas

@app.post("/pagamentos/pix")
def pagar_com_pix():
    """Pagar com Pix, passo 1: gera o QR Code. Corpo: { "pedidoId": 1 }"""
    pedido_id = inteiro_positivo(ler_json().get("pedidoId"), "pedidoId")
    pedido = buscar_pedido_aberto(pedido_id)

    db = banco.conexao()
    for pendente in db.execute("""SELECT p.id, x.expira_em FROM pagamento p JOIN pix x ON x.pagamento_id = p.id
                                  WHERE p.pedido_id = ? AND p.status = 'PENDENTE'""", (pedido_id,)).fetchall():
        if pendente["expira_em"] >= agora_iso():
            raise ErroHttp(409, f"Já existe um Pix pendente para esse pedido (pagamento {pendente['id']})")
        recusar(pendente["id"], "O Pix expirou (validade de 30 minutos)")

    pix = Pix(pedido["valorTotal"], pedido_id)
    pix.gerar_qrcode()
    pagamento_id = criar_pagamento(pedido, "PIX")
    db.execute("INSERT INTO pix (pagamento_id, chave_pix, qr_code, expira_em) VALUES (?, ?, ?, ?)",
               (pagamento_id, pix.chave_pix, pix.qr_code, pix.expira_em))
    db.commit()
    return jsonify(para_json(buscar_pagamento(pagamento_id))), 201


@app.post("/pagamentos/<pagamento_id>/confirmar")
def confirmar_pix(pagamento_id):
    """Pagar com Pix, passo 2: o banco avisa que o cliente pagou (aqui é simulado por esta rota)."""
    p = buscar_pagamento(inteiro_positivo(pagamento_id, "id do pagamento"))
    if p["metodo"] != "PIX":
        raise ErroHttp(400, "Só pagamentos Pix precisam de confirmação")
    if p["status"] != "PENDENTE":
        raise ErroHttp(409, f"O pagamento {p['id']} está {p['status']}")

    x = banco.conexao().execute("SELECT * FROM pix WHERE pagamento_id = ?", (p["id"],)).fetchone()
    concluir(p["id"], Pix(p["valor"], p["pedido_id"], x["qr_code"], x["expira_em"]))

    final = buscar_pagamento(p["id"])
    if final["status"] == "RECUSADO":
        raise ErroHttp(409, final["motivo"])
    return jsonify(para_json(final))


@app.post("/pagamentos/cartao")
def pagar_com_cartao():
    """
    Pagar com cartão. Corpo:
    { "pedidoId": 1, "nomeTitular": "MARIA SOUZA", "numeroCartao": "4111 1111 1111 1111",
      "validade": "12/28", "cvv": "123", "parcelas": 1 }
    """
    corpo = ler_json()
    pedido_id = inteiro_positivo(corpo.get("pedidoId"), "pedidoId")
    parcelas = corpo.get("parcelas", 1)
    if isinstance(parcelas, str) and parcelas.isdigit():
        parcelas = int(parcelas)

    pedido = buscar_pedido_aberto(pedido_id)
    # Valida os dados digitados antes de gravar qualquer coisa (400 se algo estiver errado)
    cartao = Cartao(pedido["valorTotal"], corpo.get("nomeTitular"), corpo.get("numeroCartao"),
                    corpo.get("validade"), corpo.get("cvv"), parcelas)

    db = banco.conexao()
    pagamento_id = criar_pagamento(pedido, "CARTAO")
    db.execute("""INSERT INTO cartao (pagamento_id, nome_titular, final_cartao, bandeira, parcelas, valor_parcela)
                  VALUES (?, ?, ?, ?, ?, ?)""",
               (pagamento_id, cartao.nome_titular.upper(), cartao.final, cartao.bandeira,
                cartao.parcelas, cartao.valor_parcela))
    db.commit()

    concluir(pagamento_id, cartao)
    # 201: o pagamento foi registrado. O campo "status" diz se foi CONFIRMADO ou RECUSADO.
    return jsonify(para_json(buscar_pagamento(pagamento_id))), 201


@app.get("/pagamentos")
def listar_pagamentos():
    """Listar pagamentos, com filtros opcionais ?usuarioId= &pedidoId= &status="""
    sql, params = "SELECT * FROM pagamento WHERE 1 = 1", []
    for campo, coluna in (("usuarioId", "usuario_id"), ("pedidoId", "pedido_id")):
        if request.args.get(campo):
            sql += f" AND {coluna} = ?"
            params.append(inteiro_positivo(request.args[campo], campo))
    if request.args.get("status"):
        sql += " AND status = ?"
        params.append(request.args["status"].upper())
    linhas = banco.conexao().execute(sql + " ORDER BY id DESC", params).fetchall()
    return jsonify([para_json(p) for p in linhas])


@app.get("/pagamentos/<pagamento_id>")
def detalhes_pagamento(pagamento_id):
    """Detalhes de um pagamento (ex.: conferir se o Pix já foi confirmado)."""
    return jsonify(para_json(buscar_pagamento(inteiro_positivo(pagamento_id, "id do pagamento"))))


@app.post("/pagamentos/<pagamento_id>/estornar")
def estornar_pagamento(pagamento_id):
    """Estornar: devolve o dinheiro. O Serviço de Pedidos cancela o pedido e libera os assentos."""
    p = buscar_pagamento(inteiro_positivo(pagamento_id, "id do pagamento"))
    if p["status"] != "CONFIRMADO":
        raise ErroHttp(409, f"Só pagamentos CONFIRMADOS podem ser estornados (este está {p['status']})")

    # O Serviço de Pedidos confere as regras (sessão não começou, ingressos não usados)
    status, dados = chamar_servico("Pedidos", "POST", f"{PEDIDOS_URL}/pedidos/{p['pedido_id']}/cancelar",
                                   {"pagamentoId": str(p["id"])})
    if status != 200:
        raise ErroHttp(409 if status in (404, 409) else 502,
                       mensagem_de(dados, f"Serviço de Pedidos não cancelou o pedido (erro {status})"))

    db = banco.conexao()
    db.execute("UPDATE pagamento SET status = 'ESTORNADO', data_estorno = ? WHERE id = ?", (agora_iso(), p["id"]))
    db.commit()
    return jsonify(para_json(buscar_pagamento(p["id"])))


@app.get("/")
def status_servico():
    """Para conferir se o serviço está no ar (útil no Render)."""
    return jsonify({"servico": "pagamentos", "status": "ok",
                    "pedidosService": PEDIDOS_URL, "fidelidadeService": FIDELIDADE_URL})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8084)), debug=False)
