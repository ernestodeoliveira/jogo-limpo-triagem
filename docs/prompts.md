# docs/prompts.md: registro dos principais prompts

Registro dos prompts mais relevantes usados para **planejar, implementar, corrigir e melhorar** o agente. Atualizado a cada sessão de trabalho, não no final.

Convenção: `P-0xx` planejamento · `S-0xx` prompts de sistema do agente · `I-0xx` implementação e correção.

---

## 1. Planejamento

### P-000: Concepção e plano do projeto (assistente de IA generalista, 12/07)

Resumo dos prompts usados na fase de concepção:

1. Análise dos requisitos do projeto e do repositório de referência `stack-sentinel-senai` (branch `aula6`) para avaliar a adaptação do conceito de chatbot de triagem do Jogo Limpo a um agente LangGraph enxuto e demonstrável.
2. Pedido de decisão fundamentada: partir do repositório de referência ou começar do zero (decisão: do zero; ver `DECISIONS.md` D-01).
3. Geração da documentação de planejamento: README, PRD, ARCHITECTURE, DECISIONS e este arquivo.

### P-001: Prompt inicial para o Claude Code (planejamento, padrão Contexto + Papel + Tarefa + Formato)

```text
# Contexto
Este é o repositório "jogo-limpo-triagem": protótipo do Jogo Limpo Lab, um agente
de triagem de risco de jogo baseado no questionário PGSI (9 itens), construído com
LangGraph. Características centrais: conversa multi-turno com checkpointer e
interrupt(), gate de crise com precedência absoluta, 3 ferramentas (leitura de
data/pgsi.json, função controlada de score, escrita de relatório em reports/) e
modo offline com fakes determinísticos (TRIAGE_FAKE_LLM=1) para rodar sem chave
de API. Marco v0.1 (publicação e congelamento): 19/07/2026.
A documentação de planejamento já existe e é a fonte de verdade:
README.md, docs/PRD.md, docs/ARCHITECTURE.md e docs/DECISIONS.md.
Requisitos inegociáveis do projeto: StateGraph com estado, nós e arestas
condicionais; ferramentas reais integradas ao fluxo; memória e contexto de sessão;
validação de entrada, de ferramenta e de saída; nenhum segredo versionado
(.env.example só com nomes de variáveis); commits semânticos em inglês, em
branches curtas.
Stack: Python 3.11, uv, langgraph>=1.2.6, langchain[google-genai], pydantic,
pytest. Convenções: documentação em PT-BR; código e identificadores em inglês;
não usar travessão longo (—) em nenhum texto gerado.

# Papel
Atue como engenheiro de software sênior especialista em LangGraph e arquitetura de
agentes, no papel de planejador técnico deste repositório. Nesta sessão você NÃO
implementa código de produção e NÃO cria arquivos além do plano pedido.

# Tarefa
1. Leia README.md, docs/PRD.md, docs/ARCHITECTURE.md e docs/DECISIONS.md.
2. Aponte inconsistências, lacunas ou riscos entre esses documentos (se houver).
3. Produza o plano de implementação em tarefas pequenas (máximo ~2h cada), na
   ordem de execução, cobrindo os marcos do PRD §7. Para cada tarefa: arquivos a
   criar ou alterar, teste correspondente, requisito do PRD que ela atende
   (RF-xx/RNF-xx) e mensagem de commit semântica sugerida.
4. Liste os riscos técnicos com plano B (em especial o ciclo com interrupt(),
   decisão A/B do dia 14 conforme ARCHITECTURE §4).
5. Liste as perguntas abertas que exigem decisão humana antes de codar.

# Formato
Crie o arquivo docs/PLAN.md com exatamente estas seções:
1. "Resumo do entendimento" (máximo 10 linhas);
2. "Inconsistências e lacunas encontradas";
3. "Backlog ordenado" (tabela: ID | Tarefa | Arquivos | Teste | Requisito (PRD) |
   Commit sugerido);
4. "Riscos e plano B";
5. "Perguntas abertas".
Ao final, imprima no chat apenas o resumo do entendimento e as perguntas abertas,
e pare aguardando minhas respostas antes de qualquer implementação.
```

**Resultado**: `docs/PLAN.md` criado com as 5 seções; 8 inconsistências apontadas (2 graves: gate de crise fora do caminho de resume e escala "quase sempre" divergente do instrumento); backlog de 24 tarefas nos marcos do PRD §7; 7 riscos com plano B; 6 perguntas abertas.

### P-002: Decisão interativa das perguntas abertas (Claude Code, 12/07)

```text
gere as perguntas de forma interativa com mais detalhes nas opcoes e indicando a
opcao recomendada, ao final registre as opcoes escolhidas
```

Complemento enviado durante a execução:

```text
nao esqueca de sempre realizar conventional commits
https://www.conventionalcommits.org/en/v1.0.0/
```

**Resultado**: as 6 perguntas abertas respondidas e registradas em `docs/PLAN.md` §5, com destaque para: escala validada com sinônimos (Q2), oferta de escolha após 3 inválidas (Q3), checagem de crise em `validate_answer` (Q4), fluxo por pull requests (Q5) e troca do Gemini por modelo local servido via MLX (Q6, com impactos listados). Conventional Commits 1.0.0 declarado explicitamente no PLAN.md §3.

### P-003: Pesquisa da fonte do PGSI em português (Claude Code, 12/07)

```text
pode realizar a pesquisa, o inicio de implementacao sera realizado em outra sessao
```

**Resultado**: fonte encontrada e aprovada: Moura CC et al., "Cross-cultural adaptation and content validity of the PGSI into Brazilian Portuguese", Rev Saúde Pública. 2026;60:e27, DOI 10.11606/s1518-8787.2026060007368. Texto literal dos 9 itens, stem e escala transcritos e verificados em dupla extração do XML JATS; registrados no Anexo A do `docs/PLAN.md`. Aprovação com ajuste de termo: trocar "versão validada" por "versão brasileira com adaptação transcultural e validade de conteúdo" no README §12 e na D-07 (T-21/T-23).

