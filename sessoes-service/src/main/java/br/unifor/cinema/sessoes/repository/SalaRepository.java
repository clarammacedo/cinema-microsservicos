package br.unifor.cinema.sessoes.repository;

import br.unifor.cinema.sessoes.model.Sala;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SalaRepository extends JpaRepository<Sala, Long> {
    List<Sala> findByCinemaIdOrderByNumero(Long cinemaId);
    boolean existsByCinemaIdAndNumero(Long cinemaId, Integer numero);
}
