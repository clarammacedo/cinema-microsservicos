# Rede de Cinemas — Microsserviços de Usuários e Fidelidade (JavaScript)

Parte da **Amanda Maria** no trabalho 4 de Arquitetura de Sistemas (UNIFOR).
Equipe: Amanda Maria (JavaScript), Ana Clara (Java) e Edson Terceiro (Python).

| Microsserviço | Porta local | Banco próprio | Papel |
|---|---|---|---|
| `usuarios-service` | 8085 | `db_usuarios` | **Provedor**: fornece os dados dos usuários e faz o login |
| `fidelidade-service` | 8086 | `db_fidelidade` | **Consumidor**: chama o Serviço de Usuários ao aderir ao programa |
| `frontend/index.html` | — | — | Abas **Usuários** e **Fidelidade** no frontend da equipe |

Tecnologias: JavaScript com Node.js 22 (módulo `http` nativo), banco **SQLite** (módulo `node:sqlite`, que já vem no Node, com um arquivo por serviço), HTML + JavaScript (fetch) e Render para a nuvem.
**Não precisa de `npm install`:** os serviços usam só o que vem com o Node.

---

## 1. Como as peças se conectam

```
 navegador (index.html)
     │  fetch("http://localhost:8086/fidelidade", POST { usuarioId: 1 })
     ▼
 fidelidade-service/server.js   (rota "aderir ao programa")
     │  fetch("http://localhost:8085/usuarios/1")    ← chamada entre microsserviços
     ▼
 usuarios-service/server.js     (devolve { id, nome, dataCadastro } ou 404)
     │  SELECT * FROM usuario WHERE id = 1
     ▼
 db_usuarios  (arquivo usuarios-service/data/db_usuarios.db)

 de volta no fidelidade-service:
     │  INSERT INTO conta_fidelidade (usuario_id, nome_usuario, ...)
     ▼
 db_fidelidade  (arquivo fidelidade-service/data/db_fidelidade.db)
```

Arquivos de cada serviço:
- `server.js`: as rotas (o que cada endpoint faz);
- `banco.js`: cria as tabelas no SQLite e os dados de exemplo;
- `util.js`: funções de apoio (ler o JSON, responder com CORS, roteador simples).

O Serviço de Fidelidade **não lê o banco de usuários**. Ele guarda só o `usuario_id` e uma cópia do nome.

Tabelas:
- `db_usuarios`: `usuario` (id, nome, email, senha_hash, telefone, data_nascimento, data_cadastro) e `sessao_login` (token, usuario_id, criado_em, expira_em).
- `db_fidelidade`: `conta_fidelidade` (id, usuario_id, nome_usuario, pontos, data_adesao) e `movimentacao` (id, conta_id, tipo ACUMULO/USO, pontos, pedido_id, descricao, data).

A senha nunca é salva como texto: é guardada como hash (`scrypt`, com sal aleatório).

---

## 2. Rodando no computador (VSCode)

**Pré-requisito:** Node.js 22.13 ou mais novo (`node -v` no terminal). Baixe em https://nodejs.org (versão LTS).

```bash
cd usuarios-service   && npm start     # terminal 1 → http://localhost:8085
cd fidelidade-service && npm start     # terminal 2 → http://localhost:8086
```

Depois abra o `frontend/index.html` no navegador (de preferência com a extensão **Live Server**).

Na primeira execução é criado o usuário de exemplo **cliente@cinema.com / senha 123456** (id 1).
Para apagar os dados e começar do zero, pare os serviços e apague as pastas `data/`.

**Ver o banco** (bom para mostrar no vídeo): instale a extensão **SQLite Viewer** no VSCode e clique no arquivo `data/db_usuarios.db` ou `data/db_fidelidade.db`.

---

## 3. Rotas (endpoints)

### Serviço de Usuários — `http://localhost:8085`

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/usuarios` | cadastrar usuário | O cliente precisa de conta para comprar e juntar pontos. Valida nome, email (único), senha (mín. 6), telefone e data de nascimento. |
| POST | `/login` | realizar login | Confere email e senha e devolve um **token** que vale 8 horas. |
| POST | `/logout` | realizar logout | Apaga o token no banco: depois disso ele não funciona mais. |
| GET | `/usuarios/me` | consultar dados | Mostra os dados completos do usuário logado (precisa do token). |
| PUT | `/usuarios/me` | atualizar cadastro | Altera nome, email, telefone, nascimento e, se pedir, a senha (exige a senha atual). Só altera o próprio cadastro. |
| GET | `/usuarios/{id}` | consultar dados públicos | **Rota usada pelos outros serviços** (Fidelidade e Pedidos) para saber se o usuário existe. Devolve só id, nome e data de cadastro. |

Rotas protegidas usam o cabeçalho `Authorization: Bearer <token>`.

Exemplos:
```json
POST /usuarios  { "nome": "Maria Souza", "email": "maria@email.com", "senha": "123456", "telefone": "85999990000", "dataNascimento": "2003-08-20" }
POST /login     { "email": "maria@email.com", "senha": "123456" }
PUT  /usuarios/me  { "telefone": "85988887777", "senhaAtual": "123456", "novaSenha": "nova123" }
```

### Serviço de Fidelidade — `http://localhost:8086`

Regras: **cada R$ 1,00 gasto = 1 ponto**; **cada ponto vale R$ 0,10** de desconto (100 pontos = R$ 10,00).

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/fidelidade` | aderir ao programa | Cria a conta de pontos. **Chama o Serviço de Usuários** para confirmar que o usuário existe (404 se não existir, 503 se o serviço estiver fora do ar). Não deixa aderir duas vezes. |
| GET | `/fidelidade/{usuarioId}` | ver número de pontos | Saldo de pontos e quanto ele vale em reais. |
| GET | `/fidelidade/{usuarioId}/extrato` | ver histórico | Mostra de onde vieram e onde foram usados os pontos, para o cliente conferir o saldo. |
| POST | `/fidelidade/{usuarioId}/acumular` | acumular pontos | Chamada pelo **Serviço de Pedidos/Pagamentos** quando a compra é paga. O mesmo `pedidoId` não gera pontos duas vezes (409). |
| POST | `/fidelidade/{usuarioId}/usar` | usar pontos | Troca pontos por desconto e devolve o valor do desconto. Recusa se o saldo for insuficiente (422). |

Exemplos:
```json
POST /fidelidade                 { "usuarioId": 1 }
POST /fidelidade/1/acumular      { "pedidoId": "123", "valor": 60.00 }
POST /fidelidade/1/usar          { "pontos": 100, "pedidoId": "124" }
```

### Rotas que **não** foram criadas (e por quê)

- **`DELETE /usuarios/{id}`**: o usuário tem pedidos, pagamentos e pontos em **outros bancos**. Apagar o cadastro deixaria esses registros apontando para ninguém, e os outros serviços não ficariam sabendo.
- **`GET /usuarios` (listar todos)**: exporia email e telefone de todos os clientes. Nenhuma tela do sistema precisa da lista completa.
- **`PUT /fidelidade/{usuarioId}` (alterar o saldo direto)**: os pontos só mudam por acúmulo ou uso, para que todo ponto tenha um registro no extrato.
- **Sair do programa / apagar conta de fidelidade**: o cliente perderia o histórico de pontos. Quem não quer mais participar simplesmente não usa.
- **Estornar pontos quando um pedido é cancelado**: dependeria de um fluxo combinado com Pedidos e Pagamentos (desfazer pagamento, assentos e pontos juntos), que ficou fora do escopo.

---

## 4. Integração com os outros serviços da equipe

- **Pedidos (Edson, Python):**
  - ao realizar um pedido → `GET {usuarios}/usuarios/{id}` para validar o cliente;
  - quando o cliente quiser desconto → `POST {fidelidade}/fidelidade/{id}/usar` com `{ "pontos": N, "pedidoId": "..." }` e subtrair o `valorDesconto` devolvido;
  - quando o pagamento for aprovado → `POST {fidelidade}/fidelidade/{id}/acumular` com `{ "pedidoId": "...", "valor": total_pago }`.
  - Se o cliente não participa do programa, a Fidelidade responde 404: é só seguir o pedido sem pontos.
- **Frontend:** o objeto `API` no começo do `<script>` do `index.html` tem as entradas `usuarios` e `fidelidade`.

---

## 5. Implantação na nuvem (Render, plano gratuito)

1. Suba o código para o GitHub (seção 6).
2. Em https://render.com → **New → Web Service** → conecte o repositório.
   - **Root Directory:** `usuarios-service`
   - **Language:** Node · **Build Command:** `npm install` · **Start Command:** `npm start` · **Instance type:** Free
   - Crie o serviço e copie o link (ex.: `https://cinema-usuarios.onrender.com`).
3. Repita para o `fidelidade-service` (Root Directory `fidelidade-service`) e, em **Environment**, adicione:
   - `USUARIOS_SERVICE_URL` = link do serviço de usuários (sem `/` no final)
4. No `frontend/index.html`, troque `https://SEU-usuarios-service.onrender.com` e `https://SEU-fidelidade-service.onrender.com` pelos links reais e faça commit (o frontend já está publicado pela Ana Clara; ele atualiza sozinho com o push).

Observações:
- O `package.json` pede Node 22.13 ou mais novo (`engines`), e o Render usa essa versão.
- O plano gratuito "dorme" após 15 min sem uso: abra os dois links antes de gravar o vídeo.
- No plano gratuito o arquivo SQLite é apagado quando o serviço reinicia, e o usuário de exemplo é recriado. Para dados permanentes seria preciso um disco persistente (pago) ou um banco externo.

---

## 6. Git (obrigatório usar CLI/IDE, **não** enviar arquivos pela interface do GitHub)

A Ana Clara precisa adicionar a Amanda como colaboradora (Settings → Collaborators). Depois, **no computador da Amanda**:

```bash
git config --global user.name  "Amanda Maria"
git config --global user.email "email-da-conta-github-da-amanda"

git clone https://github.com/clarammacedo/cinema-microsservicos.git
cd cinema-microsservicos
# copie para cá as pastas usuarios-service e fidelidade-service e os arquivos frontend/index.html, .gitignore e README-amanda.md

git add usuarios-service .gitignore
git commit -m "Cria microsservico de usuarios com banco db_usuarios e login por token"
git add fidelidade-service
git commit -m "Cria microsservico de fidelidade que consome o servico de usuarios"
git add frontend/index.html
git commit -m "Adiciona telas de usuarios e fidelidade no frontend"
git add README-amanda.md
git commit -m "Documenta rotas, execucao e implantacao dos servicos de usuarios e fidelidade"
git push
```

Listagem de commits para o relatório: `git log --author="Amanda" --pretty=format:"%h %ad %s" --date=short`.

---

## 7. Roteiro do vídeo (1 a 5 min)

1. **Objetivo** (15 s): sistema de rede de cinemas. Minha parte é Usuários e Fidelidade, em JavaScript/Node.js.
2. **Arquitetura** (30 s): mostrar o diagrama. Cada serviço tem seu banco (`db_usuarios`, `db_fidelidade`). Usuários é o provedor e Fidelidade é o consumidor.
3. **Demonstração na nuvem** (2 min): cadastrar um usuário → tentar cadastrar o mesmo email (erro) → login → atualizar o telefone → aderir à fidelidade (explicar que a Fidelidade chamou o Serviço de Usuários) → tentar aderir com um id que não existe (erro 404 vindo do outro serviço) → acumular pontos com um pedido → repetir o mesmo pedido (erro) → usar pontos e mostrar o extrato → logout.
4. **Rotas** (1 min): passar pelas tabelas da seção 3 e explicar as rotas que não foram criadas.
5. **Nuvem** (15 s): mostrar os dois serviços no painel do Render.
