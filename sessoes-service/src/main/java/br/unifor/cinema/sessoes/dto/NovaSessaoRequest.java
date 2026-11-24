package br.unifor.cinema.sessoes.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** Dados enviados para criar uma sessão (POST /sessoes) */
public record NovaSessaoRequest(
        @NotNull(message = "Informe o filme") Long filmeId,
        @NotNull(message = "Informe a sala") Long salaId,
        @NotNull(message = "Informe a data e hora") LocalDateTime dataHora,
        @NotBlank(message = "Informe o idioma") String idioma,
        @NotBlank(message = "Informe o formato") String formato,
        @NotNull(message = "Informe o preço") @PositiveOrZero BigDecimal preco
) { }
