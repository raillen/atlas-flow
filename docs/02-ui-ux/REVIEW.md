# Review UX

Review é uma matriz de confiança que liga intenção a evidência.

## Matriz

Cada acceptance criterion deve relacionar:

- tarefa responsável;
- run e estado;
- diff/arquivos quando disponíveis;
- teste ou comando executado;
- evidência por gate;
- finding e severidade;
- ação seguinte.

Gates e evidências continuam sendo a autoridade para declarar conclusão. Uma
linha sem evidência é `PENDING`, não aprovação implícita.

## Resultados

- **Approve** — todas as condições estão cobertas;
- **Request repair** — reparo direcionado, sem enfraquecer acceptance;
- **Block** — risco, conflito ou gate falho impede integração;
- **Propose Goal amendment** — o contrato precisa mudar explicitamente.

Não existe bypass de gate obrigatório.
