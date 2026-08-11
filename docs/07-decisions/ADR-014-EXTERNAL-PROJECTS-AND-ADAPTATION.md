# ADR-014 — Abrir projetos externos e adaptar ao Project Atlas

**Status:** Accepted · 2026-08-11

## Contexto

Atlas Flow precisa ser útil no primeiro contato com um projeto existente. Exigir
`PROJECT_MANIFEST.yaml` no diálogo de abertura impede inspeção, recuperação de
contexto e planejamento da adaptação. Ao mesmo tempo, executar Goals sem os
manifestos, policies e gates do Project Atlas criaria uma aparência de
proveniência e verificação que não existe.

## Decisão

O shell aceita qualquer diretório real fora do próprio bundle do aplicativo. O
backend classifica o projeto antes de liberar capacidades:

- `atlas-ready` — manifests válidos, versão suportada;
- `atlas-needs-adaptation` — framework reconhecido, mas manifests ausentes ou
  inválidos;
- `atlas-incompatible` — framework ou versão não suportados;
- `external` — nenhum Project Atlas detectado.

Todos os modos permitem inspeção de arquivos e Discuss persistido. Apenas
`atlas-ready` libera Plan, Run e Review; execução também exige Git para isolar
mudanças em worktrees.

Para `external` e `atlas-needs-adaptation`, Atlas Flow oferece uma recomendação
de adaptação. A adaptação é sempre `preview → confirmação → apply → re-inspeção`.
Ela cria somente arquivos novos do scaffold mínimo, nunca sobrescreve arquivos
existentes, não executa comandos do projeto e não cria Goals `LOCKED` ou `DONE`.
Projetos incompatíveis exigem uma migração revisada, não o scaffold automático.

## Consequências

- O projeto pode ser explorado antes de adotar o framework.
- A interface informa claramente o que está disponível e por que uma etapa está
  bloqueada.
- A verdade canônica continua em Git; `.atlas-flow/` continua operacional.
- A adaptação deixa um diff revisável e não presume decisões de produto,
  critérios de aceitação ou comandos de verificação.
- Projetos sem Git podem ser adaptados e discutidos, mas não executados com
  isolamento até que Git esteja disponível.

## Limites de segurança

A exploração é somente leitura, bloqueia traversal, ignora `.git`,
`.atlas-flow`, dependências e artefatos de build, não abre binários e limita o
conteúdo textual. A aplicação valida novamente os paths do preview e recusa
qualquer overwrite.
