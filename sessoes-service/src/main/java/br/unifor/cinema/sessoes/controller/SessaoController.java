package br.unifor.cinema.sessoes.controller;

import br.unifor.cinema.sessoes.client.FilmesClient;
import br.unifor.cinema.sessoes.dto.AssentosResponse;
import br.unifor.cinema.sessoes.dto.FilmeDTO;
import br.unifor.cinema.sessoes.dto.NovaSessaoRequest;
import br.unifor.cinema.sessoes.dto.ReservaRequest;
import br.unifor.cinema.sessoes.model.Reserva;
import br.unifor.cinema.sessoes.model.Sala;
import br.unifor.cinema.sessoes.model.Sessao;
import br.unifor.cinema.sessoes.repository.ReservaRepository;
import br.unifor.cinema.sessoes.repository.SalaRepository;
import br.unifor.cinema.sessoes.repository.SessaoRepository;
import jakarta.validation.Valid;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * Rotas de sessões e assentos.
 *
 *   POST   /sessoes                          -> criar sessão (consulta o Serviço de Filmes)
 *   GET    /sessoes                          -> listar sessões (filtros: ?filmeId= &cinemaId= &data=AAAA-MM-DD)
 *   GET    /sessoes/{id}                     -> detalhes de uma sessão
 *   GET    /sessoes/{id}/assentos            -> ver assentos livres
 *   POST   /sessoes/{id}/reservas            -> ocupar assentos (chamada pelo Serviço de Pedidos)
 *   DELETE /sessoes/{id}/reservas/{pedidoId} -> liberar assentos (pedido cancelado)
 */
@RestController
@RequestMapping("/sessoes")
public class SessaoController {

    /** Tempo de limpeza da sala entre uma sessão e outra */
    private static final int INTERVALO_LIMPEZA_MIN = 20;

    private final SessaoRepository sessaoRepository;
    private final SalaRepository salaRepository;
    private final ReservaRepository reservaRepository;
    private final FilmesClient filmesClient;

    public SessaoController(SessaoRepository sessaoRepository, SalaRepository salaRepository,
                            ReservaRepository reservaRepository, FilmesClient filmesClient) {
        this.sessaoRepository = sessaoRepository;
        this.salaRepository = salaRepository;
        this.reservaRepository = reservaRepository;
        this.filmesClient = filmesClient;
    }

    /** Criar sessão */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Sessao criar(@Valid @RequestBody NovaSessaoRequest dados) {
        Sala sala = salaRepository.findById(dados.salaId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Sala " + dados.salaId() + " não existe"));

        // >>> Chamada HTTP para o outro microsserviço <<<
        FilmeDTO filme = filmesClient.buscarFilme(dados.filmeId());
        if (Boolean.FALSE.equals(filme.emCartaz())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O filme \"" + filme.titulo() + "\" não está em cartaz");
        }

        LocalDateTime inicio = dados.dataHora();
        LocalDateTime fim = inicio.plusMinutes(filme.duracao());
        verificarConflitoDeHorario(sala, inicio, fim);

        Sessao sessao = new Sessao();
        sessao.setFilmeId(filme.id());
        sessao.setTituloFilme(filme.titulo());
        sessao.setDuracaoFilme(filme.duracao());
        sessao.setClassificacao(filme.classificacao());
        sessao.setSala(sala);
        sessao.setDataHora(inicio);
        sessao.setIdioma(dados.idioma());
        sessao.setFormato(dados.formato());
        sessao.setPreco(dados.preco());
        return sessaoRepository.save(sessao);
    }

    /** Listar sessões */
    @GetMapping
    public List<Sessao> listar(@RequestParam(required = false) Long filmeId,
                               @RequestParam(required = false) Long cinemaId,
                               @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate data) {
        return sessaoRepository.findAll().stream()
                .filter(s -> filmeId == null || filmeId.equals(s.getFilmeId()))
                .filter(s -> cinemaId == null || cinemaId.equals(s.getSala().getCinema().getId()))
                .filter(s -> data == null || data.equals(s.getDataHora().toLocalDate()))
                .sorted(Comparator.comparing(Sessao::getDataHora))
                .toList();
    }

    /** Detalhes de uma sessão (o Serviço de Pedidos usa para saber o preço) */
    @GetMapping("/{id}")
    public Sessao detalhes(@PathVariable Long id) {
        return sessaoRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Sessão " + id + " não encontrada"));
    }

    /** Ver assentos livres */
    @GetMapping("/{id}/assentos")
    public AssentosResponse assentos(@PathVariable Long id) {
        Sessao sessao = detalhes(id);
        Sala sala = sessao.getSala();
        Set<String> ocupados = new HashSet<>();
        for (Reserva r : reservaRepository.findBySessaoId(id)) {
            ocupados.add(r.getAssento());
        }
        List<String> todos = sala.gerarAssentos();
        List<String> livres = todos.stream().filter(a -> !ocupados.contains(a)).toList();
        List<String> ocupadosOrdenados = todos.stream().filter(ocupados::contains).toList();
        return new AssentosResponse(id, sala.getFileiras(), sala.getAssentosPorFileira(),
                sala.getCapacidade(), livres.size(), livres, ocupadosOrdenados);
    }

    /** Ocupar assentos de um pedido (usado pelo Serviço de Pedidos) */
    @PostMapping("/{id}/reservas")
    @ResponseStatus(HttpStatus.CREATED)
    @Transactional
    public AssentosResponse reservar(@PathVariable Long id, @Valid @RequestBody ReservaRequest dados) {
        Sessao sessao = detalhes(id);
        List<String> existentes = sessao.getSala().gerarAssentos();
        Set<String> ocupados = new HashSet<>();
        reservaRepository.findBySessaoId(id).forEach(r -> ocupados.add(r.getAssento()));

        Set<String> pedidos = new LinkedHashSet<>();
        for (String a : dados.assentos()) {
            String assento = a.trim().toUpperCase();
            if (!existentes.contains(assento)) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "O assento " + assento + " não existe nesta sala");
            }
            if (ocupados.contains(assento)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "O assento " + assento + " já está ocupado");
            }
            pedidos.add(assento);
        }
        for (String assento : pedidos) {
            reservaRepository.save(new Reserva(sessao, assento, dados.pedidoId()));
        }
        return assentos(id);
    }

    /** Liberar os assentos de um pedido cancelado */
    @DeleteMapping("/{id}/reservas/{pedidoId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    @Transactional
    public void liberar(@PathVariable Long id, @PathVariable String pedidoId) {
        detalhes(id);
        List<Reserva> reservas = reservaRepository.findBySessaoIdAndPedidoId(id, pedidoId);
        if (reservas.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Nenhum assento reservado para o pedido " + pedidoId);
        }
        reservaRepository.deleteAll(reservas);
    }

    /** Regra de negócio: a mesma sala não pode ter duas sessões ao mesmo tempo */
    private void verificarConflitoDeHorario(Sala sala, LocalDateTime inicio, LocalDateTime fim) {
        for (Sessao outra : sessaoRepository.findBySalaId(sala.getId())) {
            LocalDateTime outraInicio = outra.getDataHora();
            LocalDateTime outraFim = outra.getFim().plusMinutes(INTERVALO_LIMPEZA_MIN);
            boolean sobrepoe = inicio.isBefore(outraFim) && fim.plusMinutes(INTERVALO_LIMPEZA_MIN).isAfter(outraInicio);
            if (sobrepoe) {
                throw new ResponseStatusException(HttpStatus.CONFLICT,
                        "A sala " + sala.getNumero() + " já tem a sessão de \"" + outra.getTituloFilme()
                                + "\" às " + outraInicio.toLocalTime() + " nesse horário");
            }
        }
    }
}
