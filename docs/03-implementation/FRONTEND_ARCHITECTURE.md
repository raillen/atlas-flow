---
schema_version: 1
id: DOC-IMPL-FRONTEND-ARCHITECTURE
title: Atlas Flow Frontend Architecture
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
tags: [frontend, avalonia, mvvm, integration]
related: [ADR-018-AVALONIA-DESKTOP, DOC-IMPL-APPLICATION-CONTRACT]
---

# Atlas Flow Frontend Architecture

## Objetivo

Permitir que o frontend Avalonia evolua em paralelo ao núcleo C# sem duplicar
regras de negócio e sem acoplar Views a tipos internos do backend. O limite é
local e in-process, mas continua sendo um contrato arquitetural.

```text
MainWindow / Controls
        │ bindings e commands
        ▼
WorkspaceViewModel
        │ estado de apresentação e intenções
        ▼
IAtlasFlowFrontendGateway ── agrega ── AtlasFlow.Application.Contracts
```

O contrato compartilhado canônico é
[`AtlasFlow.Application.Contracts`](APPLICATION_CONTRACT.md), não o gateway do
Desktop. `AtlasFlow.Application` nunca referencia `AtlasFlow.Desktop`. O
gateway inicial apenas agrega as duas consultas necessárias ao shell e mantém o
fallback de apresentação substituível; ele não redefine tipos do domínio.

## Ownership

O frontend possui:

- Views, controles, estilos, recursos, temas e acessibilidade;
- ViewModels, seleção, expansão e estado efêmero de apresentação;
- gateway de composição do shell e estado efêmero de apresentação;
- o composition root do processo Desktop;
- testes de comportamento, composição headless, contraste e interação.

O frontend não possui:

- regras de Goals, Plans, Runs, review ou autorização;
- acesso direto a SQLite, Git, filesystem, processos ou providers;
- validação canônica de Project Atlas;
- retry, persistência operacional ou ordenação autoritativa de eventos.

## Contrato inicial

`IAtlasFlowFrontendGateway` é uma porta local do shell, não uma segunda API do
produto. `LoadWorkspaceAsync` retorna `WorkspaceSnapshot`, que agrupa
`ProjectInspection` e a lista de `Goal` recebidas dos contratos públicos. Modos,
capabilities, IDs e estados são os mesmos tipos usados pelo núcleo.

`ApplicationAtlasFlowFrontendGateway` já compõe `IProjectService` e
`IGoalService`. Enquanto essas interfaces ainda não têm implementações
registradas, `UnavailableAtlasFlowFrontendGateway` retorna um snapshot seguro e
explícito. Falha de integração não impede renderização, troca de tema ou leitura
do erro.

Ao conectar o backend:

1. registrar as implementações públicas em `AtlasFlowServices.AddAtlasFlow`;
2. chamar `AddAtlasFlow` no composition root com o projeto selecionado;
3. substituir o registro do fallback por
   `ApplicationAtlasFlowFrontendGateway`;
4. manter testes de contrato para agregação, cancelamento e erros;
5. preservar o fallback para design, testes e recuperação.

O gateway não cresce para encapsular os oito serviços. ViewModels de domínio
receberão diretamente `IDiscussionService`, `IPlanService`, `IRunService` e os
demais contratos que realmente usam. Isso mantém dependências pequenas e torna
operações e cancelamento visíveis.

## Comandos e eventos

Mutação entra na aplicação como comando por intenção, por exemplo
`SelectProject`, `SendDiscussionMessage`, `LockPlan` ou `CancelRun`. A UI não
faz mutações otimistas de estado canônico: exibe pending, recebe confirmação e
atualiza sua projeção.

Atualizações contínuas chegam por `IRunService.WatchAsync` e `WatchAllAsync`,
como streams canceláveis de eventos tipados. Transporte e persistência ficam
abaixo de `AtlasFlow.Application`. ViewModels não conhecem sockets, tabelas ou
envelopes de provider. Subscriptions têm ciclo de vida da tela, cancelamento
explícito e sequência monotônica quando o domínio a fornecer.

## Estado de apresentação

- contratos públicos de Application/Domain atravessam a fronteira sem cópia;
- labels, seleção, expansão, loading, empty e error pertencem aos ViewModels;
- capabilities são calculadas pelo núcleo e apenas consumidas pela UI;
- `WorkspaceSnapshot` agrupa resultados, mas não espelha entidades;
- tipos internos de persistência e orquestração não chegam às Views.

Um novo campo de View não justifica um DTO espelho. Primeiro ele é derivado no
ViewModel; se representar informação real ausente no contrato compartilhado, a
mudança é discutida antes de editar `Application/Contracts`.

## Testes e gates

- ViewModels usam gateways e controladores substituíveis, sem runtime real;
- `Avalonia.Headless.XUnit` compõe o XAML e inspeciona automação e frame;
- paletas têm teste automatizado de contraste;
- adapters reais recebem testes de integração separados;
- Release exige build sem warnings e publish NativeAOT do Desktop;
- interação crítica futura requer teste de teclado e regressão visual.

## Estado atual

A fundação implementada contém fallback indisponível, adapter de aplicação
compilado, ViewModel do workspace, tema semântico claro/escuro e App Shell. O
adapter real ainda não está registrado porque os serviços de aplicação não têm
implementações públicas. A UI não afirma integração com Discuss, AG-UI ou
settings; os controles correspondentes permanecem desabilitados.
