package br.unifor.cinema.sessoes.repository;

import br.unifor.cinema.sessoes.model.Sessao;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface SessaoRepository extends JpaRepository<Sessao, Long> {
    List<Sessao> findBySalaId(Long salaId);
}
