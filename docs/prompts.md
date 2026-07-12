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

## 2. Implementação

### I-001: Implementação do lote do dia 13/07, T-01 a T-06 (Claude Code, 12/07)

```text
# Contexto
Este é o repositório "jogo-limpo-triagem" (github.com/ernestodeoliveira/jogo-limpo-triagem):
protótipo do Jogo Limpo Lab, agente de triagem de risco de jogo baseado no questionário
PGSI (9 itens), construído com LangGraph. O planejamento está concluído: README.md,
docs/PRD.md, docs/ARCHITECTURE.md, docs/DECISIONS.md e docs/PLAN.md são a fonte de
verdade. O docs/PLAN.md contém o backlog ordenado (T-01 a T-24), as decisões Q1 a Q6
registradas na seção 5 (incluindo os impactos da troca do Gemini por modelo local servido
via MLX, decisão Q6) e o Anexo A com o texto literal aprovado dos 9 itens do PGSI
(Moura et al., Rev Saúde Pública, 2026) para data/pgsi.json.
Requisitos inegociáveis: testes sempre executáveis offline e sem chave de API
(TRIAGE_FAKE_LLM=1); nenhum segredo versionado (.env.example só com nomes de variáveis);
Conventional Commits 1.0.0 em inglês; branches curtas integradas via pull request na main;
documentação em PT-BR; código e identificadores em inglês; não usar travessão longo (—)
em nenhum texto gerado.
Stack: Python 3.11, uv, langgraph>=1.2.6, langchain-openai (endpoint local
OpenAI-compatible, conforme Q6), pydantic, pytest.

# Papel
Atue como engenheiro de software sênior especialista em LangGraph e arquitetura de
agentes, executando o backlog do docs/PLAN.md exatamente na ordem planejada. Nesta
sessão você implementa APENAS o lote do dia 13/07 (T-01 a T-06). Não implemente o
grafo, o interrupt() nem qualquer tarefa dos dias seguintes (T-07 em diante).

# Tarefa
Antes de começar: confirme que o PR #1 está mergeado e atualize a main local.
Implemente na ordem, com um commit convencional por tarefa (mensagens sugeridas na
coluna "Commit sugerido" do backlog) e o teste da coluna "Teste" escrito antes ou
junto de cada implementação:
1. T-01 scaffold: pyproject com uv e dependências, pacote src/triagem, tests/,
   extensão do .gitignore (.env e relatórios gerados em reports/), .env.example com
   TRIAGE_FAKE_LLM=, TRIAGE_LLM_BASE_URL= e TRIAGE_LLM_MODEL= (impactos da Q6 no
   PLAN.md §5).
2. T-02 data/pgsi.json: usar o texto LITERAL do Anexo A do PLAN.md (stem, escala e
   9 itens), com a citação completa no próprio arquivo; confirmar a lista de autores
   na página do DOI 10.11606/s1518-8787.2026060007368 antes de gravar.
3. T-03 state.py (TriageState + initial_state, current_question 0..9).
4. T-04 load_pgsi_questions com validação estrita e PGSIDataError.
5. T-05 compute_pgsi_score + ScoreResult (função pura e controlada).
6. T-06 função pura de score para faixa (0 sem_risco; 1-2 baixo; 3-7 moderado;
   8-27 alto).
Rode uv run pytest ao final de cada tarefa; a suíte deve permanecer verde sem .env.
Agrupe o trabalho em dois pull requests: primeiro "chore: scaffold" (T-01) e, após o
merge dele, "feat: data, state and controlled scoring" (T-02 a T-06), cada um em
branch curta criada da main atualizada.
Registre esta sessão em docs/prompts.md como I-001 (prompt e resultado), no padrão
do arquivo.

# Formato
Ao final, imprima: o que foi implementado por tarefa, a saída resumida de
uv run pytest (verde, sem .env), os links dos pull requests criados e qualquer
desvio do planejado com justificativa. Pare antes de qualquer tarefa do dia 14.
```

Complementos enviados durante a execução (decisões via AskUserQuestion e mensagens diretas):

```text
antes de criar cada pull request rode code review e security review com as skills do superpowers
```

```text
outra coisa importante eh que seja realizada auditoria de supply chain
```

**Resultado**: T-01 a T-06 implementados via TDD (teste falho, implementação mínima, teste verde), um commit convencional por tarefa, em dois pull requests mergeados na main:

- **PR #2** "chore: scaffold project with uv and package layout" (T-01): projeto uv em Python 3.11 com `langgraph`, `langchain-openai` e `pydantic` (Q6); pacote `src/triagem`; `.gitignore` estendido; `.env.example` com 4 variáveis (`TRIAGE_FAKE_LLM`, `TRIAGE_LLM_BASE_URL`, `TRIAGE_LLM_MODEL`, `TRIAGE_REPORTS_DIR`, decisão da sessão). Antes do PR: code review (agente `superpowers:code-reviewer`, aprovado sem achados críticos/importantes) e security review (skill `security-review`, sem achados). A auditoria de supply chain (agente dedicado) confirmou origem PyPI com hashes íntegros em todos os 46 pacotes travados e ausência de typosquatting, mas apontou risco Médio de dependências sem teto de versão; corrigido com tetos (`<2`, `<3` etc.) antes de abrir o PR.
- **PR #3** "feat: data, state and controlled scoring" (T-02 a T-06): `data/pgsi.json` com os 9 itens literais do Anexo A e citação completa (lista de 7 autores reconfirmada na página do artigo, incluindo "André Monezi de Andrade" = "Andrade AM"); `TriageState` + `initial_state` (`state.py`); `load_pgsi_questions` com `PGSIDataError` (`tools.py`); `compute_pgsi_score` + `ScoreResult` puros e controlados (`tools.py`); `score_to_band` mapeando score para faixa (`nodes.py`). Antes do PR: nova rodada de code review e security review, sem achados relevantes.

`uv run pytest` verde ao final de cada tarefa e ao final da sessão (38 testes, sem `.env`, sem chave de API).

**Desvios do planejado, com justificativa**:
1. Coluna Teste do T-02 no PLAN.md aponta `test_load_valid_items`, mas esse teste depende do loader do T-04; para manter a suíte verde a cada commit, T-02 ganhou `test_pgsi_data_file_valid` (valida o JSON diretamente) e `test_load_valid_items` foi escrito no T-04 como planejado.
2. `.env.example` recebeu uma 4ª variável (`TRIAGE_REPORTS_DIR`), não listada no prompt original mas já prevista em ARCHITECTURE.md §9 e PLAN.md §2 item 8e; aprovado pelo usuário via AskUserQuestion.
3. Os dois pull requests foram mergeados dentro da própria sessão via `gh pr merge`, decisão do usuário para manter o fluxo contínuo.
4. Adicionado `tests/test_smoke.py` (não pedido explicitamente): necessário porque o pytest retorna código de saída 5 quando não coleta nenhum teste, o que quebraria o critério "suíte verde" do T-01.
5. Código review, security review e auditoria de supply chain (esta última pedida durante a execução) rodados antes de cada PR, com um achado corrigido (tetos de versão no `pyproject.toml`) antes do PR #2.

