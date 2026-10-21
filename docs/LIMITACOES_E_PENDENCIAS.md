# Limitações e pendências (registradas com honestidade)

## Não implementado de propósito (dependem de dados/serviços ainda não fornecidos)
- Pagamento online, cálculo de frete, opções de entrega/retirada, horários — não definidos pela KNAZH.
- Integração de pedidos com iFood (há apenas link público configurável) e envio automático de WhatsApp.
- Recuperação de senha por e-mail (exigiria serviço de e-mail; não foi simulada).
- Painel administrativo (será o GabHub). Endereços/notificações da "Minha conta" não existem e por isso não aparecem.
- Opções de produto da referência (escolha de sabor/adicionais) — exigiriam dados reais de catálogo.
- Domínio, e-mail e redes oficiais: configuráveis por `.env`; nada foi inventado.

## Conteúdo provisório (revisar)
- Textos de "Sobre", privacidade e termos são provisórios e marcados na tela. Respostas de FAQ sem dado real aparecem como "Informação pendente".
- Preços, popularidade e imagens dos produtos são de demonstração.
- Fontes de marca originais não foram fornecidas; usadas Fredoka/DM Sans/Caveat (OFL) como aproximação.

## Testes
- Automatizados (pytest): rodam sem rede nem serviços externos. SMTP é testado com simulação; **não** foi testado com servidor real.
- WhatsApp/iFood: testada a geração dos links; **não** foi verificada a abertura nos apps/lojas reais.
- Verificação visual feita em Chromium (Playwright) em 1366 px e 384 px (referência Galaxy A15); **não** foi testado em aparelho físico
  nem com teclado virtual real. Desempenho (Lighthouse etc.) **não** foi medido.
- Limitador de login é em memória, por processo.

## Painel administrativo (primeira versão)
- Só o catálogo de produtos: sem Pedidos, Clientes, Configurações nem gerenciamento de categorias (usa as existentes).
- Uma foto principal por produto (sem galeria). Fotos em `knazh/static/uploads/products/` exigem armazenamento persistente e backup.
- A migração (`migrate-db`) cobre `customers.is_admin` e `customers.can_manage_admins`; mudanças futuras de esquema devem entrar em `knazh/migrations.py`.
- Gerenciar administradores: só dois níveis (administrador do catálogo e gestor de administradores). Não há e-mail de aviso ao conceder/remover acesso,
  nem registro de auditoria (quem alterou o quê), nem verificação de e-mail no cadastro. A proteção contra remover o último gestor foi testada em SQLite;
  em outros bancos ela depende do isolamento da transação (uma instrução condicional única, mas sem teste de concorrência real aqui).
- Produto "indisponível" continua visível no cardápio público (com selo e sem compra); não existe estado "rascunho/não publicado" separado.
- O limitador de login continua por processo (veja README).
