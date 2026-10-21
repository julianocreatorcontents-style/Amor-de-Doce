# Integração futura com o GabHub (NÃO implementada nesta etapa)

O site roda sozinho. Para facilitar a integração depois:

- **Mesma stack** (Flask + SQLAlchemy). O banco é configurável por `DATABASE_URL`.
- **Modelos prontos para administração**: `Category`, `Product` (preço em centavos, `image`, `is_available`, `is_featured`,
  `is_demo`), `Order`/`OrderItem` (status: `pendente`, `confirmado`, `concluido`, `cancelado`; hoje o site só cria `pendente`),
  `ContactMessage`, `Customer`.
- **Fonte única de verdade**: preços/disponibilidade são lidos do banco a cada requisição; basta o GabHub alterar as tabelas.
- **`search_text`** do produto é recalculado automaticamente ao salvar via ORM. Se o GabHub gravar por SQL direto,
  deve atualizar esse campo (texto minúsculo sem acentos de nome + descrição + detalhes + categoria).
- **Imagens**: `Product.image` é um caminho relativo a `/static`. O GabHub precisará de uma pasta de upload e das regras
  de validação (tipo, tamanho) quando for permitir envio de fotos.
- **Passos sugeridos**: (1) decidir banco compartilhado ou API; (2) cadastrar catálogo real e executar `remove-demo`;
  (3) painel de pedidos/mensagens; (4) atualização de status dos pedidos; (5) banners/páginas editáveis (hoje em
  `knazh/content.py` e templates).
