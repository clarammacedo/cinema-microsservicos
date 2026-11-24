package br.unifor.cinema.sessoes;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Ponto de entrada do Serviço de Sessões.
 * Rode esta classe e a API sobe em http://localhost:8082
 * (o Serviço de Filmes precisa estar rodando para criar sessões).
 */
@SpringBootApplication
public class SessoesApplication {
    public static void main(String[] args) {
        SpringApplication.run(SessoesApplication.class, args);
    }
}
