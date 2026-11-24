package br.unifor.cinema.sessoes.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** Dados enviados para cadastrar uma sala (POST /cinemas/{id}/salas) */
public record NovaSalaRequest(
        @NotNull(message = "O número da sala é obrigatório") @Min(1) Integer numero,
        @NotBlank(message = "O tipo da sala é obrigatório") String tipo,
        @NotNull @Min(value = 1, message = "Mínimo de 1 fileira") @Max(value = 26, message = "Máximo de 26 fileiras (A-Z)") Integer fileiras,
        @NotNull @Min(value = 1, message = "Mínimo de 1 assento por fileira") @Max(value = 40, message = "Máximo de 40 assentos por fileira") Integer assentosPorFileira
) { }
