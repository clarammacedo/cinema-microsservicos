package br.unifor.cinema.filmes.repository;

import br.unifor.cinema.filmes.model.Filme;
import org.springframework.data.jpa.repository.JpaRepository;

/**
 * Camada de acesso ao banco db_filmes.
 * O Spring gera sozinho o SQL de save(), findAll(), findById()...
 */
public interface FilmeRepository extends JpaRepository<Filme, Long> {
}
