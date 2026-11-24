package br.unifor.cinema.sessoes.client;

import br.unifor.cinema.sessoes.dto.FilmeDTO;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/**
 * COMUNICAÇÃO ENTRE MICROSSERVIÇOS
 * O Serviço de Sessões (consumidor) chama o Serviço de Filmes (provedor) via HTTP:
 *     GET {filmes.service.url}/filmes/{id}
 * para confirmar que o filme existe antes de criar uma sessão.
 */
@Component
public class FilmesClient {

    private final RestClient restClient;

    public FilmesClient(RestClient.Builder builder,
                        @Value("${filmes.service.url}") String filmesUrl) {
        this.restClient = builder.baseUrl(filmesUrl).build();
    }

    public FilmeDTO buscarFilme(Long filmeId) {
        try {
            return restClient.get()
                    .uri("/filmes/{id}", filmeId)
                    .retrieve()
                    .body(FilmeDTO.class);
        } catch (HttpClientErrorException.NotFound e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "O filme " + filmeId + " não existe no Serviço de Filmes");
        } catch (ResourceAccessException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Serviço de Filmes indisponível. Ele está rodando?");
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "Erro ao consultar o Serviço de Filmes: " + e.getMessage());
        }
    }
}
