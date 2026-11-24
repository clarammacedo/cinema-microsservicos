package br.unifor.cinema.filmes;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Ponto de entrada do Serviço de Filmes.
 * Rode esta classe (botão "Run" no VSCode) e a API sobe em http://localhost:8081
 */
@SpringBootApplication
public class FilmesApplication {
    public static void main(String[] args) {
        SpringApplication.run(FilmesApplication.class, args);
    }
}
