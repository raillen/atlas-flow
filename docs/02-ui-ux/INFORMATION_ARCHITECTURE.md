# Information Architecture

Atlas Flow é um workspace de supervisão de Goals e agentes, não uma IDE nem um
conjunto de páginas isoladas. O contexto atual — projeto, modo, Goal, run e
próxima ação — permanece visível enquanto a pessoa muda de atividade.

## Perguntas que a interface responde

1. **O que precisa da minha atenção?** → bloqueios, recuperação, decisões,
   permissões, reviews e runs ativos.
2. **O que estamos definindo?** → Discuss persistido, decisões, premissas,
   perguntas abertas e Project Draft.
3. **O que será executado?** → Goal, DAG, contexto, risco, escopo, routing,
   autonomia, runner e orçamento.
4. **O que os agentes estão fazendo?** → runs, tasks, tentativas, atividade,
   worktrees, diffs e erros.
5. **Posso chamar isso de concluído?** → critérios, gates, testes e evidências.
6. **Qual é a verdade do projeto?** → documentação canônica, ADRs, Goals e Git.

## Workspace

```text
┌─────────────────────────────────────────────────────────────┐
│ projeto ▾  Attention Define Plan Run Review Knowledge       │
├────────────┬──────────────────────────────┬─────────────────┤
│ Goals      │ Project mode banner          │ Goal/run detail │
│ por fase   │ Attention / Define / Plan     │ gates/evidence  │
│            │ Run / Review / Knowledge      │ selected item   │
├────────────┴──────────────────────────────┴─────────────────┤
│ run atual · progresso · estado do engine · Stop             │
└─────────────────────────────────────────────────────────────┘
```

- **Header:** projeto aberto, modo atual e atividades do workspace.
- **Banner de modo:** explica `external`, `atlas-needs-adaptation` e
  `atlas-incompatible`; oferece adaptação apenas quando ela é segura.
- **Sidebar:** Goals e estado, quando o projeto está Atlas ready.
- **Centro:** uma atividade por vez, em largura total.
- **Inspector:** detalhes do Goal ou item selecionado, sempre no mesmo lugar.
- **Status bar:** run em voo e engine, sempre visíveis.

Em janelas menores, a sidebar recolhe e o inspector vira drawer. Detalhe técnico
é progressive disclosure: aparece sob demanda, não compete com decisão,
progresso e bloqueio.

## Estágios

| Estágio | Responde | Disponibilidade |
| --- | --- | --- |
| Attention | O que precisa de atenção agora? | sempre |
| Define | O que estamos decidindo? | sempre |
| Plan | O que este Goal vai exigir? | Project Atlas válido |
| Run | O que os agentes estão fazendo? | Project Atlas válido + Git |
| Review | Há evidência suficiente para concluir? | Project Atlas válido |
| Knowledge | O que o projeto declara? | sempre; explorer somente leitura também funciona em projeto externo |

`Plan`, `Run` e `Review` não desaparecem em projeto externo: permanecem visíveis,
desabilitados e explicam a condição que falta. Isso ensina o workflow sem
prometer uma execução sem governança.

## Onboarding de projeto externo

1. Abrir diretório.
2. Inspecionar modo, framework, Git e manifests.
3. Explorar arquivos e documentação.
4. Discutir intenção e preparação da adaptação.
5. Revisar preview de arquivos novos e conflitos.
6. Autorizar criação do scaffold.
7. Reinspecionar e liberar o workspace Atlas quando válido.

Nenhuma etapa escreve ou executa algo silenciosamente.
