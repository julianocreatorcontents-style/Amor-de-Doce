# KNAZH — Site público

Site da marca **KNAZH** (doces e sobremesas): cardápio, categorias, busca, detalhes de produto, carrinho, pedido,
conta de cliente, páginas institucionais, contato, dúvidas, privacidade/termos e estados de erro.
Feito com **Python + Flask + Jinja + SQLAlchemy (SQLite)**, CSS e JavaScript simples (sem build, sem CDN).

> Projeto **independente do GabHub** nesta etapa. A integração futura está descrita em
> [`docs/INTEGRACAO_GABHUB.md`](docs/INTEGRACAO_GABHUB.md) e **não** é necessária para rodar o site.

## Requisitos
- Python 3.10 ou superior (testado com 3.12)

## Instalação (Windows PowerShell / macOS / Linux)

```bash
# 1) ambiente virtual
python -m venv .venv
#   Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate

# 2) dependências
pip install -r requirements.txt

# 3) configuração (copie e edite)
cp .env.example .env        # Windows: copy .env.example .env

# 4) banco de dados (cria as tabelas; NÃO apaga nada) e catálogo de DEMONSTRAÇÃO
python -m flask --app wsgi init-db
python -m flask --app wsgi seed-demo

# 5) rodar
python -m flask --app wsgi run
#   abra http://127.0.0.1:5000
```

Em desenvolvimento a chave secreta é gerada automaticamente em `instance/.dev_secret_key`.
**Em produção** defina `KNAZH_ENV=production` e `SECRET_KEY` (o app se recusa a iniciar sem ela).
Produção: `gunicorn wsgi:app` atrás de HTTPS (cookies seguros são ativados automaticamente).

## Testes
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
Cobrem: inicialização/banco, páginas e links, catálogo/categorias/busca/filtros/ordenação/paginação, carrinho,
recálculo no servidor, checkout, persistência e idempotência de pedidos, CSRF, contas e isolamento de dados,
contato (inclusive falha de SMTP), canais não configurados, cabeçalhos de segurança e páginas de erro.
Veja as limitações em [`docs/LIMITACOES_E_PENDENCIAS.md`](docs/LIMITACOES_E_PENDENCIAS.md).

## Comandos úteis
| Comando | O que faz |
|---|---|
| `python -m flask --app wsgi init-db` | cria tabelas ausentes (não destrutivo) |
| `python -m flask --app wsgi migrate-db` | atualiza um banco **já existente** (idempotente; veja “Painel administrativo”) |
| `python -m flask --app wsgi provision-initial-admin` | cria/promove o administrador inicial (veja “Gerenciar administradores”) |
| `python -m flask --app wsgi promote-admin EMAIL [--manager]` | concede acesso de administrador (e, com `--manager`, a permissão de gerenciar administradores) a uma conta existente |
| `python -m flask --app wsgi revoke-admin EMAIL` | remove o acesso de administrador (recusa remover o último gestor) |
| `python -m flask --app wsgi seed-demo` | carrega/atualiza o catálogo **de demonstração** (idempotente) |
| `python -m flask --app wsgi remove-demo` | remove só os produtos marcados como demonstração |
| `python -m flask --app wsgi list-orders` | lista pedidos registrados |
| `python -m flask --app wsgi list-messages` | lista mensagens do formulário de contato |

## Dados reais x demonstração (LEIA ANTES DE PUBLICAR)
- Nomes e descrições dos produtos de demonstração seguem as telas de referência; **preços, popularidade e
  disponibilidade são fictícios** (`knazh/demo_data.py`). As imagens são **ilustrações demonstrativas**, não fotos aprovadas.
- O site **não** exibe mais a faixa de "catálogo de demonstração" (a faixa, o estilo e a variável `SHOW_DEMO_NOTICE` foram removidos).
  Os produtos de demonstração continuam sendo só dados: troque-os pelo catálogo real e rode `remove-demo`.
- Para publicar: cadastre o catálogo real (futuramente pelo GabHub), depois `remove-demo`.
- As telas de referência exibem um número de WhatsApp. **Ele não foi copiado para o código**: confirme o número
  oficial e informe em `WHATSAPP_NUMBER`.

## Configurar WhatsApp, iFood e redes (`.env`)
| Variável | Efeito |
|---|---|
| `WHATSAPP_NUMBER` | ex.: `41999999999`. Ativa botões "Pedir pelo WhatsApp" (link `wa.me` com mensagem pronta do carrinho/pedido). |
| `IFOOD_STORE_URL` | URL **https** pública da loja. É só um **link** — não há integração de pedidos com o iFood. |
| `INSTAGRAM_URL`, `TIKTOK_URL`, `FACEBOOK_URL`, `YOUTUBE_URL` | ícones no rodapé (https). |
| `PUBLIC_CONTACT_EMAIL` | e-mail exibido em Contato. |
| `SITE_URL` | domínio real (sem barra final): canonical, sitemap, robots, Open Graph. |

Canal sem configuração fica **oculto** (ou aparece como "Canal ainda não disponível" em Contato). Abrir o WhatsApp
só **prepara** a mensagem; não garante envio nem confirmação.

## Como funciona o pedido (sem pagamento online)
1. Carrinho em sessão guarda só `id → quantidade`. **Preços, nomes e disponibilidade vêm sempre do banco.**
2. `Finalizar pedido` valida os dados (servidor + navegador), refaz os cálculos e grava `Order` + `OrderItem` (snapshot de nome e preço).
3. O pedido nasce **"Aguardando confirmação"**. O site **não cobra** e **não confirma**: o cliente conclui pelo WhatsApp/iFood.
4. Reenvio do formulário não duplica pedidos (token de envio único). Entrega: "a combinar" (regras ainda não definidas).
5. Visitante vê o pedido na sessão em que o criou; cliente logado vê **somente os próprios** pedidos.

## Contato
Mensagens **sempre** são gravadas no banco (`list-messages`). Envio por e-mail é opcional: preencha
`CONTACT_EMAIL_TO`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`. Sem SMTP, nada é enviado
por e-mail e o site não diz que foi.

## Painel administrativo (catálogo de produtos)

Área restrita em **`/admin/produtos`** para listar, buscar, filtrar, cadastrar, editar, trocar a foto, alterar a
disponibilidade e excluir produtos. Só contas com `is_admin = true` entram; **não existe cadastro público de
administrador** e nenhuma senha padrão. A permissão é verificada **no servidor** a cada requisição (a conta é relida
do banco): visitante é enviado para `/conta/entrar`, cliente comum recebe 403.

### Primeira vez em um banco que já existe (ordem importa)
```bash
# 0) pare o site e FAÇA BACKUP do banco (e da pasta de fotos, se já existir)
cp instance/knazh.db instance/knazh.db.bak-$(date +%Y%m%d)      # Windows: copie o arquivo manualmente

# 1) instale a nova dependência (Pillow, usada para validar as fotos)
python -m pip install -r requirements.txt

# 2) migre o banco: adiciona a coluna customers.is_admin (padrão false) sem apagar nada. Pode rodar mais de uma vez.
python -m flask --app wsgi migrate-db

# 3) a pessoa cria a conta normalmente em /conta/cadastrar; depois promova-a pelo e-mail:
python -m flask --app wsgi promote-admin email@exemplo.com

# 4) inicie o site e acesse /admin/produtos (ou use o ícone/atalho “Painel administrativo” após entrar)
python -m flask --app wsgi run
```
**Não inicie a versão nova sem rodar o passo 2** em um banco antigo: o site lê `customers.is_admin` e falharia.
Em um banco novo, `init-db` já cria tudo e o passo 2 não é necessário. Para remover o acesso: `revoke-admin EMAIL`.

### Como funciona
- **Preço:** digitado em reais (`18,50`), convertido e validado em centavos inteiros no servidor (positivo, até R$ 100.000,00).
- **Imagem:** cada produto tem **uma** foto principal. Na edição, sem arquivo novo a foto atual é mantida. No cadastro a foto é obrigatória.
- **Slug:** produtos novos recebem um slug único gerado do nome; na edição o slug **não muda** (as URLs públicas continuam valendo).
- **Excluir:** só por `POST` com CSRF, depois de uma confirmação (diálogo; sem JavaScript, uma tela de confirmação). Pedidos antigos
  mantêm nome e preço (snapshot); só o vínculo `product_id` do item é anulado. Favoritos do produto são removidos.
  Se a exclusão falhar, aparece uma mensagem segura sugerindo marcar o produto como indisponível.
- **Produtos de demonstração:** ao salvar/alterar um produto pelo painel ele deixa de ser “demo”, para `seed-demo` não sobrescrevê-lo
  e `remove-demo` não apagá-lo.
- O painel não tem Pedidos/Configurações nem galeria de várias fotos: ficam para uma próxima etapa. A seção “Administradores” lista as contas só para gerenciar acesso.

### Upload de fotos — limites e cuidados
- Aceita **JPEG, PNG e WebP reais** (conteúdo aberto e verificado com Pillow; SVG, GIF, extensão/MIME falsos e arquivos corrompidos são recusados).
- Máximo **5 MiB por arquivo** (`UPLOAD_MAX_FILE_MB`) e **25 megapixels** (protege contra decompression bombs). A requisição do painel
  aceita esse valor + 512 KiB; o site público continua com limite de 64 KiB.
- A imagem é **reprocessada**: orientação aplicada, EXIF/GPS/perfis removidos, reduzida a no máximo 1600 px e salva como JPEG
  (ou PNG, se tiver transparência). O nome é **UUID gerado no servidor**; o nome enviado nunca vira caminho.
- Arquivos ficam em `knazh/static/uploads/products/` e `Product.image` guarda `uploads/products/<uuid>.jpg` (compatível com `url_for('static', ...)`).
- Se o banco falhar ao salvar, a foto nova é removida e a antiga permanece. Ao trocar/excluir, a foto antiga só é apagada **depois** do commit e **somente**
  se for um arquivo gerado pelo painel — as ilustrações originais do projeto nunca são tocadas.
- **Produção:** monte `knazh/static/uploads/products/` em **armazenamento persistente** e inclua-o no **backup** junto com o banco. Em
  plataformas com disco efêmero (ou contêineres sem volume) as fotos enviadas se perdem a cada deploy. Se houver proxy (nginx etc.), libere
  `client_max_body_size` ≥ 6 MiB para `/admin/`.

## Gerenciar administradores (painel → “Administradores”)

Seção em **`/admin/administradores`**, só para contas com `is_admin` **e** `can_manage_admins` ("gestores"). Lista as contas,
mostra quem tem acesso (Cliente / Administrador / Gerencia administradores), busca por nome/e-mail, filtra por tipo e permite
**conceder** ou **remover** o acesso, sempre com confirmação (diálogo; sem JavaScript, uma tela de confirmação) e mensagem de sucesso/erro.

Regras aplicadas **no servidor** (nada vem do navegador; o papel é relido do banco a cada requisição, então a revogação vale na hora):
- visitante → login; cliente comum → 403; **administrador sem a permissão de gestão → 403** (rotas `user_*` têm guarda em `before_request`, no decorador e no serviço);
- POST com CSRF; a concessão só aceita `is_admin`/`can_manage_admins` vindos da própria ação (formulários públicos/perfil ignoram esses campos);
- **ninguém altera o próprio acesso** pelo painel; quem perde acesso perde também a permissão de gestão;
- o **último gestor nunca é removido**: a remoção é um único `UPDATE` condicional (conta os gestores e confere que quem age ainda é gestor
  dentro da própria instrução, então remoções simultâneas não zeram os gestores). Recuperação (precisa de acesso ao servidor):
  `flask --app wsgi promote-admin EMAIL --manager`;
- conceder dá acesso ao catálogo; a permissão de gerenciar administradores é uma caixa à parte, desmarcada por padrão.

### Administrador inicial (gaabprc@gmail.com)
```bash
# 1) backup do banco; depois atualize o esquema (adiciona customers.can_manage_admins; administradores já existentes viram gestores)
python -m flask --app wsgi migrate-db

# 2) defina a senha SÓ no ambiente (nada no código/repositório) e provisione
export INITIAL_ADMIN_PASSWORD='uma-senha-forte-com-letras-e-numeros'     # PowerShell: $env:INITIAL_ADMIN_PASSWORD='...'
python -m flask --app wsgi provision-initial-admin                        # e-mail padrão: INITIAL_ADMIN_EMAIL (gaabprc@gmail.com)
unset INITIAL_ADMIN_PASSWORD                                              # e remova-a do ambiente/.env depois
```
- Se a conta **já existe**, o comando mostra a situação (data de criação e nome), **não altera senha nem dados** e pede confirmação antes de promovê-la
  (`--yes` dispensa o prompt). Se já é gestora, não faz nada. Nunca cria duplicatas (e-mail é único).
- Sem `INITIAL_ADMIN_PASSWORD` e sem terminal, o comando falha; num terminal, pede a senha oculta. A senha precisa ter 8+ caracteres com letras e números e nunca é exibida.
- O cadastro público **recusa o e-mail do administrador inicial**, para ninguém registrá-lo antes e ficar com a conta; ele só nasce pelo comando acima.
- O site (`/conta/entrar`) é o login: depois de entrar, aparece a **engrenagem** laranja no cabeçalho (acesso ao painel).

## Estrutura
```
wsgi.py                  ponto de entrada
knazh/__init__.py        fábrica da app, cabeçalhos de segurança, erros
knazh/config.py          configuração (variáveis de ambiente)
knazh/models.py          Category, Product, Customer (is_admin, can_manage_admins), Favorite, Order, OrderItem, ContactMessage
knazh/services/          catálogo, carrinho, pedidos, canais, e-mail, dinheiro, segurança, admin_catalog, admin_users, uploads
knazh/migrations.py      migrações explícitas e idempotentes (migrate-db)
knazh/blueprints/        rotas: main, catalog, cart, checkout, account, admin (painel)
knazh/templates/         Jinja (components/ = macros e ícones)
knazh/static/            css (tokens/base/components/pages/admin), js, fonts (OFL), img, uploads/products (fotos do painel)
knazh/demo_data.py       catálogo de DEMONSTRAÇÃO (separado)
tools/make_art.py        gera mascote/produtos demo (SVG) — opcional
tests/                   pytest
docs/                    integração GabHub, mascote, limitações
```

## Segurança (resumo)
CSRF em todos os formulários · senhas com hash (Werkzeug) · limite de tentativas de login · sessão renovada no login ·
validação no servidor · ORM com consultas parametrizadas · escape automático do Jinja · redirecionamentos validados ·
CSP restritiva sem scripts/estilos inline · upload de fotos só no painel admin (validado com Pillow) · papel admin checado no servidor · erros sem detalhes internos · segredos só em variáveis de ambiente.
**Antes de produção:** `SECRET_KEY` forte, HTTPS, banco com backup, revisar textos legais, considerar limitação de taxa
em proxy/WAF (o limitador de login é por processo).

## Licenças de fontes
Fredoka, DM Sans e Caveat (SIL OFL 1.1) — arquivos locais em `knazh/static/fonts/` com as licenças.
