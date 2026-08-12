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

`ApplicationAtlasFlowFrontendGateway` já compõe as implementações reais de
`IProjectService` e `IGoalService` registradas em `AddAtlasFlow`. O
`UnavailableAtlasFlowFrontendGateway` permanece somente como fallback explícito
para construção Avalonia, testes e recuperação. Falha de integração não impede
renderização, troca de tema ou leitura do erro.

Ao conectar o backend:

1. registrar as implementações públicas em `AtlasFlowServices.AddAtlasFlow`;
2. chamar `AddAtlasFlow` no composition root com o projeto selecionado;
3. registrar `ApplicationAtlasFlowFrontendGateway` no composition root;
4. manter testes de contrato para agregação, cancelamento e erros;
5. preservar o fallback para design, testes e recuperação.

O primeiro ViewModel de domínio, `PlanViewModel`, recebe `IPlanService`
diretamente. Ele carrega o histórico de snapshots do primeiro Goal, cria um
`DRAFT` e solicita o bloqueio de um plano selecionado. A UI não valida o DAG
nem muda o estado otimisticamente: a aplicação confirma cada transição.

`RunViewModel` recebe `IRunService` e a mesma instância de `PlanViewModel`.
Ele só envia `StartRunRequest` para um plano `LOCKED`, acompanha
`WatchAsync` com replay dos eventos duráveis e delega cancelamento cooperativo
ao serviço. A timeline é uma projeção de `DomainEvent`; ela não interpreta
payloads para fabricar estados locais nem faz polling em timer.

O gateway não cresce para encapsular os oito serviços. ViewModels de domínio
receberão diretamente `IDiscussionService`, `IPlanService`, `IRunService` e os
demais contratos que realmente usam. Isso mantém dependências pequenas e torna
operações e cancelamento visíveis.

DiscussViewModel segue essa regra: recebe IDiscussionService opcionalmente,
carrega a conversa mais recente, projeta mensagens e decisões e envia
AppendMessageRequest com referências relativas. A referência permanece um
valor do contrato; o Desktop não resolve caminhos, lê arquivos, faz upload ou
antecipa a validação canônica do serviço.

Proposta, aceite e finalização seguem o mesmo limite: o ViewModel exibe a
intenção e só atualiza a projeção depois da confirmação de IDiscussionService.

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
real, ViewModels de workspace, Plan e Run, tema semântico claro/escuro e App
Shell. O Define agora tem uma superfície Discuss baseada no contrato público,
com thread, composer e referências de arquivo/imagem aguardando o serviço de
aplicação. O fluxo de Plan já carrega histórico, cria rascunhos e bloqueia
snapshots; o fluxo de Run inicia somente snapshots bloqueados e expõe fila,
progresso, timeline durável e cancelamento cooperativo. A UI ainda não afirma
integração com settings, e Discuss permanece explicitamente indisponível até
que sua implementação seja registrada no composition root.
