# Define UX

Define é o workspace de definição de projeto, não um chat genérico.

A experiência persistida combina:

- Conversation — mensagens reidratadas do backend;
- Decisions — propostas com Accept, Edit, Reject, Defer e impacto de domínio;
- Project Draft — completude de Product, Architecture, UX, Data, Security,
  Quality, Operations, AI/orchestration e Roadmap;
- Open questions, constraints e assumptions;
- Project Atlas adaptation — inspeção, preview, confirmação e revalidação.

Mensagens não executam ações por inferência. Comandos determinísticos continuam
disponíveis como atalho avançado; ações principais aparecem como controles
contextuais.

Finalization mostra readiness, decisões aceitas, gaps e os arquivos que serão
escritos antes de chamar o endpoint. Em projeto externo, Discuss e exploração
são permitidos, mas finalização e Plan/Run/Review ficam bloqueados até a
adaptação autorizada.

A sessão é criada ou retomada por `/api/discussions`; mensagens, decisões e
drafts persistem em SQLite. O WebSocket serve para atualizações ao vivo, não é
a única fonte da conversa.
