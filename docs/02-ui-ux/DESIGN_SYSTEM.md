# Atlas Flow Design System

## Direção visual

Atlas Flow é um workspace técnico, premium e silencioso. A interface deve
parecer uma ferramenta de trabalho contínuo, não um dashboard SaaS genérico.
Hierarquia vem de contraste, bordas, espaçamento e tipografia; sombras e
animações são discretas e funcionais.

Princípios:

- uma atividade primária e, no máximo, um contexto secundário visível;
- contexto persistente de projeto, estágio, Goal e conexão;
- progressive disclosure: decisão e bloqueio antes do payload técnico;
- densidade compacta sem sacrificar legibilidade ou alvos de interação;
- estado nunca depende apenas de cor;
- teclado e leitor de tela são caminhos de primeira classe;
- nenhuma ação destrutiva se parece com uma ação comum.

## Foundations

### Cor

Os componentes consomem recursos semânticos definidos em
`src/AtlasFlow.Desktop/Styles/AtlasTheme.axaml`; valores hexadecimais isolados
não entram em Views ou controles.

| Papel | Escuro | Claro |
| --- | --- | --- |
| Background | `#070708` | `#F4F5F2` |
| Surface | `#111114` | `#FFFFFF` |
| Elevated surface | `#18181C` | `#E9EDE8` |
| Border | `#2A2A31` | `#C9CFC7` |
| Primary text | `#F7F7F8` | `#171A18` |
| Secondary text | `#B4B4BA` | `#3F4742` |
| Muted text | `#92929A` | `#59635D` |
| Atlas accent | `#65D6A7` | `#176B50` |

O verde Atlas é reservado para ação primária, seleção, foco e sucesso. Warning,
danger e info têm tons próprios e sempre aparecem com texto ou iconografia.
As duas paletas são auditadas por testes de contraste em
`tests/AtlasFlow.Desktop.Tests/PaletteTests.cs`.

### Tipografia e espaçamento

- Inter é a família principal; monospace fica restrita a IDs, comandos e logs;
- texto-base: 14 px; microcopy: 11 px; section heading: 16 px; heading: 24 px;
- peso forte identifica ação, seleção ou título atual, não parágrafos inteiros;
- a grade espacial é de 4 px;
- raios preferenciais: 6 px em controles, 8 px em elementos compactos e 10 px
  em painéis;
- borda é o mecanismo principal de profundidade.

### Movimento

Transições devem durar de 120 a 180 ms e comunicar mudança de estado. Não há
movimento decorativo contínuo. Toda animação futura precisa respeitar a
preferência de redução de movimento da plataforma.

## Shell

| Região | Regra |
| --- | --- |
| Top bar | 50 px; marca, projeto e estágio à esquerda; ações globais à direita |
| Navegação | 232 px expandida, 64 px compacta |
| Work surface | flexível; contém a única atividade primária |
| Context panel | 384 px; recolhível e nunca canônico |
| Status bar | 30 px; conexão e ambiente sem competir com a tarefa |

Em `Define`, conversa e composer formam a superfície primária. Nos estágios
operacionais, o painel direito pode mostrar contexto, inspector ou conversa,
mas nunca os três ao mesmo tempo.

## Componentes e estados

A primeira fundação inclui `Panel`, `Button`, `TextBox`, navegação de estágios,
tipografia semântica, shell e um command center de Run com fila, timeline e
ações de execução. Cada componente interativo deve cobrir, quando aplicável:
default, hover, pressed, focus-visible, disabled, loading, empty, error e
success.

Componentes de domínio previstos:

- `ProjectSwitcher` e `ProjectModeBanner`;
- `AttentionStage` e `AdaptationWizard`;
- `DiscussScreen`, `ReferencePicker` e `DecisionRail`;
- `GoalSidebar`, `TaskGraph` e `PlanInspector`;
- `RunQueue`, `RunStatusBar` e task detail — a primeira versão está integrada
  ao `RunViewModel`, ainda sem drawer detalhado de tentativa;
- `ReviewMatrix` e `ProjectExplorer`.

Nenhum controle de domínio acessa arquivos, SQLite, Git, processos ou serviços
de aplicação diretamente. Ele recebe estado do ViewModel e emite uma intenção.

## Temas e acessibilidade

O sistema inicia no tema escuro e permite alternância claro/escuro no shell.
Persistência da preferência é responsabilidade futura do
serviço de settings local, sem criar configuração no projeto aberto.

Requisitos mínimos:

- WCAG 2.2 AA para texto e 3:1 para indicadores de foco e componentes;
- foco visível, ordem de tabulação previsível e navegação completa por teclado;
- nome de automação em toda ação cujo conteúdo visual não descreva seu efeito;
- rótulo textual para estados semânticos;
- zoom/escala da plataforma sem corte de conteúdo essencial;
- testes headless de composição e automação antes de cada release.

## Governança

Novos valores entram primeiro como token semântico. Novos componentes precisam
de nome, responsabilidade, estados, comportamento de teclado e evidência de
contraste. Exceções visuais ficam documentadas; copiar valores para resolver uma
tela local não é uma exceção aceita.
