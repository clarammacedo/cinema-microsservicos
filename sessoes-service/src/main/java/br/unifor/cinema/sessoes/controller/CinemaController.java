package br.unifor.cinema.sessoes.controller;

import br.unifor.cinema.sessoes.dto.NovaSalaRequest;
import br.unifor.cinema.sessoes.model.Cinema;
import br.unifor.cinema.sessoes.model.Sala;
import br.unifor.cinema.sessoes.repository.CinemaRepository;
import br.unifor.cinema.sessoes.repository.SalaRepository;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

/**
 * Rotas de cinemas e salas ("cadastrar cinema e sala" no diagrama).
 *
 *   POST /cinemas              -> cadastrar cinema
 *   GET  /cinemas              -> listar cinemas
 *   POST /cinemas/{id}/salas   -> cadastrar sala em um cinema
 *   GET  /cinemas/{id}/salas   -> listar salas de um cinema
 */
@RestController
@RequestMapping("/cinemas")
public class CinemaController {

    private final CinemaRepository cinemaRepository;
    private final SalaRepository salaRepository;

    public CinemaController(CinemaRepository cinemaRepository, SalaRepository salaRepository) {
        this.cinemaRepository = cinemaRepository;
        this.salaRepository = salaRepository;
    }

    @GetMapping
    public List<Cinema> listar() {
        return cinemaRepository.findAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Cinema cadastrar(@Valid @RequestBody Cinema cinema) {
        cinema.setId(null);
        return cinemaRepository.save(cinema);
    }

    @GetMapping("/{cinemaId}/salas")
    public List<Sala> listarSalas(@PathVariable Long cinemaId) {
        buscarCinema(cinemaId);
        return salaRepository.findByCinemaIdOrderByNumero(cinemaId);
    }

    @PostMapping("/{cinemaId}/salas")
    @ResponseStatus(HttpStatus.CREATED)
    public Sala cadastrarSala(@PathVariable Long cinemaId, @Valid @RequestBody NovaSalaRequest dados) {
        Cinema cinema = buscarCinema(cinemaId);
        if (salaRepository.existsByCinemaIdAndNumero(cinemaId, dados.numero())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "Já existe a sala " + dados.numero() + " neste cinema");
        }
        Sala sala = new Sala();
        sala.setNumero(dados.numero());
        sala.setTipo(dados.tipo());
        sala.setFileiras(dados.fileiras());
        sala.setAssentosPorFileira(dados.assentosPorFileira());
        sala.setCinema(cinema);
        return salaRepository.save(sala);
    }

    private Cinema buscarCinema(Long id) {
        return cinemaRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Cinema " + id + " não encontrado"));
    }
}
