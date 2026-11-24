package br.unifor.cinema.sessoes.model;

import jakarta.persistence.*;

import java.util.ArrayList;
import java.util.List;

/**
 * Sala de um cinema. Os assentos são uma grade: fileiras A, B, C... x números 1, 2, 3...
 * Ex.: 5 fileiras x 8 assentos = 40 lugares (A1 ... E8).
 */
@Entity
@Table(name = "sala")
public class Sala {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Integer numero;

    /** 2D, 3D, IMAX, VIP... */
    private String tipo;

    private Integer fileiras;

    private Integer assentosPorFileira;

    @ManyToOne(optional = false, fetch = FetchType.EAGER)
    @JoinColumn(name = "cinema_id")
    private Cinema cinema;

    public Sala() { }

    /** Capacidade total da sala */
    public int getCapacidade() {
        return fileiras * assentosPorFileira;
    }

    /** Gera os códigos de todos os assentos: A1, A2, ..., B1, B2... */
    public List<String> gerarAssentos() {
        List<String> assentos = new ArrayList<>();
        for (int f = 0; f < fileiras; f++) {
            char letra = (char) ('A' + f);
            for (int n = 1; n <= assentosPorFileira; n++) {
                assentos.add(letra + String.valueOf(n));
            }
        }
        return assentos;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Integer getNumero() { return numero; }
    public void setNumero(Integer numero) { this.numero = numero; }

    public String getTipo() { return tipo; }
    public void setTipo(String tipo) { this.tipo = tipo; }

    public Integer getFileiras() { return fileiras; }
    public void setFileiras(Integer fileiras) { this.fileiras = fileiras; }

    public Integer getAssentosPorFileira() { return assentosPorFileira; }
    public void setAssentosPorFileira(Integer assentosPorFileira) { this.assentosPorFileira = assentosPorFileira; }

    public Cinema getCinema() { return cinema; }
    public void setCinema(Cinema cinema) { this.cinema = cinema; }
}
