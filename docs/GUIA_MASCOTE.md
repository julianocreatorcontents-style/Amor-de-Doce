# Guia de uso do mascote KNAZH

Os arquivos abaixo são as ilustrações novas do mascote em PNG com fundo transparente. As referências das páginas foram atualizadas para apontar para eles. Os SVGs antigos foram mantidos como backup e não são mais usados pelos templates.

## Mapa por página / estado

| Página ou contexto | Arquivo | Motivo |
| --- | --- | --- |
| Início / destaque principal | `mascote-feliz-brownie.png` | Mascote apresenta um doce e reforça o cardápio. |
| Sobre a KNAZH | `mascote-feliz-brownie.png` no hero; `mascote-feliz.png` no bloco de boas-vindas | Apresentação da marca com uma pose amigável. |
| Catálogo e categorias | `mascote-feliz-brownie.png` | Mantém o foco nos produtos. |
| Busca e resultados vazios | `mascote-busca.png` | Pose de procura com lupa. |
| Página de produto | `mascote-feliz-brownie.png` | Reforça a chamada para explorar outros doces. |
| FAQ / dúvidas | `mascote-busca.png` no hero; `mascote-feliz.png` no bloco de ajuda | A pose de lupa combina com dúvidas e orientação. |
| Carrinho vazio e carrinho com itens | `mascote-sacola.png` | Relaciona o personagem diretamente ao pedido. |
| Checkout / finalizar pedido | `mascote-feliz.png` | Pose positiva sem competir com o formulário. |
| Confirmação de pedido | `mascote-feliz.png` | Gesto de positivo comunica acolhimento. |
| Minha conta | `mascote-sacola.png` | Mantém a ligação com pedidos e compras. |
| Contato, páginas legais e CTA do rodapé | `mascote-feliz.png` | Pose neutra que funciona em diferentes contextos. |
| Página 404 | `mascote-404.png` | Personagem com placa em branco; o próprio título da página informa o erro 404. |
| Erros 400, 403, 413 e 500 | `mascote-ops.png` | Expressão preocupada para erros e problemas temporários. |

## Arquivos e especificações

- Pasta: `knazh/static/img/mascote/`
- Formato: PNG RGBA, fundo transparente.
- Tela padronizada: 800 × 860 px, proporção compatível com o espaço atual de 400 × 430 px dos templates.
- Paleta visual: chama laranja, contorno carvão, detalhes amarelos e tênis laranja/creme.
- As imagens de marca (logo, favicon, ícones do app) foram preservadas; elas não são o mascote de corpo inteiro.

## Como trocar uma pose depois

Substitua o PNG pelo novo arquivo usando o mesmo nome, mantendo o canvas transparente de 800 × 860 px. Assim, as páginas continuam funcionando sem mudar código. Se decidir renomear um arquivo, atualize também as referências nos templates e em `knazh/__init__.py` para páginas de erro.
