package br.unifor.cinema.filmes.config;

import br.unifor.cinema.filmes.model.Filme;
import br.unifor.cinema.filmes.repository.FilmeRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

/**
 * Coloca alguns filmes no banco quando ele está vazio,
 * para a demonstração não começar com a tela em branco.
 */
@Component
public class DadosIniciais implements CommandLineRunner {

    private final FilmeRepository repository;

    public DadosIniciais(FilmeRepository repository) {
        this.repository = repository;
    }

    @Override
    public void run(String... args) {
        if (repository.count() > 0) return;
        repository.save(new Filme("Aventura no Sertão",
                "Três amigos atravessam o sertão cearense atrás de um tesouro perdido.", 112, 10, "Aventura"));
        repository.save(new Filme("Código Fantasma",
                "Uma programadora descobre que o sistema que criou ganhou vida própria.", 128, 14, "Ficção científica"));
        repository.save(new Filme("Risadas de Domingo",
                "Uma família tenta sobreviver a um almoço de domingo cheio de confusões.", 95, 0, "Comédia"));
    }
}
