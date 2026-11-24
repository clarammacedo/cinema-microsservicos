package br.unifor.cinema.sessoes.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;

import java.util.List;

/** Enviado pelo Serviço de Pedidos para ocupar assentos (POST /sessoes/{id}/reservas) */
public record ReservaRequest(
        @NotBlank(message = "Informe o id do pedido") String pedidoId,
        @NotEmpty(message = "Informe pelo menos um assento") List<String> assentos
) { }
