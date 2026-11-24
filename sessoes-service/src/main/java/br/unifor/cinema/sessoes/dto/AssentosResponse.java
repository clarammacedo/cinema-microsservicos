package br.unifor.cinema.sessoes.dto;

import java.util.List;

/** Resposta de GET /sessoes/{id}/assentos */
public record AssentosResponse(
        Long sessaoId,
        int fileiras,
        int assentosPorFileira,
        int capacidade,
        int totalLivres,
        List<String> livres,
        List<String> ocupados
) { }
