# Context Engine

Goal: smallest sufficient context, not entire repo.

Inputs: Goal/task, ATLAS, knowledge graph, ADR/RFC, files/symbols, diff, tests, Agent/Skill requirements.

Context Pack contains task contract, canonical docs, relevant code/tests, accepted decisions, forbidden scope and validation commands.

Selection: direct links → ATLAS impact edges → search → dependency neighbors within budget → rank/deduplicate → record omissions.

## AF-EVO-001 foundation

`backend/atlas_flow/evolution/context.py` materializa essa regra sem embeddings:
`task maps` e `context packs` entram primeiro; depois uma busca lexical
determinística completa o contexto até o target/max budget. Cada item informa
seu motivo, nível progressivo e tokens estimados. Exclusões são orientação
negativa, não uma proibição que possa esconder uma dependência encontrada pelo
impacto.
