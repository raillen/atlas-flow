# Project Atlas Compatibility Matrix

O Atlas Flow pode abrir qualquer diretório real no desktop Linux, mas as
capacidades dependem do modo detectado.

## Host platform

| Platform | Support |
| --- | --- |
| Linux desktop, x86_64 | Supported, built and tested |
| macOS, Windows | Out of scope (owner decision, 2026-08-11) |

## Project modes

| Mode | Como é detectado | Explorar/Discuss | Plan | Run | Review | Adaptar |
| --- | --- | --- | --- | --- | --- | --- |
| `atlas-ready` | manifests válidos, framework 0.1.x | sim | sim | sim, com Git | sim | não necessário |
| `atlas-needs-adaptation` | framework Atlas reconhecido, manifests ausentes/inválidos | sim | não | não | não | preview + apply |
| `external` | sem `PROJECT_MANIFEST.yaml` | sim | não | não | não | preview + apply |
| `atlas-incompatible` | framework ou versão não suportada | sim | não | não | não | migração revisada |

Abrir não implica executar. Plan, Run e Review continuam visíveis na interface,
mas são bloqueados com motivo e ação corretiva quando o projeto não está pronto.

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
