package br.unifor.cinema.filmes.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

/**
 * Entidade Filme (baseada na classe Filme do diagrama de classes).
 * Cada objeto vira uma linha da tabela "filme" no banco db_filmes.
 *
 * Diferença em relação ao código antigo: o Filme NÃO guarda mais a lista de sessões.
 * Agora as sessões ficam em outro microsserviço (Sessões), que só guarda o id do filme.
 */
@Entity
@Table(name = "filme")
public class Filme {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank(message = "O título é obrigatório")
    private String titulo;

    @Column(length = 2000)
    private String sinopse;

    /** Duração em minutos */
    @NotNull(message = "A duração é obrigatória")
    @Positive(message = "A duração deve ser maior que zero")
    private Integer duracao;

    /** Classificação indicativa: 0 (Livre), 10, 12, 14, 16 ou 18 */
    @NotNull(message = "A classificação é obrigatória")
    @Min(value = 0, message = "Classificação inválida")
    private Integer classificacao;

    @NotBlank(message = "O gênero é obrigatório")
    private String genero;

    /** Link de uma imagem do cartaz (opcional) */
    private String cartazUrl;

    /** Em vez de apagar um filme, ele sai de cartaz (as sessões antigas continuam apontando para ele) */
    private Boolean emCartaz = true;

    public Filme() { }

    public Filme(String titulo, String sinopse, Integer duracao, Integer classificacao, String genero) {
        this.titulo = titulo;
        this.sinopse = sinopse;
        this.duracao = duracao;
        this.classificacao = classificacao;
        this.genero = genero;
        this.emCartaz = true;
    }

    // Getters e Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTitulo() { return titulo; }
    public void setTitulo(String titulo) { this.titulo = titulo; }

    public String getSinopse() { return sinopse; }
    public void setSinopse(String sinopse) { this.sinopse = sinopse; }

    public Integer getDuracao() { return duracao; }
    public void setDuracao(Integer duracao) { this.duracao = duracao; }

    public Integer getClassificacao() { return classificacao; }
    public void setClassificacao(Integer classificacao) { this.classificacao = classificacao; }

    public String getGenero() { return genero; }
    public void setGenero(String genero) { this.genero = genero; }

    public String getCartazUrl() { return cartazUrl; }
    public void setCartazUrl(String cartazUrl) { this.cartazUrl = cartazUrl; }

    public Boolean getEmCartaz() { return emCartaz; }
    public void setEmCartaz(Boolean emCartaz) { this.emCartaz = emCartaz; }
}
