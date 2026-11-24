# Rede de Cinemas — Microsserviços de Filmes e Sessões (Java)

Parte da **Ana Clara** no trabalho 4 de Arquitetura de Sistemas (UNIFOR).
Equipe: Amanda Maria (JavaScript), Ana Clara (Java) e Edson Terceiro (Python).

| Microsserviço | Porta local | Banco próprio | Papel |
|---|---|---|---|
| `filmes-service` | 8081 | `db_filmes` | **Provedor**: fornece os dados dos filmes |
| `sessoes-service` | 8082 | `db_sessoes` | **Consumidor**: chama o Serviço de Filmes ao criar uma sessão |
| `frontend/index.html` | — | — | Página HTML que chama os serviços |

Tecnologias: Java 17, Spring Boot 3 (Web, Data JPA, Validation), banco H2 (um arquivo por serviço), HTML + JavaScript (fetch), Docker e Render para a nuvem.

---

## 1. Como as peças se conectam (Java + HTML + banco)

```
 navegador (index.html)
     │  fetch("http://localhost:8081/filmes")   ← HTTP + JSON
     ▼
 FilmeController  (recebe a requisição, valida os dados)
     │  repository.findAll()
     ▼
 FilmeRepository  (Spring Data JPA gera o SQL sozinho)
     │  SELECT * FROM filme
     ▼
 db_filmes  (arquivo H2: filmes-service/data/db_filmes.mv.db)
```

- **HTML → Java:** o JavaScript do `index.html` usa `fetch()` para fazer requisições HTTP (GET, POST, PUT, DELETE) e recebe **JSON** de volta. O `CorsConfig` libera essas chamadas (sem ele o navegador bloqueia).
- **Java → banco:** cada classe `@Entity` (Filme, Cinema, Sala, Sessao, Reserva) vira uma tabela. O Hibernate cria as tabelas sozinho (`ddl-auto=update`) e o `Repository` faz os SELECT/INSERT/UPDATE.
- **Serviço → serviço:** ao criar uma sessão, o `FilmesClient` do Serviço de Sessões faz `GET /filmes/{id}` no Serviço de Filmes. Se o filme não existir ou estiver fora de cartaz, a sessão é recusada. O Serviço de Sessões guarda só o `filmeId` e uma cópia do título e da duração, porque **não pode acessar o banco do outro serviço**.

---

## 2. Rodando no computador (VSCode)

**Pré-requisitos:** JDK 17 ou mais novo, e no VSCode as extensões *Extension Pack for Java* e *Spring Boot Extension Pack*. Maven é opcional: a extensão do Java baixa as dependências sozinha.

1. Abra a pasta `cinema-microsservicos` no VSCode e espere ele carregar os projetos Java (pode demorar alguns minutos na primeira vez).
2. Abra `filmes-service/.../FilmesApplication.java` e clique em **Run**. Espere aparecer `Started FilmesApplication`.
3. Abra `sessoes-service/.../SessoesApplication.java` e clique em **Run**.
4. Abra o `frontend/index.html` no navegador (de preferência com a extensão **Live Server**: botão direito → *Open with Live Server*).

Se preferir o terminal (com Maven instalado):
```bash
cd filmes-service  && mvn spring-boot:run     # terminal 1
cd sessoes-service && mvn spring-boot:run     # terminal 2
```

**Ver o banco de cada serviço** (bom para mostrar no vídeo):
- http://localhost:8081/h2-console → JDBC URL `jdbc:h2:file:./data/db_filmes;AUTO_SERVER=TRUE`, usuário `sa`, senha vazia
- http://localhost:8082/h2-console → JDBC URL `jdbc:h2:file:./data/db_sessoes;AUTO_SERVER=TRUE`

Na primeira execução, cada serviço cadastra dados de exemplo: 3 filmes, e o cinema "Cine Centro" com 2 salas.

---

## 3. Rotas (endpoints)

### Serviço de Filmes — `http://localhost:8081`

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/filmes` | adicionar filme | O cinema precisa cadastrar os filmes que vai exibir. Valida título, duração e classificação (Livre, 10, 12, 14, 16 ou 18). |
| PUT | `/filmes/{id}` | atualizar filme | Corrigir dados e **tirar de cartaz** (`emCartaz: false`). |
| GET | `/filmes` | listar filmes | Mostrar a programação. Filtros opcionais `?genero=` e `?emCartaz=true`. |
| GET | `/filmes/{id}` | consultar detalhes | Mostrar a sinopse e os detalhes de um filme. **Também é a rota usada pelo Serviço de Sessões** para validar o filme. |

Exemplo de corpo do POST/PUT:
```json
{ "titulo": "Código Fantasma", "sinopse": "...", "duracao": 128, "classificacao": 14, "genero": "Ficção científica", "emCartaz": true }
```

### Serviço de Sessões — `http://localhost:8082`

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/cinemas` | cadastrar cinema | A rede tem várias unidades. |
| GET | `/cinemas` | listar cinemas | Preencher os menus do frontend. |
| POST | `/cinemas/{id}/salas` | cadastrar sala | A sala define a grade de assentos (fileiras × assentos por fileira). |
| GET | `/cinemas/{id}/salas` | listar salas | Escolher a sala ao criar a sessão. |
| POST | `/sessoes` | criar sessão | Consulta o Serviço de Filmes, copia título e duração e **impede duas sessões na mesma sala ao mesmo tempo** (com 20 min de limpeza entre elas). |
| GET | `/sessoes` | listar sessões | Programação. Filtros `?filmeId=`, `?cinemaId=` e `?data=AAAA-MM-DD`. |
| GET | `/sessoes/{id}` | detalhes da sessão | O Serviço de Pedidos usa para saber o preço e o horário. |
| GET | `/sessoes/{id}/assentos` | ver assentos livres | Lista os livres e os ocupados para o cliente escolher. |
| POST | `/sessoes/{id}/reservas` | ocupar assentos | Chamada pelo **Serviço de Pedidos** ao realizar um pedido. Devolve 409 se o assento já estiver ocupado. |
| DELETE | `/sessoes/{id}/reservas/{pedidoId}` | liberar assentos | Chamada pelo Serviço de Pedidos quando um pedido é **cancelado**. |

Exemplo para criar sessão:
```json
{ "filmeId": 1, "salaId": 1, "dataHora": "2026-12-05T19:30", "idioma": "Dublado", "formato": "2D", "preco": 30.00 }
```
Exemplo de reserva (enviado pelo Serviço de Pedidos):
```json
{ "pedidoId": "123", "assentos": ["C4", "C5"] }
```

### Rotas que **não** foram criadas (e por quê)

- **`DELETE /filmes/{id}`**: apagar um filme deixaria sessões e ingressos já vendidos apontando para um filme inexistente, e o Serviço de Sessões não tem como saber disso, porque está em outro banco. Por isso o filme só **sai de cartaz** pelo `PUT`.
- **`PUT` e `DELETE` de sessões**: mudar o horário ou apagar uma sessão com ingressos vendidos afetaria pedidos e pagamentos de outros serviços. Isso exigiria um fluxo de reembolso que fica fora do escopo. Uma sessão errada sem vendas pode ser recriada.
- **`PUT` e `DELETE` de cinemas e salas**: mudar a grade de uma sala invalidaria os assentos já reservados. Cinemas e salas mudam raramente, então foram deixados só cadastro e consulta.
- **Venda de ingresso / cálculo de valor**: é responsabilidade do Serviço de Pedidos (Edson). O Serviço de Sessões só controla quais assentos estão ocupados.

---

## 4. Integração com os outros serviços da equipe

- **Pedidos (Edson, Python):** ao realizar um pedido → `GET /sessoes/{id}` (preço) e `POST /sessoes/{id}/reservas`. Ao cancelar → `DELETE /sessoes/{id}/reservas/{pedidoId}`.
- **Frontend:** o `index.html` tem um objeto `API` no começo do `<script>`. Cada integrante adiciona o endereço do seu serviço e as suas abas.

---

## 5. Implantação na nuvem (Render, plano gratuito)

1. Suba o código para o GitHub (seção 6).
2. Em https://render.com → **New → Web Service** → conecte o repositório.
   - **Root Directory:** `filmes-service`
   - **Runtime/Language:** Docker · **Instance type:** Free
   - Crie o serviço e copie o link gerado (ex.: `https://cinema-filmes.onrender.com`).
3. Repita para `sessoes-service` (Root Directory `sessoes-service`) e, em **Environment**, adicione:
   - `FILMES_SERVICE_URL` = link do serviço de filmes (sem `/` no final)
4. No `frontend/index.html`, troque `https://SEU-filmes-service.onrender.com` e `https://SEU-sessoes-service.onrender.com` pelos links reais, faça commit e publique o frontend: **New → Static Site** com Root Directory `frontend` (ou use o GitHub Pages).

Observações:
- O plano gratuito "dorme" após 15 min sem uso. A primeira chamada pode demorar uns 50 segundos, então abra os links antes de gravar o vídeo.
- Na nuvem, o H2 é apagado quando o serviço reinicia, e os dados de exemplo são recriados. Para dados permanentes, crie um PostgreSQL (Render ou Neon) **para cada serviço** e defina `DB_URL` (`jdbc:postgresql://...`), `DB_USER` e `DB_PASSWORD`.

---

## 6. Git (obrigatório usar CLI/IDE, **não** enviar arquivos pela interface do GitHub)

```bash
git clone https://github.com/<repositorio-da-equipe>.git
cd <repositorio>
# copie as pastas filmes-service, sessoes-service e frontend para cá
git add filmes-service
git commit -m "Cria microsserviço de filmes (entidade, repositório e rotas)"
git add sessoes-service
git commit -m "Cria microsserviço de sessões com consulta ao serviço de filmes"
git add frontend
git commit -m "Adiciona telas de filmes, sessões e assentos no frontend"
git push
```
Fazer commits pequenos, um por etapa, deixa a listagem de commits do relatório mais clara. Para gerar a listagem: `git log --author="Ana Clara" --pretty=format:"%h %ad %s" --date=short`.

---

## 7. Roteiro do vídeo (1 a 5 min)

1. **Objetivo** (15 s): sistema de rede de cinemas. Minha parte é Filmes e Sessões, em Java/Spring Boot.
2. **Arquitetura** (30 s): mostrar o diagrama. Cada serviço tem seu banco (`db_filmes`, `db_sessoes`). Filmes é o provedor e Sessões é o consumidor.
3. **Demonstração na nuvem** (2 min): adicionar e editar um filme → criar uma sessão (explicar que o Serviço de Sessões chamou o de Filmes) → tentar criar outra sessão no mesmo horário e mostrar o erro → ver os assentos → reservar e liberar.
4. **Rotas** (1 min): passar pelas tabelas da seção 3 e explicar as rotas que não foram criadas.
5. **Nuvem** (15 s): mostrar os serviços rodando no painel do Render.
