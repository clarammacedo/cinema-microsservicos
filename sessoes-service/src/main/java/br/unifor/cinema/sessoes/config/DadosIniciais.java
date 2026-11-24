package br.unifor.cinema.sessoes.config;

import br.unifor.cinema.sessoes.model.Cinema;
import br.unifor.cinema.sessoes.model.Sala;
import br.unifor.cinema.sessoes.repository.CinemaRepository;
import br.unifor.cinema.sessoes.repository.SalaRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

/** Cria um cinema com duas salas quando o banco db_sessoes está vazio. */
@Component
public class DadosIniciais implements CommandLineRunner {

    private final CinemaRepository cinemaRepository;
    private final SalaRepository salaRepository;

    public DadosIniciais(CinemaRepository cinemaRepository, SalaRepository salaRepository) {
        this.cinemaRepository = cinemaRepository;
        this.salaRepository = salaRepository;
    }

    @Override
    public void run(String... args) {
        if (cinemaRepository.count() > 0) return;
        Cinema cinema = cinemaRepository.save(new Cinema("Cine Centro", "Fortaleza", "Av. Central, 1000"));
        salaRepository.save(novaSala(cinema, 1, "2D", 6, 10));
        salaRepository.save(novaSala(cinema, 2, "3D", 5, 8));
    }

    private Sala novaSala(Cinema cinema, int numero, String tipo, int fileiras, int assentosPorFileira) {
        Sala sala = new Sala();
        sala.setCinema(cinema);
        sala.setNumero(numero);
        sala.setTipo(tipo);
        sala.setFileiras(fileiras);
        sala.setAssentosPorFileira(assentosPorFileira);
        return sala;
    }
}
