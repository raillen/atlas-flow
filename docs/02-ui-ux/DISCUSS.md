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

## Estado do porte para Avalonia

O estágio Define já possui uma superfície nativa em
src/AtlasFlow.Desktop/ViewModels/DiscussViewModel.cs e na MainWindow: thread
reidratável, estado de completude, composer e rail de decisões. O ViewModel
consome IDiscussionService diretamente e não cria uma segunda API para a UI.

Referências são informadas como caminhos relativos ao projeto e ficam na
mensagem atual até o envio. O ViewModel não acessa o filesystem nem decide se o
caminho é seguro; IDiscussionService.AppendMessageAsync continua responsável
por validar traversal, existência e tipo antes da persistência. Quando esse
serviço não está registrado no runtime C#, a tela mostra a indisponibilidade
explicitamente e mantém o composer inerte.

O picker nativo de arquivos ainda é uma etapa posterior. Esta fatia já fixa o
contrato visual e de estado para arquivos e imagens sem inventar uma validação
paralela ou um upload remoto.

O Decision Rail já projeta as decisões da discussão e mantém a progressão
explícita: a pessoa propõe, seleciona e aceita uma decisão, e só então pode
solicitar a finalização no ledger. Cada ação aguarda a confirmação de
IDiscussionService; erro ou rejeição preserva o formulário para correção.
