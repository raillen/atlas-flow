# Getting Started

## Requisitos

.NET 10 SDK e Git no `PATH`. No Arch Linux:

```bash
sudo pacman -S dotnet-sdk
```

Não há mais nada para instalar. A versão anterior exigia Python e `uv` na
máquina do usuário mesmo em build empacotado; esta não exige.

## Executar

```bash
dotnet run --project src/AtlasFlow.Desktop
```

Um processo, uma janela. Não existe backend para subir em outro terminal nem
porta local para abrir.

## Abrir um projeto

Atlas Flow aceita qualquer diretório existente no Windows ou no Linux desktop.
Ao abrir, ele inspeciona o projeto sem executar comandos e mostra um modo:

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

## Checkout em um mount `noexec`

O build .NET não executa binários a partir do diretório de saída durante a
compilação, então o problema que exigia o alias `atlas-tauri` não existe mais.

O que ainda importa: o pacote NuGet global fica em `~/.nuget/packages`. Se o
`HOME` estiver em um mount `noexec`, aponte-o para outro lugar:

```bash
export NUGET_PACKAGES=/caminho/executavel/nuget
```

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

## Estado desta branch

O porte para C# é um esqueleto. A estrutura da solução e a documentação estão
prontas; a lógica de orquestração ainda não foi portada, e nada aqui foi
compilado. Os comandos acima descrevem o destino, não o que roda hoje.

A implementação Python de onde o porte é lido está em `reference/`.
