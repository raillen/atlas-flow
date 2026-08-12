# Plan UX

Plan começa com um Goal e termina com um snapshot bloqueado, não com um run
iniciado imediatamente.

## Fluxo

1. Selecionar Goal.
2. Criar snapshot determinístico ou planejado.
3. Revisar DAG, tarefas, dependências, write scope, risco, gates, runner,
   autonomia e routing.
4. Corrigir ou rejeitar o plano enquanto ele está `DRAFT`.
5. Executar `Lock plan`.
6. Executar somente o snapshot `LOCKED`.

A execução registra Goal/revisão, settings e plano consumido. Um snapshot depois
de `LOCKED` é imutável; se o Goal canônico mudar, um novo plano é necessário.

## Inspector de contexto e inteligência

O inspector do Plan mostra a decisão de contexto que foi persistida no snapshot:
perfil, estratégia, modo progressivo, orçamento de entrada/saída, limites de
expansão/delegação e justificativas. Ele não mostra nem simula o payload
recuperado; a decisão precisa permanecer revisável antes da execução.

A rail de contexto também mostra o resumo compacto de Project Intelligence:
quantidade de relatórios e tokens agregados. Custo só é apresentado como
observado quando o contrato fornece uma medição direta; ausência de medição não
é convertida em estimativa visual.

## Projeto externo

Em `external`, `atlas-needs-adaptation` e `atlas-incompatible`, Plan aparece
bloqueado com razão e ação corretiva. A pessoa pode explorar e discutir a
adaptação, mas não criar uma execução que não teria Goals ou gates confiáveis.

## DAG e alternativa textual

O DAG continua sendo uma visualização peer da lista de tarefas. Cada tarefa
expõe objetivo, dependências, escopo, risco, capacidades e gates. A lista é
usável por teclado e leitor de tela; o gráfico não é a única fonte de informação.
