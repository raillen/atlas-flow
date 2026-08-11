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
- o frontend continua em Tauri + React + TypeScript nesta fase.

## Temas

O shell oferece um botão acessível para alternar entre `dark` e `light`. A
preferência é local à instalação e persistida em `localStorage`; não altera o
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

## Fora desta fase

GTK4/libadwaita fica como alternativa futura para um renderer nativo, caso
medições de RSS, CPU, inicialização e distribuição mostrem que Tauri/WebView é
o gargalo. A decisão não será tomada por preferência ou comparação visual.

Também ficam adiados upload remoto de arquivos, colaboração em tempo real e
uma cópia visual de Codex ou Antigravity.
