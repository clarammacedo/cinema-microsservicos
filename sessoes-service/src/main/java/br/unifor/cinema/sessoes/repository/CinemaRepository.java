package br.unifor.cinema.sessoes.repository;

import br.unifor.cinema.sessoes.model.Cinema;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CinemaRepository extends JpaRepository<Cinema, Long> {
}
