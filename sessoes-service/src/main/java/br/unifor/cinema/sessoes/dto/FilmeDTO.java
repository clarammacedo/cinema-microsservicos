package br.unifor.cinema.sessoes.dto;

/**
 * Formato do JSON que o Serviço de Filmes devolve em GET /filmes/{id}.
 * Só os campos que este serviço precisa (os outros são ignorados).
 */
public record FilmeDTO(Long id, String titulo, Integer duracao, Integer classificacao, Boolean emCartaz) { }
