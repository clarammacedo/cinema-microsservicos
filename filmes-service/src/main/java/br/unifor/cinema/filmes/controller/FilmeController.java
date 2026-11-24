package br.unifor.cinema.filmes.controller;

import br.unifor.cinema.filmes.model.Filme;
import br.unifor.cinema.filmes.repository.FilmeRepository;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.Comparator;
import java.util.List;
import java.util.Set;

/**
 * Rotas (endpoints) do Serviço de Filmes.
 *
 *   POST /filmes          -> adicionar filme
 *   PUT  /filmes/{id}     -> atualizar filme
 *   GET  /filmes          -> listar filmes (filtros opcionais: ?genero=Ação&emCartaz=true)
 *   GET  /filmes/{id}     -> consultar detalhes (também usada pelo Serviço de Sessões)
 */
@RestController
@RequestMapping("/filmes")
public class FilmeController {

    private static final Set<Integer> CLASSIFICACOES_VALIDAS = Set.of(0, 10, 12, 14, 16, 18);

    private final FilmeRepository repository;

    public FilmeController(FilmeRepository repository) {
        this.repository = repository;
    }

    /** Listar filmes */
    @GetMapping
    public List<Filme> listar(@RequestParam(required = false) String genero,
                              @RequestParam(required = false) Boolean emCartaz) {
        return repository.findAll().stream()
                .filter(f -> genero == null || genero.isBlank() || f.getGenero().equalsIgnoreCase(genero))
                .filter(f -> emCartaz == null || emCartaz.equals(f.getEmCartaz()))
                .sorted(Comparator.comparing(Filme::getTitulo, String.CASE_INSENSITIVE_ORDER))
                .toList();
    }

    /** Consultar detalhes de um filme */
    @GetMapping("/{id}")
    public Filme detalhes(@PathVariable Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Filme " + id + " não encontrado"));
    }

    /** Adicionar filme */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Filme adicionar(@Valid @RequestBody Filme filme) {
        validarClassificacao(filme.getClassificacao());
        filme.setId(null); // o id é sempre gerado pelo banco
        if (filme.getEmCartaz() == null) filme.setEmCartaz(true);
        return repository.save(filme);
    }

    /** Atualizar filme (também serve para tirar de cartaz: emCartaz = false) */
    @PutMapping("/{id}")
    public Filme atualizar(@PathVariable Long id, @Valid @RequestBody Filme dados) {
        Filme filme = detalhes(id);
        validarClassificacao(dados.getClassificacao());
        filme.setTitulo(dados.getTitulo());
        filme.setSinopse(dados.getSinopse());
        filme.setDuracao(dados.getDuracao());
        filme.setClassificacao(dados.getClassificacao());
        filme.setGenero(dados.getGenero());
        filme.setCartazUrl(dados.getCartazUrl());
        if (dados.getEmCartaz() != null) filme.setEmCartaz(dados.getEmCartaz());
        return repository.save(filme);
    }

    private void validarClassificacao(Integer classificacao) {
        if (!CLASSIFICACOES_VALIDAS.contains(classificacao)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                    "Classificação deve ser 0 (Livre), 10, 12, 14, 16 ou 18");
        }
    }
}
