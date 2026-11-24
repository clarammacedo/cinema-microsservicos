package br.unifor.cinema.sessoes.repository;

import br.unifor.cinema.sessoes.model.Reserva;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface ReservaRepository extends JpaRepository<Reserva, Long> {
    List<Reserva> findBySessaoId(Long sessaoId);
    List<Reserva> findBySessaoIdAndPedidoId(Long sessaoId, String pedidoId);
}
