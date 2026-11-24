package br.unifor.cinema.sessoes.model;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;

/**
 * Um assento ocupado numa sessão.
 * Quem cria/remove reservas é o Serviço de Pedidos (Edson) ao realizar/cancelar um pedido.
 * A restrição UNIQUE garante que o mesmo assento não seja vendido duas vezes.
 */
@Entity
@Table(name = "reserva",
       uniqueConstraints = @UniqueConstraint(columnNames = {"sessao_id", "assento"}))
public class Reserva {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JsonIgnore
    @ManyToOne(optional = false, fetch = FetchType.LAZY)
    @JoinColumn(name = "sessao_id")
    private Sessao sessao;

    private String assento;

    /** Id do pedido no Serviço de Pedidos */
    private String pedidoId;

    public Reserva() { }

    public Reserva(Sessao sessao, String assento, String pedidoId) {
        this.sessao = sessao;
        this.assento = assento;
        this.pedidoId = pedidoId;
    }

    public Long getId() { return id; }
    public Sessao getSessao() { return sessao; }
    public String getAssento() { return assento; }
    public String getPedidoId() { return pedidoId; }
}
