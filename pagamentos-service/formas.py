# formas.py — formas de pagamento (Pix e Cartão).
# Vem do diagrama de classes do projeto antigo: Pagamento é uma classe abstrata e
# Pix e Cartao implementam autorizar() cada um do seu jeito (polimorfismo, GRASP).
# Aqui a "operadora" e o "banco" são simulados: nenhum dinheiro de verdade é movimentado.

import re
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from util import ErroHttp, agora

CHAVE_PIX_CINEMA = "pagamentos@redecinemas.com.br"
MINUTOS_PIX = 30          # o QR Code do Pix vale 30 minutos
MAX_PARCELAS = 3          # cartão em até 3x sem juros


class Pagamento(ABC):
    def __init__(self, valor):
        self.valor = round(float(valor), 2)

    @abstractmethod
    def autorizar(self):
        """Devolve (aprovado: bool, motivo_da_recusa: str | None)."""


class Pix(Pagamento):
    def __init__(self, valor, pedido_id, qr_code=None, expira_em=None):
        super().__init__(valor)
        self.pedido_id = pedido_id
        self.chave_pix = CHAVE_PIX_CINEMA
        self.qr_code = qr_code
        self.expira_em = expira_em

    def gerar_qrcode(self):
        """Gera o código "copia e cola" do Pix (simulado) e a validade."""
        self.qr_code = (f"PIX|{self.chave_pix}|PEDIDO-{self.pedido_id}|"
                        f"VALOR-{self.valor:.2f}|{secrets.token_hex(6).upper()}")
        self.expira_em = (agora() + timedelta(minutes=MINUTOS_PIX)).isoformat()
        return self.qr_code

    def autorizar(self):
        """O banco confirmou o Pix: vale se o QR Code existe e ainda não expirou."""
        if not self.qr_code:
            return False, "QR Code do Pix não foi gerado"
        if datetime.fromisoformat(self.expira_em) < agora():
            return False, "O Pix expirou (validade de 30 minutos)"
        return True, None


class Cartao(Pagamento):
    def __init__(self, valor, nome_titular, numero, validade, cvv, parcelas):
        super().__init__(valor)
        self.nome_titular = str(nome_titular or "").strip()
        self.numero = re.sub(r"[\s.-]", "", str(numero or ""))
        self.validade = str(validade or "").strip()
        self.cvv = str(cvv or "").strip()
        self.parcelas = parcelas
        self.bandeira = None
        self.codigo_autorizacao = None
        self.validar()

    @property
    def final(self):
        return self.numero[-4:]

    @property
    def valor_parcela(self):
        return round(self.valor / self.parcelas, 2)

    def validar(self):
        """Confere os dados digitados. Se algo estiver errado → 400 (nada é gravado)."""
        erros = []
        if len(self.nome_titular) < 3:
            erros.append("nome do titular é obrigatório")
        if not re.fullmatch(r"\d{13,19}", self.numero) or not luhn(self.numero):
            erros.append("número do cartão inválido")
        else:
            self.bandeira = descobrir_bandeira(self.numero)
            if not self.validar_bandeira():
                erros.append("bandeira não aceita (aceitamos Visa, Mastercard, Elo, Amex e Hipercard)")
        tamanho_cvv = 4 if self.bandeira == "Amex" else 3
        if not re.fullmatch(rf"\d{{{tamanho_cvv}}}", self.cvv):
            erros.append(f"CVV deve ter {tamanho_cvv} dígitos")
        if not validade_ok(self.validade):
            erros.append("validade deve estar no formato MM/AA e o cartão não pode estar vencido")
        if not isinstance(self.parcelas, int) or isinstance(self.parcelas, bool) or not 1 <= self.parcelas <= MAX_PARCELAS:
            erros.append(f"parcelas deve ser de 1 a {MAX_PARCELAS}")
        if erros:
            raise ErroHttp(400, "; ".join(erros))

    def validar_bandeira(self):
        return self.bandeira is not None

    def autorizar(self):
        """
        Operadora simulada: aprova tudo, menos cartões terminados em 0002
        (como os "cartões de teste" das operadoras reais, para mostrar uma recusa no vídeo).
        """
        if self.numero.endswith("0002"):
            return False, "Pagamento recusado pela operadora do cartão"
        self.codigo_autorizacao = "AUTH-" + secrets.token_hex(4).upper()
        return True, None


# ------------------------------------------------------------------ funções de apoio

def luhn(numero):
    """Algoritmo de Luhn: o dígito verificador que todo número de cartão tem."""
    soma = 0
    for i, d in enumerate(reversed(numero)):
        d = int(d)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
    return soma % 10 == 0


def descobrir_bandeira(numero):
    """A bandeira é descoberta pelos primeiros dígitos do cartão."""
    if re.match(r"^(4011|4312|4389|4514|4576|5041|5066|5067|509|6277|6362|6363|650|6516|6550)", numero):
        return "Elo"
    if re.match(r"^(606282|3841)", numero):
        return "Hipercard"
    if re.match(r"^3[47]", numero) and len(numero) == 15:
        return "Amex"
    if re.match(r"^4", numero):
        return "Visa"
    if re.match(r"^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))", numero):
        return "Mastercard"
    return None


def validade_ok(texto):
    """'MM/AA' e o cartão vale até o fim desse mês."""
    m = re.fullmatch(r"(\d{2})/(\d{2})", texto)
    if not m or not 1 <= int(m.group(1)) <= 12:
        return False
    mes, ano = int(m.group(1)), 2000 + int(m.group(2))
    hoje = agora()
    return (ano, mes) >= (hoje.year, hoje.month)
