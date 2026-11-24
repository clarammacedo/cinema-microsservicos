package br.unifor.cinema.sessoes.model;

import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * Sessão = um filme passando numa sala, num dia e horário.
 *
 * Importante (microsserviços): o filme NÃO é uma chave estrangeira para outra tabela,
 * porque os filmes ficam em outro banco (db_filmes). Guardamos só o filmeId e uma cópia
 * do título e da duração, obtidos do Serviço de Filmes no momento em que a sessão é criada.
 */
@Entity
@Table(name = "sessao")
public class Sessao {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** Id do filme no Serviço de Filmes */
    private Long filmeId;

    /** Cópia do título (evita chamar o Serviço de Filmes toda vez que listar sessões) */
    private String tituloFilme;

    /** Cópia da duração em minutos (usada para checar conflito de horário na sala) */
    private Integer duracaoFilme;

    private Integer classificacao;

    @ManyToOne(optional = false, fetch = FetchType.EAGER)
    @JoinColumn(name = "sala_id")
    private Sala sala;

    private LocalDateTime dataHora;

    /** Dublado / Legendado ... */
    private String idioma;

    /** 2D / 3D ... */
    private String formato;

    /** Preço da inteira (o Serviço de Pedidos usa esse valor) */
    private BigDecimal preco;

    public Sessao() { }

    /** Horário em que a sessão termina */
    public LocalDateTime getFim() {
        return dataHora.plusMinutes(duracaoFilme);
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getFilmeId() { return filmeId; }
    public void setFilmeId(Long filmeId) { this.filmeId = filmeId; }

    public String getTituloFilme() { return tituloFilme; }
    public void setTituloFilme(String tituloFilme) { this.tituloFilme = tituloFilme; }

    public Integer getDuracaoFilme() { return duracaoFilme; }
    public void setDuracaoFilme(Integer duracaoFilme) { this.duracaoFilme = duracaoFilme; }

    public Integer getClassificacao() { return classificacao; }
    public void setClassificacao(Integer classificacao) { this.classificacao = classificacao; }

    public Sala getSala() { return sala; }
    public void setSala(Sala sala) { this.sala = sala; }

    public LocalDateTime getDataHora() { return dataHora; }
    public void setDataHora(LocalDateTime dataHora) { this.dataHora = dataHora; }

    public String getIdioma() { return idioma; }
    public void setIdioma(String idioma) { this.idioma = idioma; }

    public String getFormato() { return formato; }
    public void setFormato(String formato) { this.formato = formato; }

    public BigDecimal getPreco() { return preco; }
    public void setPreco(BigDecimal preco) { this.preco = preco; }
}
