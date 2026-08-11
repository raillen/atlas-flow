# Design System

## Princípios

- command center calmo, técnico e legível;
- contexto persistente: projeto, modo, Goal e run não desaparecem;
- progressive disclosure: decisão e bloqueio primeiro, payload técnico depois;
- estado nunca depende apenas de cor;
- teclado e leitor de tela são caminhos primários, não uma adaptação posterior.

## Foundations

- superfícies semânticas: chrome, work surface, card, selected, raised;
- temas escuro e claro com a mesma hierarquia semântica; o escuro é o padrão
  inicial e a preferência fica persistida localmente;
- acento violeta para ação e seleção;
- tons semânticos para positive, negative, waiting, active e neutral;
- escala espacial única e tipografia em `rem`;
- densidade compacta para Run/Review sem alterar significado;
- movimento funcional curto e respeito a `prefers-reduced-motion`.
- tipografia regular e leve: peso forte fica reservado para a ação ou seleção
  atual;
- estados usam ponto discreto mais rótulo curto, nunca pills grandes como
  elemento dominante;
- painéis secundários começam fechados ou podem ser recolhidos sem perder o
  contexto principal;

## Componentes do workspace

- `ProjectSwitcher` — entrada para qualquer diretório real;
- `ProjectModeBanner` — modo, limitações e próxima ação;
- `AttentionStage` — inbox operacional;
- `AdaptationWizard` — preview e apply autorizados;
- `GoalSidebar` e `Inspector` — contexto persistente;
- `TaskGraph` e lista textual — plano peer e acessível;
- `RunStatusBar`, `RunQueue`/cards e task detail — execução visível;
- `ReviewMatrix` — rastreabilidade de criterion a evidence;
- `ProjectExplorer` — leitura segura no modo externo.
- `DiscussScreen` — conversa principal, composer e referências locais;
- `ReferenceChip`/picker — vínculo compacto a arquivos e imagens do projeto.

## Densidade e superfícies

O layout principal privilegia uma única superfície de trabalho. A navegação de
Goals e o painel de detalhes são laterais colapsáveis; o painel de detalhes
começa fechado. `Discuss` mantém o feed e o composer como foco, e a rail de
decisões só aparece quando o usuário solicita contexto.

No shell, somente o estágio ativo exibe seu rótulo. Os demais continuam
acessíveis por teclado, `aria-label` e tooltip, reduzindo ruído visual sem
remover a navegação.

Todos os componentes críticos cobrem loading, empty, error, disabled, focus e
sucesso quando aplicável. A implementação atual mantém tokens centralizados em
`apps/desktop/src/theme.ts`; novas superfícies devem consumir tokens semânticos,
não valores isolados.

## Temas e acessibilidade

Contraste WCAG 2.2 AA, `:focus-visible`, escala por `rem`, live regions e reduced
motion continuam obrigatórios. Os temas escuro e claro usam os mesmos tokens
semânticos e preservam a hierarquia textual e os mesmos sinais não-coloridos.

O botão de tema fica no shell, tem nome acessível e alterna entre `dark` e
`light`. A escolha é salva em `localStorage` pela chave `atlas-flow.theme`; se
o armazenamento não estiver disponível, a sessão continua funcionando com o
tema escuro inicial.
