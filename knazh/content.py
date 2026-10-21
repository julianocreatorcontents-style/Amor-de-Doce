"""Conteúdo editorial editável. Itens com answer=None aparecem como 'informação pendente' (não inventamos políticas)."""
from __future__ import annotations

PENDING_ANSWER = "Esta informação ainda não foi definida pela KNAZH. Fale com a equipe pelos canais de contato."

FAQ_CATEGORIES = [
    ("geral", "Geral", "help"),
    ("pedidos", "Pedidos", "clipboard"),
    ("entrega", "Entrega e retirada", "truck"),
    ("pagamento", "Pagamento", "card"),
    ("conta", "Minha conta", "user"),
]

FAQ_ITEMS = [
    ("geral", "Como posso entrar em contato?",
     "Pela página de Contato (formulário) e pelos canais de WhatsApp e iFood, quando estiverem disponíveis no site."),
    ("geral", "Qual é o horário de funcionamento da KNAZH?", None),
    ("geral", "Os produtos da KNAZH são artesanais?", None),
    ("pedidos", "Como faço para pedir?",
     "Adicione os doces ao carrinho, revise os itens e toque em “Finalizar pedido”. Seu pedido fica registrado no site e, para "
     "confirmar disponibilidade e combinar os detalhes, você segue pelo WhatsApp ou pelo iFood, conforme os canais disponíveis."),
    ("pedidos", "Registrar o pedido no site significa que ele foi confirmado?",
     "Não. O registro mostra o que você escolheu e fica com status “Aguardando confirmação”. A confirmação depende do contato com a equipe KNAZH."),
    ("pedidos", "Posso alterar o carrinho antes de finalizar?",
     "Sim. No carrinho você aumenta ou diminui quantidades e remove itens. Os valores são sempre recalculados pelo site."),
    ("entrega", "Vocês entregam em toda a cidade?", None),
    ("entrega", "Posso retirar meu pedido na loja?", None),
    ("pagamento", "Quais são as formas de pagamento?",
     "O site não processa pagamentos online e não cobra nada. As formas de pagamento disponíveis ainda não foram definidas aqui; confirme com a equipe."),
    ("conta", "Preciso criar uma conta para pedir?",
     "Não. Você pode finalizar como visitante. A conta é opcional e permite acompanhar os pedidos feitos no site e salvar favoritos."),
    ("conta", "Como salvo meus doces favoritos?",
     "Entre na sua conta e toque no coração dos produtos. Eles ficam reunidos em “Favoritos”."),
]

ABOUT_VALUES = [
    ("heart", "Qualidade", "Ingredientes selecionados e muito cuidado em cada preparo."),
    ("star", "Sabor", "Receitas que despertam emoções e tornam cada momento especial."),
    ("users", "Clientes", "Você no centro de tudo o que fazemos."),
    ("leaf", "Respeito", "Trabalhamos com responsabilidade, pensando em um futuro mais doce."),
]

# Textos de política: ESTRUTURA provisória baseada no que o site realmente faz. Revisar com a KNAZH e com profissional jurídico.
PRIVACY_SECTIONS = [
    ("Quais dados o site coleta",
     ["Ao finalizar um pedido: nome, telefone, e-mail (opcional), observações e os itens escolhidos.",
      "Ao criar uma conta: nome, e-mail, telefone e senha (a senha é guardada de forma protegida, nunca em texto aberto).",
      "Pelo formulário de contato: nome, e-mail, assunto e mensagem."]),
    ("Cookies",
     ["O site usa cookies essenciais para manter seu carrinho, sua sessão e a proteção dos formulários. Não usamos cookies de publicidade."]),
    ("Para que usamos os dados",
     ["Registrar pedidos, permitir o acompanhamento na sua conta e responder às suas mensagens."]),
    ("Compartilhamento",
     ["O site não envia seus dados a terceiros. Ao abrir o WhatsApp ou o iFood, você passa a seguir as regras de privacidade desses serviços."]),
    ("Seus direitos e contato do responsável",
     ["Responsável pelo tratamento, canal para solicitações e prazo de guarda dos dados: informações a definir pela KNAZH."]),
]

TERMS_SECTIONS = [
    ("Sobre o site",
     ["Este site apresenta o cardápio da KNAZH e permite montar e registrar pedidos."]),
    ("Pedidos",
     ["Registrar um pedido no site não é cobrança nem confirmação. A confirmação, a disponibilidade e as condições de entrega ou retirada são combinadas com a equipe pelos canais de atendimento.",
      "Valores e disponibilidade exibidos podem mudar; o site recalcula o pedido no momento do registro."]),
    ("Conta do cliente",
     ["A conta é opcional. Você é responsável por manter sua senha em segurança."]),
    ("Conteúdo e marca",
     ["Logotipos, ilustrações e textos da KNAZH pertencem à marca e não podem ser usados sem autorização."]),
    ("Alterações, foro e demais condições",
     ["Regras de troca, cancelamento, foro e outras condições: informações a definir pela KNAZH."]),
]
