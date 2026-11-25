# Rede de Cinemas — Microsserviços de Pedidos e Pagamentos (Python)

Parte do **Edson Terceiro** no trabalho 4 de Arquitetura de Sistemas (UNIFOR).
Equipe: Amanda Maria (JavaScript), Ana Clara (Java) e Edson Terceiro (Python).

| Microsserviço | Porta local | Banco próprio | Papel |
|---|---|---|---|
| `pedidos-service` | 8083 | `db_pedidos` | **Consumidor** de Usuários, Sessões e Fidelidade · **Provedor** para Pagamentos |
| `pagamentos-service` | 8084 | `db_pagamentos` | **Consumidor**: chama o Serviço de Pedidos (e o de Fidelidade) |
| `frontend/index.html` | — | — | Abas **Pedidos** e **Pagamentos** no frontend da equipe |

Tecnologias: Python 3.10+ com **Flask**, banco **SQLite** (módulo `sqlite3`, que já vem no Python, com um arquivo por serviço), chamadas HTTP entre serviços com `urllib` (também já vem no Python), HTML + JavaScript (fetch), Gunicorn e Render para a nuvem.

As classes do projeto antigo (`Pedido`, `Ingresso`, `Pagamento`, `Pix`, `Cartao`, `StatusPedido`, `StatusPagamento`, em github.com/EdsonTerceiro/Cinema) viraram as tabelas e as regras destes serviços. A ideia da classe abstrata `Pagamento` com `autorizar()` diferente no Pix e no Cartão (polimorfismo, GRASP) continua em `pagamentos-service/formas.py`.

---

## 1. Como as peças se conectam

```
 navegador (index.html)
     │  POST /pedidos { usuarioId, sessaoId, ingressos: [{assento, tipo}], pontos }
     ▼
 pedidos-service (Python)
     ├─► GET  {usuarios}/usuarios/{id}            o cliente existe?            (Amanda, JS)
     ├─► GET  {sessoes}/sessoes/{id}              preço, filme e horário        (Ana Clara, Java)
     ├─► POST {sessoes}/sessoes/{id}/reservas     ocupa os assentos (409 se ocupado)
     ├─► POST {fidelidade}/fidelidade/{id}/usar   desconto com pontos (opcional)
     ▼
 db_pedidos  (pedido + ingresso)   → status ABERTO, aguardando pagamento

 navegador → POST /pagamentos/cartao  (ou /pagamentos/pix + /confirmar)
     ▼
 pagamentos-service (Python)
     ├─► GET  {pedidos}/pedidos/{id}                       valor e status do pedido
     ├─► POST {pedidos}/pedidos/{id}/confirmar-pagamento   pedido passa a PAGO
     ├─► POST {fidelidade}/fidelidade/{id}/acumular        credita os pontos
     ▼
 db_pagamentos  (pagamento + pix + cartao)
```

Arquivos de cada serviço:
- `app.py`: as rotas (o que cada endpoint faz);
- `banco.py`: cria as tabelas no SQLite;
- `util.py`: funções de apoio (CORS, erros em JSON, chamada HTTP a outro serviço);
- `formas.py` (só Pagamentos): classes `Pix` e `Cartao`;
- `requirements.txt`: dependências (`flask` e `gunicorn`).

Nenhum serviço lê o banco do outro. O Pedidos guarda só o `usuario_id` e o `sessao_id`, com uma cópia do nome do cliente, do título do filme, do horário e da sala. O Pagamentos guarda só o `pedido_id` e o `usuario_id`.

Tabelas:
- `db_pedidos`: `pedido` (id, usuario_id, nome_usuario, sessao_id, titulo_filme, data_hora_sessao, fim_sessao, local_sessao, subtotal, pontos_usados, desconto, valor_total, status, pagamento_id, datas) e `ingresso` (id, pedido_id, codigo, assento, tipo INTEIRA/MEIA, valor, utilizado_em).
- `db_pagamentos`: `pagamento` (id, pedido_id, usuario_id, valor, metodo PIX/CARTAO, status, motivo, pontos_ganhos, datas), `pix` (pagamento_id, chave_pix, qr_code, expira_em) e `cartao` (pagamento_id, nome_titular, final_cartao, bandeira, parcelas, valor_parcela, codigo_autorizacao).

Do cartão só ficam guardados os **4 últimos dígitos** e a bandeira. O número completo e o CVV nunca são salvos.

Status (vindos dos enums do projeto antigo):
- Pedido: `ABERTO` → `PAGO` → `FINALIZADO` (todos os ingressos usados), ou `CANCELADO`.
- Pagamento: `PENDENTE` (Pix aguardando) → `CONFIRMADO` → `ESTORNADO`, ou `RECUSADO`.

---

## 2. Rodando no computador (VSCode)

**Pré-requisito:** Python 3.10 ou mais novo (`python --version`). No VSCode, a extensão *Python* da Microsoft.

```bash
cd pedidos-service
pip install -r requirements.txt
python app.py                 # terminal 1 → http://localhost:8083

cd pagamentos-service
pip install -r requirements.txt
python app.py                 # terminal 2 → http://localhost:8084
```

Para a demonstração completa, os serviços da Ana Clara (8081, 8082) e da Amanda (8085, 8086) também precisam estar rodando (veja o `README.md` e o `README-amanda.md`). Depois abra o `frontend/index.html` com o **Live Server**.

Os bancos são criados sozinhos em `data/db_pedidos.db` e `data/db_pagamentos.db`. Para começar do zero, pare os serviços e apague as pastas `data/`.

**Ver o banco** (bom para mostrar no vídeo): extensão **SQLite Viewer** no VSCode e clique no arquivo `.db`.

---

## 3. Rotas (endpoints)

### Serviço de Pedidos — `http://localhost:8083`

Regras: inteira = preço da sessão, **meia = 50%**; até **10 ingressos** por pedido; não vende para sessão que já começou; os pontos de fidelidade pagam **no máximo 50%** do pedido.

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/pedidos` | realizar pedido | Valida o cliente no **Serviço de Usuários**, busca o preço no **Serviço de Sessões**, calcula o total (inteira/meia), ocupa os assentos (**Sessões**) e, se pedido, usa pontos (**Fidelidade**). Gera um código único para cada ingresso. Se alguma etapa falhar, desfaz as anteriores (libera os assentos e apaga o pedido). |
| GET | `/pedidos?usuarioId=` | listar pedidos do cliente | A tela "Meus pedidos". Filtro opcional `&status=`. |
| GET | `/pedidos/{id}` | consultar detalhes | Mostra ingressos, valores e status. **É a rota que o Serviço de Pagamentos usa** para saber quanto cobrar. |
| POST | `/pedidos/{id}/cancelar` | cancelar pedido | Pedido ABERTO: o cliente cancela e os assentos voltam a ficar livres (**Sessões**). Pedido PAGO: só pelo estorno do Serviço de Pagamentos. Não cancela se a sessão já começou ou se algum ingresso já foi usado. |
| POST | `/pedidos/{id}/confirmar-pagamento` | marcar como pago | **Chamada pelo Serviço de Pagamentos** quando o pagamento é aprovado. Só aceita pedido ABERTO, então um pedido cancelado não pode ser pago. |
| POST | `/ingressos/{codigo}/validar` | validar ingresso | Usada na entrada da sala: só libera se o pedido estiver pago, o ingresso não tiver sido usado e a sessão não tiver terminado. Quando todos os ingressos são usados, o pedido vira FINALIZADO. |

Exemplo para realizar pedido:
```json
{ "usuarioId": 1, "sessaoId": 1, "pontos": 0,
  "ingressos": [ { "assento": "C4", "tipo": "INTEIRA" }, { "assento": "C5", "tipo": "MEIA" } ] }
```

### Serviço de Pagamentos — `http://localhost:8084`

| Método | Rota | Funcionalidade | Por que existe |
|---|---|---|---|
| POST | `/pagamentos/pix` | pagar com Pix (1/2) | Consulta o pedido no **Serviço de Pedidos** e gera o código "copia e cola" (válido por 30 min). O pagamento fica PENDENTE, como no Pix de verdade. |
| POST | `/pagamentos/{id}/confirmar` | pagar com Pix (2/2) | **Simula o aviso do banco** de que o Pix foi pago. Confirma o pedido no **Serviço de Pedidos** e credita os pontos no **Serviço de Fidelidade**. |
| POST | `/pagamentos/cartao` | pagar com cartão | Valida número (algoritmo de Luhn), bandeira, validade, CVV e parcelas (até 3x), e a operadora simulada aprova ou recusa na hora. Se aprovado, confirma o pedido e credita os pontos. |
| GET | `/pagamentos` | listar pagamentos | Histórico do cliente. Filtros `?usuarioId=`, `?pedidoId=` e `?status=`. |
| GET | `/pagamentos/{id}` | detalhes do pagamento | Conferir o status (ex.: se o Pix já foi confirmado). |
| POST | `/pagamentos/{id}/estornar` | estornar pagamento | Devolve o dinheiro: pede ao **Serviço de Pedidos** para cancelar o pedido, que libera os assentos no **Serviço de Sessões**. Só se a sessão não começou e nenhum ingresso foi usado. |

Exemplos:
```json
POST /pagamentos/pix      { "pedidoId": 1 }
POST /pagamentos/cartao   { "pedidoId": 1, "nomeTitular": "MARIA SOUZA", "numeroCartao": "4111 1111 1111 1111",
                            "validade": "12/28", "cvv": "123", "parcelas": 2 }
```

Cartões de teste: `4111 1111 1111 1111` (Visa) e `5555 5555 5555 4444` (Mastercard) são aprovados; `4000 0000 0000 0002` é **recusado** pela operadora simulada (fica gravado como RECUSADO, com o motivo). Um número que falha no Luhn dá erro 400 e nada é gravado.

### Rotas que **não** foram criadas (e por quê)

- **`DELETE /pedidos/{id}`** e **`DELETE /pagamentos/{id}`**: pedidos e pagamentos são registros de dinheiro e precisam ficar no histórico. Por isso existe **cancelar** e **estornar**, que mudam o status em vez de apagar.
- **`PUT /pedidos/{id}` (trocar assentos ou sessão)**: exigiria liberar e reservar assentos e recalcular o valor de um pedido que pode já estar pago. É mais seguro cancelar e fazer um pedido novo.
- **`PUT /pagamentos/{id}` (alterar valor ou status direto)**: o status só muda pelas regras (confirmar, recusar, estornar), para não existir pagamento "aprovado" sem passar pela autorização.
- **`GET /pedidos` sem `usuarioId`**: nenhuma tela precisa de todos os pedidos de todos os clientes.
- **Webhook real do banco para o Pix**: um Pix de verdade exige contrato com um banco. A rota `/confirmar` faz o papel desse aviso na demonstração.
- **Expirar sozinho um pedido ABERTO e não pago**: precisaria de uma tarefa agendada rodando no servidor (o plano gratuito do Render dorme). O cliente pode cancelar o pedido pela tela, e o Pix expira em 30 minutos.
- **Devolver os pontos de fidelidade no cancelamento/estorno**: o Serviço de Fidelidade não tem rota de estorno de pontos (decisão explicada no `README-amanda.md`). Os pontos usados no desconto e os ganhos na compra continuam como estão.

---

## 4. Integração com os outros serviços da equipe

| Este serviço chama | Rota | Quando |
|---|---|---|
| Pedidos → Usuários (Amanda) | `GET /usuarios/{id}` | realizar pedido (404 = cliente não existe) |
| Pedidos → Sessões (Ana Clara) | `GET /sessoes/{id}` | realizar pedido (preço, filme, horário) |
| Pedidos → Sessões | `POST /sessoes/{id}/reservas` | realizar pedido (409 = assento ocupado) |
| Pedidos → Sessões | `DELETE /sessoes/{id}/reservas/{pedidoId}` | cancelar pedido ou estorno |
| Pedidos → Fidelidade (Amanda) | `POST /fidelidade/{usuarioId}/usar` | desconto com pontos |
| Pagamentos → Pedidos | `GET /pedidos/{id}`, `POST /pedidos/{id}/confirmar-pagamento`, `POST /pedidos/{id}/cancelar` | pagar e estornar |
| Pagamentos → Fidelidade | `POST /fidelidade/{usuarioId}/acumular` | pagamento aprovado (1 ponto por R$ 1,00) |

Se o cliente não participa do programa de fidelidade, o pagamento segue normalmente, só sem pontos. Se um serviço estiver fora do ar, a resposta é **503** com a mensagem "Serviço de X indisponível".

---

## 5. Implantação na nuvem (Render, plano gratuito)

1. Suba o código para o GitHub (seção 6).
2. Em https://render.com → **New → Web Service** → conecte o repositório.
   - **Root Directory:** `pedidos-service`
   - **Language:** Python 3 · **Build Command:** `pip install -r requirements.txt` · **Start Command:** `gunicorn app:app` · **Instance type:** Free
   - Em **Environment**, adicione (links sem `/` no final):
     - `USUARIOS_SERVICE_URL` = link do serviço de usuários
     - `SESSOES_SERVICE_URL` = link do serviço de sessões (`https://cinema-sessoes-pq81.onrender.com`)
     - `FIDELIDADE_SERVICE_URL` = link do serviço de fidelidade
   - Crie o serviço e copie o link (ex.: `https://cinema-pedidos.onrender.com`).
3. Repita para o `pagamentos-service` (Root Directory `pagamentos-service`, mesmos comandos) com:
   - `PEDIDOS_SERVICE_URL` = link do serviço de pedidos
   - `FIDELIDADE_SERVICE_URL` = link do serviço de fidelidade
4. No `frontend/index.html`, troque `https://SEU-pedidos-service.onrender.com` e `https://SEU-pagamentos-service.onrender.com` pelos links reais e faça commit (o frontend publicado atualiza sozinho com o push).
5. Teste: abrir `https://<seu-link>/` deve mostrar `{"servico": "pedidos", "status": "ok", ...}` com os links dos outros serviços.

Observações:
- O plano gratuito "dorme" após 15 min sem uso. Antes de gravar, abra os **seis** links da equipe para acordar todos (o Pedidos depende de três deles).
- No plano gratuito o arquivo SQLite é apagado quando o serviço reinicia. Para dados permanentes seria preciso um disco persistente (pago) ou um banco externo para cada serviço.

---

## 6. Git (obrigatório usar CLI/IDE, **não** enviar arquivos pela interface do GitHub)

A Ana Clara precisa adicionar o Edson como colaborador (Settings → Collaborators). Depois, **no computador do Edson**:

```bash
git config --global user.name  "Edson Terceiro"
git config --global user.email "email-da-conta-github-do-edson"

git clone https://github.com/clarammacedo/cinema-microsservicos.git
cd cinema-microsservicos
# copie para cá as pastas pedidos-service e pagamentos-service e os arquivos frontend/index.html, .gitignore e README-edson.md

git add pedidos-service .gitignore
git commit -m "Cria microsservico de pedidos com banco db_pedidos e integracao com usuarios, sessoes e fidelidade"
git add pagamentos-service
git commit -m "Cria microsservico de pagamentos (Pix e cartao) que consome o servico de pedidos"
git add frontend/index.html
git commit -m "Adiciona telas de pedidos e pagamentos no frontend"
git add README-edson.md
git commit -m "Documenta rotas, execucao e implantacao dos servicos de pedidos e pagamentos"
git push
```

Listagem de commits para o relatório: `git log --author="Edson" --pretty=format:"%h %ad %s" --date=short`.

---

## 7. Roteiro do vídeo (1 a 5 min)

1. **Objetivo** (15 s): sistema de rede de cinemas. Minha parte é Pedidos e Pagamentos, em Python/Flask.
2. **Arquitetura** (30 s): mostrar o diagrama. Cada serviço tem seu banco (`db_pedidos`, `db_pagamentos`). O Pedidos consome Usuários, Sessões e Fidelidade e é provedor do Pagamentos.
3. **Demonstração na nuvem** (2 min 30 s):
   - login → aba Pedidos → escolher 2 assentos (1 meia) e usar alguns pontos → realizar pedido (explicar as 4 chamadas a outros serviços);
   - tentar comprar o mesmo assento de novo (erro 409 vindo do Serviço de Sessões);
   - aba Pagamentos → cartão `4000 0000 0000 0002` (recusado) → cartão `4111 1111 1111 1111` (aprovado, pontos creditados);
   - outro pedido → gerar Pix → confirmar;
   - validar um ingresso na aba Pedidos e tentar validar de novo (já utilizado);
   - estornar um pagamento e mostrar que os assentos voltaram a ficar livres.
4. **Rotas** (1 min): passar pelas tabelas da seção 3 e explicar as rotas que não foram criadas.
5. **Nuvem** (15 s): mostrar os dois serviços no painel do Render.
