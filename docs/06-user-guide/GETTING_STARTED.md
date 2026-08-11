# Getting Started

## Abrir um projeto

Atlas Flow aceita qualquer diretório existente no desktop Linux. Ao abrir, ele
inspeciona o projeto sem executar comandos e mostra um modo:

- **Project Atlas ready** — Discuss, Plan, Run, Review e Knowledge;
- **External project** — explorar arquivos e documentação, Discuss e preparar
  adaptação;
- **Needs adaptation** — corrigir/completar manifests através de preview;
- **Incompatible framework** — inspeção disponível, mas exige migração revisada.

Projetos externos não são tratados como se tivessem Goals. Plan, Run e Review
permanecem bloqueados até a adaptação autorizada e validada. A adaptação nunca
sobrescreve arquivos nem cria Goals concluídos.

## Adaptação

1. Abra **Review adaptation** no banner do projeto.
2. Examine arquivos novos, conflitos e limitações.
3. Confirme **Create scaffold**.
4. Revise o resultado no Git e continue em Define.

O scaffold cria somente a estrutura mínima do Project Atlas. Decisões, Goals,
critérios de aceitação e comandos de verificação ainda precisam ser definidos e
aceitos explicitamente.

## Executar com Tauri em um mount `noexec`

Se o checkout estiver em um mount com `noexec`, use o alias `atlas-tauri` após
recarregar o Zsh:

```bash
source ~/.zshrc
atlas-tauri
```

O alias chama o CLI Tauri via Node diretamente, usa o backend do checkout por um
caminho absoluto, passa `ATLAS_FLOW_PROJECT_ROOT` para o projeto aberto e move os
artefatos do Cargo e o cache do Vite para `~/.cache`. Isso evita que os wrappers
em `node_modules/.bin` e os diretórios de build sejam executados na unidade
`noexec`.

## Workflow recomendado

1. **Attention** — veja bloqueios, recuperação e próximas ações.
2. **Define** — registre intenção, decisões, perguntas e Project Draft.
3. **Plan** — crie um snapshot, revise DAG/risco/contexto e bloqueie-o.
4. **Run** — supervisione tarefas, tentativas, worktrees e atividade dos agentes.
5. **Review** — relacione critérios, tarefas, testes e evidências.
6. **Knowledge** — consulte a documentação canônica e o histórico.

## Execução

Run exige Project Atlas válido e Git para isolamento por worktree. Um run da UI
sempre nasce de um plano `LOCKED`; o plano fica imutável e é marcado como
`CONSUMED` quando a execução é agendada.

## Validação

```bash
sh scripts/validate_all.sh
```

Consulte `docs/09-references/COMPATIBILITY_MATRIX.md` para os requisitos completos.
