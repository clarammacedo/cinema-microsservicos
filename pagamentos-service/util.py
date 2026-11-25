# util.py — funções de apoio do serviço (erros, CORS, JSON e chamadas a outros microsserviços).
# Usa só o Flask e a biblioteca padrão do Python (urllib para as chamadas HTTP).

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import jsonify, request

# Fortaleza não tem horário de verão: UTC-3 o ano todo.
# As sessões do Serviço de Sessões usam o horário local (ex.: "2026-12-05T19:30:00").
FUSO_FORTALEZA = timezone(timedelta(hours=-3))

# O plano gratuito do Render "dorme"; a primeira chamada pode levar uns 50 segundos.
TEMPO_LIMITE = 60


class ErroHttp(Exception):
    """Erro com código HTTP (400, 404, 409...). Vira uma resposta JSON { "message": ... }."""

    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


def agora():
    """Data e hora atuais em Fortaleza, sem fuso (para comparar com as datas das sessões)."""
    return datetime.now(FUSO_FORTALEZA).replace(tzinfo=None, microsecond=0)


def agora_iso():
    return agora().isoformat()


def configurar(app):
    """Liga o CORS e o tratamento de erros no app Flask."""

    # Sem CORS o navegador bloqueia as chamadas feitas pelo index.html
    @app.after_request
    def cors(resposta):
        resposta.headers["Access-Control-Allow-Origin"] = "*"
        resposta.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        resposta.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return resposta

    @app.errorhandler(ErroHttp)
    def erro_http(e):
        return jsonify({"message": e.mensagem}), e.status

    @app.errorhandler(404)
    def rota_inexistente(e):
        return jsonify({"message": f"Rota {request.method} {request.path} não existe"}), 404

    @app.errorhandler(405)
    def metodo_invalido(e):
        return jsonify({"message": f"Método {request.method} não é aceito em {request.path}"}), 405

    @app.errorhandler(500)
    def erro_interno(e):
        return jsonify({"message": "Erro interno no servidor"}), 500


def ler_json():
    """Lê o corpo da requisição como objeto JSON (ou {} se vier vazio)."""
    if not request.data:
        return {}
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ErroHttp(400, "JSON inválido no corpo da requisição")
    return dados


def inteiro_positivo(valor, nome):
    """Converte para int > 0 ou devolve 400."""
    if isinstance(valor, bool):
        raise ErroHttp(400, f"{nome} deve ser um número inteiro maior que zero")
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ErroHttp(400, f"{nome} deve ser um número inteiro maior que zero")
    if n <= 0 or (isinstance(valor, float) and not valor.is_integer()):
        raise ErroHttp(400, f"{nome} deve ser um número inteiro maior que zero")
    return n


def chamar_servico(nome_servico, metodo, url, corpo=None):
    """
    Faz uma requisição HTTP para OUTRO microsserviço e devolve (status, dados_json).
    Se o serviço estiver fora do ar, devolve 503 para quem chamou.
    """
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as resposta:
            status, texto = resposta.status, resposta.read().decode("utf-8")
    except urllib.error.HTTPError as erro:  # 4xx e 5xx também têm corpo JSON
        status, texto = erro.code, erro.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError) as erro:
        print(f"[{nome_servico}] falha ao chamar {metodo} {url}: {erro}")
        raise ErroHttp(503, f"Serviço de {nome_servico} indisponível, tente de novo em instantes")

    try:
        json_resposta = json.loads(texto) if texto else None
    except ValueError:
        json_resposta = None
    return status, json_resposta


def mensagem_de(dados, padrao):
    """Pega o campo "message" da resposta de erro de outro serviço."""
    if isinstance(dados, dict) and dados.get("message"):
        return dados["message"]
    return padrao
