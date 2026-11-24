package br.unifor.cinema.sessoes.model;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;

/** Unidade da rede de cinemas (classe "Cinemas" do diagrama de classes). */
@Entity
@Table(name = "cinema")
public class Cinema {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank(message = "O nome do cinema é obrigatório")
    private String nome;

    @NotBlank(message = "A cidade é obrigatória")
    private String cidade;

    private String endereco;

    public Cinema() { }

    public Cinema(String nome, String cidade, String endereco) {
        this.nome = nome;
        this.cidade = cidade;
        this.endereco = endereco;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getNome() { return nome; }
    public void setNome(String nome) { this.nome = nome; }

    public String getCidade() { return cidade; }
    public void setCidade(String cidade) { this.cidade = cidade; }

    public String getEndereco() { return endereco; }
    public void setEndereco(String endereco) { this.endereco = endereco; }
}
