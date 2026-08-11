---
schema_version: 1
id: DOC-UX-FOUNDATION
title: Atlas Flow UX Foundation
status: active
version: 1
audience: [developer, maintainer, agent]
visibility: internal
authority: canonical
source: human
owner: atlas-flow-maintainers
last_reviewed: 2026-08-11
review_interval: 180d
risk: medium
tags: [ux, chat, references, progressive-disclosure]
related: [ADR-016-ATLAS-FLOW-UX-FOUNDATION]
---

# Atlas Flow UX Foundation

## Problema

A primeira interface do workspace expunha muitos textos e estados ao mesmo
tempo. `Discuss` parecia uma tela técnica com uma lista de mensagens, enquanto
o chat experimental não participava do fluxo principal. Isso aumentava a carga
cognitiva e enfraquecia a conversa como ponto de entrada do produto.

## Direção

- o workspace é um command center, não um conjunto de telas documentais;
- a conversa é a superfície principal para definir intenção;
- o contexto secundário aparece em uma rail compacta, sem competir com o feed;
- estados e ações usam ícones consistentes, rótulos curtos e estados não
  dependentes apenas de cor;
- detalhes técnicos aparecem por progressive disclosure;
- a tela inicial apresenta uma thread e um composer; Goals, detalhes e decisões
  são superfícies recolhíveis e não aparecem todos ao mesmo tempo;
- peso tipográfico é contido e estados são pontos discretos com rótulos curtos;
- a base visual é compacta e legível, com temas escuro e claro baseados nos
  mesmos tokens semânticos; o escuro é o padrão inicial;
- o frontend é Avalonia 11 sobre .NET 10, sem webview (ADR-018).

## Temas

O shell oferece um botão acessível para alternar entre `dark` e `light`. A
preferência é local à instalação e persistida no arquivo de settings do
usuário; não altera o
contrato do backend nem cria uma configuração de projeto que poderia ser
aplicada involuntariamente a outras pessoas.

## Referência de interação

A análise da interface atual do Codex foi usada como referência de modelo
mental, não de identidade visual. A decisão aproveitada foi thread-first:
projeto e conversas organizam o trabalho, enquanto progresso, diffs e ações de
supervisão aparecem dentro da thread ou sob demanda. Isso orienta o Atlas Flow
a manter uma superfície principal e esconder detalhes operacionais até que a
pessoa os peça.

## Referências de mensagem

Uma mensagem pode carregar referências locais ao projeto:

```json
{
  "path": "docs/ATLAS.md",
  "kind": "file",
  "label": "ATLAS.md",
  "mime_type": null
}
```

`kind` é `file` ou `image`. O backend valida que o caminho existe dentro do
projeto aberto, rejeita traversal e persiste as referências junto da mensagem.
O conteúdo não é enviado automaticamente a nenhum provider; a referência é
um vínculo explícito ao contexto canônico.

## O renderer nativo: o que esta seção previa, e o que aconteceu

Esta seção dizia que GTK4/libadwaita ficava como alternativa futura para um
renderer nativo, **caso medições de RSS, CPU, inicialização e distribuição
mostrassem que Tauri/WebView era o gargalo**, e que a decisão não seria tomada
por preferência ou comparação visual.

A troca aconteceu em 2026-08-11 ([ADR-018](../07-decisions/ADR-018-AVALONIA-DESKTOP.md)).
Registrando com precisão: **as medições não foram feitas.** A decisão partiu de
duas restrições concretas — o app empacotado não subia sem Python instalado no
host, e o webview era a parte mais pesada — e de um julgamento do owner, não de
um número medido contra um orçamento.

Isso não invalida a decisão. Invalida a afirmação de que ela seguiu o critério
que esta seção havia pré-registrado, e a diferença fica escrita aqui em vez de
ser apagada.

Duas correções ao texto original, para quem for auditar depois:

- **O renderer escolhido não foi GTK4.** GTK4 era a resposta certa enquanto
  Linux era a única plataforma. Windows voltou ao escopo e derrubou o GTK4;
  Avalonia ganhou por ser a única opção nativa com acessibilidade real nas duas
  plataformas.
- **Os primeiros números existem, e um deles é pior que o estimado.** Medido em
  2026-08-11 no Linux: binário publicado de 20 MB (estimativa era 40 MB) e
  **114 MB de RSS para uma janela vazia** (estimativa era 80 MB). São de um
  esqueleto sem orquestrador, não do produto, e não substituem os orçamentos do
  `PERFORMANCE_BUDGETS.md` — mas já contradizem uma das duas estimativas, e é
  melhor que isso esteja escrito.

## Fora desta fase

Também ficam adiados upload remoto de arquivos, colaboração em tempo real e
uma cópia visual de Codex ou Antigravity.
