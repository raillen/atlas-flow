# Project Atlas Compatibility Matrix

O Atlas Flow pode abrir qualquer diretório real no Windows ou no Linux
desktop, mas as capacidades dependem do modo detectado.

## Host platform

| Platform | Support |
| --- | --- |
| Linux desktop, x86_64 | Supported target. **Not yet built or tested on this branch.** |
| Windows, x86_64 | Supported target since [ADR-018](../07-decisions/ADR-018-AVALONIA-DESKTOP.md). Was a non-goal on P06, P09 and P10 under the owner decision of 2026-08-11; those Goals inherit the work. **Nothing has been tested on Windows.** |
| macOS | Out of scope (owner decision, 2026-08-11, unchanged) |

## Project modes

| Mode | Como é detectado | Explorar/Discuss | Plan | Run | Review | Adaptar |
| --- | --- | --- | --- | --- | --- | --- |
| `atlas-ready` | manifests válidos, framework 0.1.x | sim | sim | sim, com Git | sim | não necessário |
| `atlas-needs-adaptation` | framework Atlas reconhecido, manifests ausentes/inválidos | sim | não | não | não | preview + apply |
| `external` | sem `PROJECT_MANIFEST.yaml` | sim | não | não | não | preview + apply |
| `atlas-incompatible` | framework ou versão não suportada | sim | não | não | não | migração revisada |

Abrir não implica executar. Plan, Run e Review continuam visíveis na interface,
mas são bloqueados com motivo e ação corretiva quando o projeto não está pronto.

### Requisito de runtime

Nenhum. O executável é NativeAOT self-contained. A versão anterior exigia
Python e `uv` na máquina do usuário mesmo em build empacotado.

Git continua obrigatório no `PATH` para isolamento por worktree.

## Framework e manifests

`atlas-ready` exige `project-atlas-framework` versão `0.1.x` e:

- `PROJECT_MANIFEST.yaml`;
- `ENTRYPOINT.md`, `PROJECT_STATE.md`, `docs/ATLAS.md`;
- `.ai/context/project-profile.yaml`;
- `.ai/goals/`;
- manifests de Agents, Skills e Recipes;
- model policy, autonomy policy, orchestrator e fallbacks.

## Adaptação

A adaptação é não destrutiva: mostra arquivos novos e conflitos, cria somente
paths autorizados, não executa comandos, não sobrescreve arquivos e não cria
Goals `LOCKED`/`DONE`. Depois do apply, o projeto é inspecionado novamente.

Projetos sem Git podem ser explorados e adaptados, mas execução por worktree
permanece bloqueada até Git existir.

## Execução segura

A validação definitiva continua em `resolve_project()` e
`validate_compatibility()`. O runtime não usa um formato alternativo de Goal.
Projetos sem Atlas não recebem uma semântica de execução paralela implícita.
