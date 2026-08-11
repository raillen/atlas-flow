# Run UX

Run é um command center de supervisão, não um terminal disfarçado.

## Centro

- fila de runs ativos, bloqueados e históricos;
- progresso por tasks e dependências;
- timeline semântica como visão principal;
- atividade AG-UI ao vivo separada do registro durável.

## Task drawer

Ao selecionar uma tarefa, o drawer mostra objetivo, estado, role, modelo,
provider, runner, worktree, tentativas, arquivos, transcript, permissões,
erros e evidência. Payload técnico e log bruto ficam em detalhes expandidos.

## Ações

- cancel e stop são sempre explícitos;
- retry, repair, escalation e resume explicam seu efeito;
- worktrees de tarefas falhas/canceladas permanecem inspecionáveis;
- nenhuma ação destrutiva descarta output sem confirmação.

Um projeto externo não pode entrar em Run: a UI mostra o bloqueio e direciona
para a adaptação Project Atlas.
