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

## Projeto externo

Em `external`, `atlas-needs-adaptation` e `atlas-incompatible`, Plan aparece
bloqueado com razão e ação corretiva. A pessoa pode explorar e discutir a
adaptação, mas não criar uma execução que não teria Goals ou gates confiáveis.

## DAG e alternativa textual

O DAG continua sendo uma visualização peer da lista de tarefas. Cada tarefa
expõe objetivo, dependências, escopo, risco, capacidades e gates. A lista é
usável por teclado e leitor de tela; o gráfico não é a única fonte de informação.
