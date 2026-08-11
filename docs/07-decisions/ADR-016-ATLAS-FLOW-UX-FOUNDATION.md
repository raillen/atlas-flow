---
schema_version: 1
id: ADR-016-ATLAS-FLOW-UX-FOUNDATION
title: Fundação de UX do Atlas Flow e adiamento de GTK
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
tags: [ux, frontend, gtk, chat]
---

# ADR-016 — Fundação de UX do Atlas Flow e adiamento de GTK

**Status:** Accepted
**Date:** 2026-08-11

## Decisão

O frontend permanece em Tauri 2 + React + TypeScript. A próxima evolução
prioriza uma interface chat-first, compacta e orientada a contexto, com
referências persistentes a arquivos e imagens do projeto.

GTK4/libadwaita é uma ideia futura, não uma dependência desta fase. Só será
considerado após uma prova de conceito medir o custo real do WebView e provar
paridade de acessibilidade, fluxo, distribuição e manutenção.

## Razões

- a fronteira HTTP/WebSocket/AG-UI já permite trocar o renderer sem duplicar o
  runtime;
- o problema atual é hierarquia, densidade e interação, não prova de que React
  seja o gargalo;
- uma migração nativa agora aumentaria drasticamente o custo e atrasaria o
  fluxo central Discuss → Goal → Run → Review;
- referências são vínculos ao projeto canônico, não uploads implícitos.

## Consequências

A UI passa a usar uma rail de contexto, um feed de conversa real, composer com
referências e tokens visuais semânticos. Os tokens suportam tema claro e
escuro sem duplicar componentes; a preferência é local ao renderer. O contrato
de referência será mantido no backend e coberto por validação de caminho e
persistência.

Após a revisão visual, a rail de contexto e o inspector passaram a ser
superfícies sob demanda. A navegação de Goals pode ser recolhida, o inspector
começa fechado e apenas o estágio ativo mantém texto visível no shell. Isso
reduz carga cognitiva sem remover os caminhos de teclado e os rótulos
acessíveis.

Uma eventual implementação GTK deverá viver atrás dos mesmos contratos e ser
avaliada como spike isolado, sem substituir o frontend atual antes dos gates.
