# Serviço de Pedidos — CONSUMIDOR (de Usuários, Sessões e Fidelidade) e PROVEDOR (para Pagamentos)
# Funcionalidades: realizar pedido, consultar detalhes, cancelar pedido, validar ingresso.
#
#   POST /pedidos                          -> realizar pedido
#   GET  /pedidos?usuarioId=               -> listar os pedidos de um usuário
#   GET  /pedidos/{id}                     -> consultar detalhes (o Serviço de Pagamentos usa)
#   POST /pedidos/{id}/cancelar            -> cancelar pedido (libera os assentos)
#   POST /pedidos/{id}/confirmar-pagamento -> marcar como PAGO (chamada pelo Serviço de Pagamentos)
#   POST /ingressos/{codigo}/validar       -> validar ingresso na entrada da sala

import os
import secrets
from datetime import datetime

from flask import Flask, jsonify, request

import banco
from util import (ErroHttp, agora, agora_iso, chamar_servico, configurar, inteiro_positivo,
                  ler_json, mensagem_de)

# Endereços dos outros microsserviços (na nuvem, defina as variáveis com os links do Render)
USUARIOS_URL = os.environ.get("USUARIOS_SERVICE_URL", "http://localhost:8085").rstrip("/")
SESSOES_URL = os.environ.get("SESSOES_SERVICE_URL", "http://localhost:8082").rstrip("/")
FIDELIDADE_URL = os.environ.get("FIDELIDADE_SERVICE_URL", "http://localhost:8086").rstrip("/")

# Regras de negócio
TIPOS_INGRESSO = {"INTEIRA": 1.0, "MEIA": 0.5}   # meia-entrada paga 50% do preço da sessão
MAX_INGRESSOS = 10                                # por pedido
VALOR_PONTO = 0.10                                # 1 ponto = R$ 0,10 (regra do Serviço de Fidelidade)
DESCONTO_MAXIMO = 0.5                             # pontos pagam no máximo 50% do pedido

app = Flask(__name__)
app.json.ensure_ascii = False
app.json.sort_keys = False
configurar(app)
banco.criar_tabelas()
app.teardown_appcontext(banco.fechar)


# ------------------------------------------------------------------ funções de apoio

def para_json(p, com_ingressos=True):
    """Converte a linha do banco no JSON devolvido pela API."""
    dados = {
        "id": p["id"],
        "usuarioId": p["usuario_id"],
        "nomeUsuario": p["nome_usuario"],
        "sessaoId": p["sessao_id"],
        "tituloFilme": p["titulo_filme"],
        "dataHoraSessao": p["data_hora_sessao"],
        "localSessao": p["local_sessao"],
        "subtotal": p["subtotal"],
        "pontosUsados": p["pontos_usados"],
        "desconto": p["desconto"],
        "valorTotal": p["valor_total"],
        "status": p["status"],
        "pagamentoId": p["pagamento_id"],
        "dataPedido": p["data_pedido"],
        "dataPagamento": p["data_pagamento"],
        "dataCancelamento": p["data_cancelamento"],
    }
    if com_ingressos:
        linhas = banco.conexao().execute(
            "SELECT * FROM ingresso WHERE pedido_id = ? ORDER BY id", (p["id"],)).fetchall()
        dados["ingressos"] = [ingresso_json(i) for i in linhas]
    return dados


def ingresso_json(i):
    return {"codigo": i["codigo"], "assento": i["assento"], "tipo": i["tipo"],
            "valor": i["valor"], "utilizadoEm": i["utilizado_em"]}


def buscar_pedido(pedido_id):
    p = banco.conexao().execute("SELECT * FROM pedido WHERE id = ?", (pedido_id,)).fetchone()
    if p is None:
        raise ErroHttp(404, f"Pedido {pedido_id} não encontrado")
    return p


def data_sessao(texto):
    """'2026-12-05T19:30:00' -> datetime (o Java pode mandar com ou sem segundos)."""
    return datetime.fromisoformat(str(texto)[:19])


def validar_ingressos(lista):
    """Confere a lista [{ "assento": "C4", "tipo": "MEIA" }, ...] enviada pelo cliente."""
    if not isinstance(lista, list) or not lista:
        raise ErroHttp(400, "Informe pelo menos um ingresso (lista 'ingressos')")
    if len(lista) > MAX_INGRESSOS:
        raise ErroHttp(400, f"No máximo {MAX_INGRESSOS} ingressos por pedido")
    resultado, vistos = [], set()
    for item in lista:
        if not isinstance(item, dict) or not str(item.get("assento") or "").strip():
            raise ErroHttp(400, "Cada ingresso precisa do campo 'assento' (ex.: \"C4\")")
        assento = str(item["assento"]).strip().upper()
        tipo = str(item.get("tipo") or "INTEIRA").strip().upper()
        if tipo not in TIPOS_INGRESSO:
            raise ErroHttp(400, f"Tipo de ingresso inválido: {tipo} (use INTEIRA ou MEIA)")
        if assento in vistos:
            raise ErroHttp(400, f"O assento {assento} foi escolhido duas vezes")
        vistos.add(assento)
        resultado.append({"assento": assento, "tipo": tipo})
    return resultado


# --- chamadas aos outros microsserviços ---

def buscar_usuario(usuario_id):
    status, dados = chamar_servico("Usuários", "GET", f"{USUARIOS_URL}/usuarios/{usuario_id}")
    if status == 404:
        raise ErroHttp(404, f"Usuário {usuario_id} não existe no Serviço de Usuários")
    if status != 200:
        raise ErroHttp(502, mensagem_de(dados, f"Serviço de Usuários respondeu com erro {status}"))
    return dados


def buscar_sessao(sessao_id):
    status, dados = chamar_servico("Sessões", "GET", f"{SESSOES_URL}/sessoes/{sessao_id}")
    if status == 404:
        raise ErroHttp(404, f"Sessão {sessao_id} não existe no Serviço de Sessões")
    if status != 200:
        raise ErroHttp(502, mensagem_de(dados, f"Serviço de Sessões respondeu com erro {status}"))
    return dados


def reservar_assentos(sessao_id, pedido_id, assentos):
    status, dados = chamar_servico("Sessões", "POST", f"{SESSOES_URL}/sessoes/{sessao_id}/reservas",
                                   {"pedidoId": str(pedido_id), "assentos": assentos})
    if status not in (200, 201):
        # 409 = assento ocupado, 400 = assento não existe na sala
        raise ErroHttp(status if status in (400, 409) else 502,
                       mensagem_de(dados, f"Serviço de Sessões recusou a reserva (erro {status})"))


def liberar_assentos(sessao_id, pedido_id):
    status, dados = chamar_servico("Sessões", "DELETE",
                                   f"{SESSOES_URL}/sessoes/{sessao_id}/reservas/{pedido_id}")
    # 404 = não havia assentos reservados (ex.: banco da nuvem reiniciado): nada a liberar
    if status not in (200, 204, 404):
        raise ErroHttp(502, mensagem_de(dados, f"Serviço de Sessões não liberou os assentos (erro {status})"))


def usar_pontos(usuario_id, pedido_id, pontos):
    status, dados = chamar_servico("Fidelidade", "POST", f"{FIDELIDADE_URL}/fidelidade/{usuario_id}/usar",
                                   {"pontos": pontos, "pedidoId": str(pedido_id)})
    if status != 200:
        # 404 = não participa do programa, 422 = saldo insuficiente
        raise ErroHttp(422 if status in (404, 422) else 502,
                       mensagem_de(dados, f"Serviço de Fidelidade recusou o uso dos pontos (erro {status})"))
    return float(dados["valorDesconto"])


# ------------------------------------------------------------------ rotas

@app.post("/pedidos")
def realizar_pedido():
    """
    Realizar pedido. Corpo:
    { "usuarioId": 1, "sessaoId": 1, "pontos": 0,
      "ingressos": [ { "assento": "C4", "tipo": "INTEIRA" }, { "assento": "C5", "tipo": "MEIA" } ] }
    """
    corpo = ler_json()
    usuario_id = inteiro_positivo(corpo.get("usuarioId"), "usuarioId")
    sessao_id = inteiro_positivo(corpo.get("sessaoId"), "sessaoId")
    ingressos = validar_ingressos(corpo.get("ingressos"))
    pontos = corpo.get("pontos") or 0
    if pontos:
        pontos = inteiro_positivo(pontos, "pontos")

    # 1) O usuário existe? (Serviço de Usuários)
    usuario = buscar_usuario(usuario_id)

    # 2) Dados da sessão: preço, filme e horário (Serviço de Sessões)
    sessao = buscar_sessao(sessao_id)
    inicio = data_sessao(sessao["dataHora"])
    if inicio <= agora():
        raise ErroHttp(400, "Essa sessão já começou, não é possível comprar ingressos")

    # 3) Cálculo do valor (inteira = preço da sessão, meia = 50%)
    preco = float(sessao["preco"])
    for ing in ingressos:
        ing["valor"] = round(preco * TIPOS_INGRESSO[ing["tipo"]], 2)
    subtotal = round(sum(i["valor"] for i in ingressos), 2)
    if pontos and pontos * VALOR_PONTO > subtotal * DESCONTO_MAXIMO + 1e-9:
        maximo = int(subtotal * DESCONTO_MAXIMO / VALOR_PONTO)
        raise ErroHttp(400, f"Os pontos podem pagar no máximo 50% do pedido: use até {maximo} pontos")

    sala = sessao.get("sala") or {}
    local = f"{(sala.get('cinema') or {}).get('nome', 'Cinema')} - Sala {sala.get('numero', '?')}"

    # 4) Grava o pedido (status ABERTO = aguardando pagamento) para ter um id
    db = banco.conexao()
    cur = db.execute("""
        INSERT INTO pedido (usuario_id, nome_usuario, sessao_id, titulo_filme, data_hora_sessao, fim_sessao,
                            local_sessao, subtotal, valor_total, status, data_pedido)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ABERTO', ?)""",
        (usuario_id, usuario["nome"], sessao_id, sessao.get("tituloFilme", "?"), inicio.isoformat(),
         sessao.get("fim"), local, subtotal, subtotal, agora_iso()))
    pedido_id = cur.lastrowid
    db.commit()

    try:
        # 5) Ocupa os assentos (Serviço de Sessões). 409 se algum já estiver ocupado.
        reservar_assentos(sessao_id, pedido_id, [i["assento"] for i in ingressos])
        try:
            # 6) Desconto com pontos (Serviço de Fidelidade) — feito por último porque não tem volta
            desconto = usar_pontos(usuario_id, pedido_id, pontos) if pontos else 0.0
        except ErroHttp:
            liberar_assentos(sessao_id, pedido_id)
            raise
    except ErroHttp:
        # Algo deu errado: o pedido não foi realizado
        db.execute("DELETE FROM pedido WHERE id = ?", (pedido_id,))
        db.commit()
        raise

    # 7) Gera os ingressos e grava o valor final
    for ing in ingressos:
        db.execute("INSERT INTO ingresso (pedido_id, codigo, assento, tipo, valor) VALUES (?, ?, ?, ?, ?)",
                   (pedido_id, "ING-" + secrets.token_hex(4).upper(), ing["assento"], ing["tipo"], ing["valor"]))
    db.execute("UPDATE pedido SET pontos_usados = ?, desconto = ?, valor_total = ? WHERE id = ?",
               (pontos, round(desconto, 2), round(subtotal - desconto, 2), pedido_id))
    db.commit()
    return jsonify(para_json(buscar_pedido(pedido_id))), 201


@app.get("/pedidos")
def listar_pedidos():
    """Listar os pedidos de um usuário (?usuarioId= obrigatório, ?status= opcional)."""
    usuario_id = inteiro_positivo(request.args.get("usuarioId"), "usuarioId")
    sql, params = "SELECT * FROM pedido WHERE usuario_id = ?", [usuario_id]
    status = request.args.get("status")
    if status:
        sql += " AND status = ?"
        params.append(status.upper())
    linhas = banco.conexao().execute(sql + " ORDER BY id DESC", params).fetchall()
    return jsonify([para_json(p) for p in linhas])


@app.get("/pedidos/<pedido_id>")
def detalhes_pedido(pedido_id):
    """Consultar detalhes. O Serviço de Pagamentos usa para saber o valor e o status."""
    return jsonify(para_json(buscar_pedido(inteiro_positivo(pedido_id, "id do pedido"))))


@app.post("/pedidos/<pedido_id>/cancelar")
def cancelar_pedido(pedido_id):
    """
    Cancelar pedido e liberar os assentos.
    - ABERTO (não pago): o próprio cliente cancela.
    - PAGO: só pelo estorno do Serviço de Pagamentos, que envia { "pagamentoId": "..." }.
    """
    p = buscar_pedido(inteiro_positivo(pedido_id, "id do pedido"))
    corpo = ler_json()

    if p["status"] == "CANCELADO":
        raise ErroHttp(409, f"O pedido {p['id']} já está cancelado")
    if p["status"] == "FINALIZADO":
        raise ErroHttp(409, "Os ingressos desse pedido já foram utilizados, não é possível cancelar")
    if p["status"] == "PAGO":
        if str(corpo.get("pagamentoId") or "") != str(p["pagamento_id"]):
            raise ErroHttp(409, "Pedido já pago: para cancelar, estorne o pagamento "
                                f"{p['pagamento_id']} no Serviço de Pagamentos")
        if data_sessao(p["data_hora_sessao"]) <= agora():
            raise ErroHttp(409, "A sessão já começou, não é possível cancelar nem estornar")
        usados = banco.conexao().execute(
            "SELECT COUNT(*) FROM ingresso WHERE pedido_id = ? AND utilizado_em IS NOT NULL", (p["id"],)).fetchone()[0]
        if usados:
            raise ErroHttp(409, "Algum ingresso desse pedido já foi utilizado, não é possível cancelar nem estornar")

    # Devolve os assentos para venda (Serviço de Sessões)
    liberar_assentos(p["sessao_id"], p["id"])

    db = banco.conexao()
    db.execute("UPDATE pedido SET status = 'CANCELADO', data_cancelamento = ? WHERE id = ?", (agora_iso(), p["id"]))
    db.commit()
    return jsonify(para_json(buscar_pedido(p["id"])))


@app.post("/pedidos/<pedido_id>/confirmar-pagamento")
def confirmar_pagamento(pedido_id):
    """Chamada pelo Serviço de Pagamentos quando o pagamento é aprovado. Corpo: { "pagamentoId": "7" }"""
    p = buscar_pedido(inteiro_positivo(pedido_id, "id do pedido"))
    pagamento_id = str(ler_json().get("pagamentoId") or "").strip()
    if not pagamento_id:
        raise ErroHttp(400, "pagamentoId é obrigatório")

    if p["status"] == "PAGO" and p["pagamento_id"] == pagamento_id:
        return jsonify(para_json(p))  # repetição da mesma confirmação: nada muda
    if p["status"] != "ABERTO":
        raise ErroHttp(409, f"O pedido {p['id']} está {p['status']} e não pode receber pagamento")

    db = banco.conexao()
    db.execute("UPDATE pedido SET status = 'PAGO', pagamento_id = ?, data_pagamento = ? WHERE id = ?",
               (pagamento_id, agora_iso(), p["id"]))
    db.commit()
    return jsonify(para_json(buscar_pedido(p["id"])))


@app.post("/ingressos/<codigo>/validar")
def validar_ingresso(codigo):
    """Validar ingresso na entrada da sala: só passa se o pedido estiver pago e o ingresso não foi usado."""
    db = banco.conexao()
    i = db.execute("SELECT * FROM ingresso WHERE codigo = ?", (codigo.strip().upper(),)).fetchone()
    if i is None:
        raise ErroHttp(404, f"Ingresso {codigo} não existe")
    p = buscar_pedido(i["pedido_id"])

    if p["status"] == "ABERTO":
        raise ErroHttp(409, "Ingresso inválido: o pedido ainda não foi pago")
    if p["status"] == "CANCELADO":
        raise ErroHttp(409, "Ingresso inválido: o pedido foi cancelado")
    if i["utilizado_em"]:
        raise ErroHttp(409, f"Ingresso já utilizado em {i['utilizado_em']}")
    if p["fim_sessao"] and data_sessao(p["fim_sessao"]) < agora():
        raise ErroHttp(409, "Ingresso vencido: a sessão já terminou")

    db.execute("UPDATE ingresso SET utilizado_em = ? WHERE id = ?", (agora_iso(), i["id"]))
    # Quando todos os ingressos do pedido forem usados, o pedido fica FINALIZADO
    restantes = db.execute("SELECT COUNT(*) FROM ingresso WHERE pedido_id = ? AND utilizado_em IS NULL",
                           (p["id"],)).fetchone()[0]
    if restantes == 0:
        db.execute("UPDATE pedido SET status = 'FINALIZADO' WHERE id = ?", (p["id"],))
    db.commit()

    i = db.execute("SELECT * FROM ingresso WHERE id = ?", (i["id"],)).fetchone()
    return jsonify({
        "mensagem": f"Entrada liberada: assento {i['assento']}",
        "ingresso": ingresso_json(i),
        "pedidoId": p["id"],
        "tituloFilme": p["titulo_filme"],
        "dataHoraSessao": p["data_hora_sessao"],
        "localSessao": p["local_sessao"],
    })


@app.get("/")
def status_servico():
    """Para conferir se o serviço está no ar (útil no Render)."""
    return jsonify({"servico": "pedidos", "status": "ok",
                    "usuariosService": USUARIOS_URL, "sessoesService": SESSOES_URL,
                    "fidelidadeService": FIDELIDADE_URL})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8083)), debug=False)
