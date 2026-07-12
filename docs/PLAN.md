# PLAN: plano de implementação do agente de triagem PGSI

Gerado a partir de README.md, docs/PRD.md, docs/ARCHITECTURE.md e docs/DECISIONS.md. Backlog ordenado pelos marcos do PRD §7 (12/07 a 19/07). Tarefas de no máximo ~2h.

## 1. Resumo do entendimento

Protótipo educacional de triagem de risco de jogo (Jogo Limpo Lab): agente conversacional em LangGraph, CLI multi-turno em PT-BR, sem claim clínico.
Fluxo: `safety_gate` com precedência absoluta, `classify_intent` com saída estruturada, ciclo de 9 itens PGSI com `interrupt()`/`Command(resume=...)`, checkpointer `InMemorySaver` e `thread_id` por sessão.
Score vem só da função controlada `compute_pgsi_score`; faixa por regra fixa (0; 1-2; 3-7; 8-27); relatório .md e .json em `reports/` sem sobrescrever; nenhum número da saída vem de LLM.
Validação em três pontos: entrada (parser determinístico e fallback LLM restrito a `Literal[0,1,2,3] | None`), insumos de ferramenta e saída final com disclaimer e encaminhamentos fixos (Autoexclusão gov.br, CVV 188, CAPS/SUS).
Modo offline com fakes determinísticos (`TRIAGE_FAKE_LLM=1`) é o caminho principal de demo e testes; Gemini real só para gravar exemplos.
Stack: Python 3.11, uv, langgraph>=1.2.6, langchain[google-genai], pydantic, pytest. Sem segredos versionados; commits semânticos em inglês em branches curtas; docs em PT-BR, código em inglês.
Marco v0.1 em 19/07/2026 com os aceites 1-6 do PRD §6; marcos diários do PRD §7 ordenam o backlog.
Riscos principais: estabilidade do ciclo com `interrupt()` (decisão A/B no dia 14) e cobertura do gate de crise nas respostas retomadas.

## 2. Inconsistências e lacunas encontradas

1. **(Grave) Crise no meio do questionário vs opção A.** RF-01 diz "toda entrada passa primeiro por `safety_gate`" e o aceite 3 exige crise detectada no meio do questionário. Mas na opção A (ARCHITECTURE §4) as respostas retomam via `Command(resume=...)` direto em `validate_answer`, sem passar por `safety_gate` (que só existe na aresta a partir de START). É preciso rodar a checagem de crise também no caminho de resume (proposta: dentro de `validate_answer`, antes do parser). Ver pergunta aberta Q4.
2. **(Grave) Escala do PGSI vs tabela de parsing.** ARCHITECTURE §5 mapeia "quase sempre" para 2 e "sempre" para 3. Na versão validada do PGSI a escala de resposta é 0 nunca, 1 às vezes, 2 na maioria das vezes, 3 quase sempre. Como D-07 proíbe paráfrase do instrumento, a tabela precisa ser corrigida (ou a escala confirmada) antes de codar `parsing.py` e `data/pgsi.json`. Ver Q2.
3. **(Média) Comportamento após 3 tentativas inválidas.** PRD RF-05 e aceite 2 falam em "oferta de encerrar" (sugere escolha do usuário); ARCHITECTURE define `abort_node` que encerra direto. Ver Q3.
4. **(Média) Intenção "responder" morta na opção A.** Com `interrupt()`, as respostas do questionário nunca passam por `classify_intent`; "responder" só é usada na primeira mensagem ou no plano B. Documentar para não implementar rota morta e manter o rótulo por compatibilidade com o plano B.
5. **(Baixa) Diagrama do README omite o abort.** O fluxo do README §4 não mostra `abort_node`/limite de 3 tentativas, presente na ARCHITECTURE §3 e no RF-05. Atualizar o README quando o grafo estiver fechado (tarefa T-21).
6. **(Baixa) Semântica de `current_question`.** Comentado como "0..8 (índice do próximo item)", mas a condição de saída usa `current_question == 9`. O intervalo real é 0..9, com 9 significando questionário completo. Corrigir o comentário no código.
7. **(Baixa) Contrato do fallback LLM divergente.** RNF-03 restringe a `Literal[0,1,2,3]`; ARCHITECTURE §5 usa `Literal[0,1,2,3] | None` (None = não interpretável, conta tentativa). Adotar a versão com None; anotar o alinhamento no PRD na revisão final.
8. **(Baixa) Lacunas operacionais.** (a) Repositório ainda sem `git init` e sem remote, mas o PRD exige histórico de commits: é o primeiro passo do backlog. (b) README §6 com URL placeholder `<SEU_USUARIO>`. (c) Reset de `attempts` não especificado: zerar a cada resposta válida e a cada novo item. (d) Modelo `Question` citado na ARCHITECTURE §6 mas não definido: definir Pydantic em `tools.py`. (e) RNF-01 diz `.env.example` apenas com `GOOGLE_API_KEY=`, mas ARCHITECTURE §9 define também `TRIAGE_FAKE_LLM` e `TRIAGE_REPORTS_DIR`: incluir os três nomes, sem valores. (f) `reports/` precisa de regra no `.gitignore` que ignore relatórios gerados mas versione 1 exemplo (README §13).

## 3. Backlog ordenado

Todos os commits seguem [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/), em inglês, um commit por tarefa concluída (mais commits intermediários quando fizer sentido), sempre em branch curta integrada via pull request (decisão Q5).

### Dia 13/07: scaffold, estado, dados e score

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-01 | `git init` + scaffold: pyproject (uv; langgraph, langchain[google-genai], pydantic, pytest), pacote `src/triagem`, `tests/`, `.gitignore` (.env, reports gerados), `.env.example` com os 3 nomes de variáveis | `pyproject.toml`, `.gitignore`, `.env.example`, `src/triagem/__init__.py`, `tests/__init__.py` | smoke: `uv sync` e `uv run pytest` coletam sem erro | RNF-01, §3 | `chore: scaffold project with uv and package layout` |
| T-02 | Criar `data/pgsi.json`: 9 itens validados em PT-BR, escala e fonte citada no próprio arquivo (bloqueado por Q1/Q2) | `data/pgsi.json` | `test_tools.py::test_load_valid_items` | RF-03, D-07 | `feat(data): add PGSI items with attribution and scale` |
| T-03 | `state.py`: `TriageState` + `initial_state()` (com `current_question` 0..9 documentado) | `src/triagem/state.py` | `tests/test_state.py`: defaults e merge do reducer de `answers` | RF-06 | `feat(state): add TriageState with answers reducer` |
| T-04 | `tools.py`: modelo `Question`, `load_pgsi_questions` com validação estrita e `PGSIDataError` | `src/triagem/tools.py` | `tests/test_tools.py`: ok, item faltando, texto vazio, JSON inválido | RF-03, RF-07 | `feat(tools): add load_pgsi_questions with strict validation` |
| T-05 | `tools.py`: `compute_pgsi_score` + `ScoreResult` (exige q1..q9, int 0-3, puro) | `src/triagem/tools.py` | `tests/test_score.py`: bordas 0, 1, 2, 3, 7, 8, 27; chave faltando; valor fora de 0-3 | RF-07 | `feat(tools): add compute_pgsi_score controlled function` |
| T-06 | Função pura score para faixa (0 sem_risco; 1-2 baixo; 3-7 moderado; 8-27 alto) | `src/triagem/nodes.py` | `tests/test_score.py::test_severity_bands` | RF-08 | `feat(scoring): map score to severity band` |

### Dia 14/07: grafo core e ciclo com interrupt (decisão A/B)

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-07 | Spike de `interrupt()`/`Command(resume=...)`: grafo mínimo com `InMemorySaver`, validar formato de `__interrupt__`, 2 ciclos de pausa e retomada; timebox 2h; registrar decisão A/B em DECISIONS.md | `tests/test_interrupt_spike.py`, `docs/DECISIONS.md` | o próprio spike (pausa, resume, ciclo repetido) | RF-04, §8 | `test(graph): add interrupt resume spike and record decision` |
| T-08 | `graph.py`: `build_agent(llm)` com `safety_gate` stub, `ask_question` (idempotente, só monta payload e chama `interrupt()`), `validate_answer` aceitando apenas dígitos nesta fase, arestas condicionais do ciclo, compile com checkpointer | `src/triagem/graph.py`, `src/triagem/nodes.py` | `tests/test_graph_e2e.py::test_happy_path_digits`: 9 resumes com "0".."3" chegam ao fim do ciclo | RF-03, RF-04, RF-06 | `feat(graph): add questionnaire cycle with interrupt and checkpointer` |
| T-09 | `fakes.py`: `FakeClassifier` e `FakeAnswerParser` (mesma interface `with_structured_output`/`invoke`) + factory `get_llm()` que respeita `TRIAGE_FAKE_LLM` | `src/triagem/fakes.py`, `src/triagem/graph.py`, `tests/conftest.py` | fixture nos testes; suíte roda sem chave | RNF-02, RNF-04 | `feat(fakes): add deterministic fakes for offline mode` |
| T-10 | `classify.py`: `IntentResult` (Pydantic, Literal) + `classify_intent_node` + rotas `fora_dominio` para fallback e `duvida` para `info_node` | `src/triagem/classify.py`, `src/triagem/nodes.py`, `src/triagem/graph.py` | `tests/test_routing.py`: cada intenção chega ao nó certo | RF-02 | `feat(classify): route intents with structured output` |

### Dia 15/07: parser, validação e gate de crise

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-11 | `parsing.py`: normalização (lower, strip, sem acento) + tabela determinística corrigida conforme Q2 + regra de ambiguidade | `src/triagem/parsing.py` | `tests/test_parsing.py`: tabela completa, ambíguos, injeção tratada como inválida | RF-05, RNF-03 | `feat(parsing): add deterministic answer parser` |
| T-12 | `parsing.py`: fallback LLM `with_structured_output` restrito a `Literal[0,1,2,3] \| None` + fake correspondente | `src/triagem/parsing.py`, `src/triagem/fakes.py` | `tests/test_parsing.py::test_llm_fallback` com fake | RF-05, RNF-03 | `feat(parsing): add constrained llm fallback` |
| T-13 | `validate_answer` completo: parser, `attempts` (zera em resposta válida e em novo item), re-pergunta com dica, `abort_node` após 3 (comportamento conforme Q3) | `src/triagem/nodes.py`, `src/triagem/graph.py` | `tests/test_graph_e2e.py::test_retry_and_abort` | RF-05, aceite 2 | `feat(graph): enforce retry limit with graceful abort` |
| T-14 | `safety.py`: heurística de termos + `safety_gate_node` + `crisis_node` (CVV 188, SAMU 192) + checagem de crise nas respostas retomadas dentro do ciclo (conforme Q4) | `src/triagem/safety.py`, `src/triagem/nodes.py`, `src/triagem/graph.py` | `tests/test_safety.py` + `tests/test_graph_e2e.py::test_crisis_mid_questionnaire` | RF-01, aceite 3 | `feat(safety): add crisis gate with absolute precedence` |

### Dia 16/07: relatório, saída final e CLI

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-15 | `tools.py`: `TriageOutcome` + `write_triage_report` (.md e .json, timestamp, recusa sobrescrever, respeita `TRIAGE_REPORTS_DIR`) | `src/triagem/tools.py` | `tests/test_report.py`: escrita em `tmp_path`, conteúdo com 9 respostas e faixa, recusa overwrite | RF-09, RNF-05 | `feat(tools): add triage report writer` |
| T-16 | Nós `score_node`, `band_node`, `report_node` e `final_answer` (saída estruturada, disclaimer, encaminhamentos fixos, caminho do relatório; nenhum número de LLM) | `src/triagem/nodes.py`, `src/triagem/graph.py` | `tests/test_graph_e2e.py::test_full_triage`: score, faixa, `report_path` e disclaimer presentes | RF-10, RNF-05, RNF-06 | `feat(output): assemble verifiable final answer` |
| T-17 | `cli.py`: loop de sessão com `thread_id`, modo real (dotenv + Gemini) e offline, render de perguntas e resultado | `src/triagem/cli.py` | manual: `TRIAGE_FAKE_LLM=1 uv run python -m triagem.cli` ponta a ponta | RF-04, aceite 1 | `feat(cli): add interactive triage session` |
| T-18 | Fechamento da suíte offline: crise, fora_dominio, duvida, abort e caminho feliz todos verdes sem `.env` | `tests/*` | `uv run pytest` verde em ambiente sem chave | RNF-04, aceites 1-4 | `test: cover critical paths offline` |

### Dia 17/07: documentação e exemplos reais

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-19 | Completar `docs/prompts.md` (criado em 12/07, atualizado a cada sessão): colar as versões finais dos prompts de sistema S-001 a S-003 e manter os registros I-xxx de implementação | `docs/prompts.md` | revisão manual (aceite 6) | §3, aceite 6 | `docs: update prompt log with final system prompts` |
| T-20 | Gravar transcritos reais (baixo, moderado, crise) em `examples/` e 1 relatório de amostra em `reports/` (LLM real se houver chave, senão offline rotulado) | `examples/*`, `reports/*` | conferência manual contra README §7 e §8 | §3 | `docs: add execution transcripts and sample report` |
| T-21 | README final: substituir placeholders §7 e §8, URL do repositório, diagrama com abort_node, revisão dos passos | `README.md` | manual: máquina limpa segue o README em menos de 5 min | aceite 5 | `docs: finalize README with real examples` |

### Dia 18/07: slides e revisão final

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-22 | `docs/slides.md`: roteiro de apresentação | `docs/slides.md` | revisão manual | README §13 | `docs: add presentation outline` |
| T-23 | Revisão final contra aceites 1-6 em máquina limpa (clone novo, `uv sync`, `pytest`, CLI offline) + correções | vários | checklist dos 6 aceites executado e registrado | aceites 1-6 | `chore: final acceptance review fixes` |

### Dia 19/07: publicação

| ID | Tarefa | Arquivos | Teste | Requisito (PRD) | Commit sugerido |
|---|---|---|---|---|---|
| T-24 | Push para o GitHub, tag v0.1, congelamento do repositório | n/a (git) | página do repo confere com README | §7 | `chore(release): v0.1` |

## 4. Riscos e plano B

| Risco | Gatilho | Plano B |
|---|---|---|
| R-01: ciclo com `interrupt()` instável no CLI (decisão A/B) | Spike T-07 não fica estável em 2h no dia 14 (pausa, resume, ciclo de 9, re-pergunta) | Opção B da ARCHITECTURE §4: um `invoke` por mensagem com o mesmo `thread_id`, roteando pela `phase`. Mudanças localizadas: entrada do grafo condicionada à `phase` em `graph.py`, CLI sem `Command(resume)`, testes e2e trocam resumes por invocações sucessivas. Registrar em DECISIONS.md |
| R-02: reexecução do nó ao retomar (`interrupt()` reexecuta o nó desde o início) duplica efeitos colaterais | Testes do spike ou e2e mostram `attempts`/`answers` duplicados | `ask_question` idempotente (só monta payload e chama `interrupt()`); todo efeito colateral fica em `validate_answer`. Se persistir, isolar o `interrupt()` em nó dedicado mínimo |
| R-03: drift de API do LangGraph (formato de `__interrupt__`, `Command`) | Spike revela formato diferente do esqueleto da ARCHITECTURE §4 | Pinar a versão no pyproject; isolar o acesso ao payload em um helper único usado pelo CLI e pelos testes; consultar a documentação da versão pinada |
| R-04: quota, latência ou indisponibilidade do Gemini | Falhas ao gravar exemplos reais no dia 17 | Modo offline é o caminho principal (RNF-02); publicar com transcritos gerados offline, rotulados como tal, e regravar depois se possível |
| R-05: heurística de crise com falso negativo | Frase de sofrimento agudo não dispara a rota nos testes | Lista de termos com recall alto (falso positivo é aceitável, D-04) + classificação LLM estruturada em caso de dúvida quando houver chave; offline, heurística pura e limitação documentada no README §10 |
| R-06: fonte validada do PGSI em PT-BR não confirmada a tempo | Q1/Q2 sem resposta até o dia 13 | T-02 fica bloqueada; seguir com T-03 a T-10 usando fixture de teste com 9 itens sintéticos claramente marcados, e trocar pelo conteúdo validado assim que aprovado |
| R-07: escopo crescer e estourar o prazo de 19/07 | Qualquer proposta fora dos aceites 1-6 antes do congelamento | Cortar extensões (web, mock API, persistência); os aceites 1-6 são o corte mínimo e inegociável, conforme PRD §8 |

## 5. Perguntas abertas

Todas respondidas em 12/07/2026. Registro das decisões:

| # | Pergunta (resumo) | Decisão registrada |
|---|---|---|
| Q1 | Fonte dos 9 itens PGSI em PT-BR (`data/pgsi.json`) | **Eu pesquiso e proponho**: pesquisa realizada em 12/07/2026; fonte encontrada e texto literal dos 9 itens registrados no Anexo A deste documento (status no próprio anexo) |
| Q2 | Escala de resposta 0-3 e tabela de parsing | **Escala validada + sinônimos**: 0 nunca, 1 às vezes, 2 na maioria das vezes, 3 quase sempre; sinônimos remapeados ("quase sempre", "sempre", "toda vez" = 3; "na maioria das vezes", "frequentemente" = 2; "raramente", "de vez em quando" = 1; "nao", "jamais" = 0); corrigir a ARCHITECTURE §5 (afeta T-02 e T-11) |
| Q3 | Comportamento após 3 respostas inválidas | **Oferta com escolha**: após a terceira inválida, novo `interrupt()` pergunta se a pessoa quer tentar de novo ou encerrar; continuar zera `attempts` e reapresenta o item; encerrar entrega recursos; atende RF-05 e aceite 2 literalmente (afeta T-13) |
| Q4 | Checagem de crise nas respostas retomadas | **Checar em `validate_answer`**: a heurística de crise roda antes do parser em toda resposta retomada via `Command(resume=...)`; disparo roteia para `crisis_node` com `crisis_flag=True` (afeta T-14; atende aceite 3 dentro do grafo) |
| Q5 | GitHub e fluxo de branches | **Pull requests no GitHub**: repositório `https://github.com/ernestodeoliveira/jogo-limpo-triagem.git` criado pelo usuário em 12/07 (usuário correto: `ernestodeoliveira`, e não `ernextodeoliveira` como registrado inicialmente); T-01 conecta o `origin` e cada branch curta é integrada via pull request |
| Q6 | LLM do modo real | **Modelo local servido via MLX** (resposta literal: "vou utilizar um modelo local rodando no oMLX"), no lugar do Gemini. Premissa de integração: endpoint local OpenAI-compatible (ex.: `mlx-lm serve` ou LM Studio) consumido via `langchain-openai` com `base_url`; URL e nome do modelo em variáveis de ambiente |

Impactos da decisão Q6 a aplicar no backlog e nos documentos:

- **T-01**: `.env.example` passa a listar `TRIAGE_LLM_BASE_URL=` e `TRIAGE_LLM_MODEL=` (com `GOOGLE_API_KEY=` removida ou mantida como opcional); dependência `langchain[google-genai]` substituída por `langchain-openai`.
- **T-09 e T-17**: a factory `get_llm()` cria o cliente apontando para o endpoint local; o modo offline com fakes permanece o caminho principal de demo e testes.
- **T-21 e T-23**: atualizar README §6 e §11, PRD RNF-01 e §8, e ARCHITECTURE §9, que hoje citam Gemini e `GOOGLE_API_KEY`.
- **R-04**: o risco de quota/latência do Gemini passa a ser disponibilidade e qualidade de structured output do modelo local; a mitigação continua a mesma (offline como caminho principal).
- **Detalhe pendente (não bloqueia o início)**: confirmar qual servidor local (`mlx-lm serve`, LM Studio, outro) e qual modelo será usado, pois o fallback de parsing e a classificação dependem de suporte confiável a tool calling ou JSON mode no servidor escolhido.

## Anexo A: proposta de conteúdo PGSI para data/pgsi.json (Q1)

Status: **aprovado pelo usuário em 12/07/2026**, na opção "aprovar com ajuste de termo": os itens abaixo entram em `data/pgsi.json` na T-02, e a redação "versão validada em português" do README §12 e da D-07 será trocada por "versão brasileira com adaptação transcultural e validade de conteúdo (Moura et al., 2026)" nas tarefas T-21/T-23. Com isso, a T-02 está desbloqueada e a fixture sintética do plano B (R-06) fica desnecessária.

**Fonte proposta**: Moura CC, Spritzer DT, Machado RM, Borghi RN, Gabioneta NS, Andrade AM, Tavares H. Cross-cultural adaptation and content validity of the PGSI into Brazilian Portuguese. Rev Saúde Pública. 2026;60:e27. DOI [10.11606/s1518-8787.2026060007368](https://dx.doi.org/10.11606/s1518-8787.2026060007368). Instrumento original: Ferris J, Wynne H. The Canadian Problem Gambling Index (2001), de uso livre com atribuição. Confirmar a lista completa de autores na página do DOI durante T-02.

**Natureza da fonte**: adaptação transcultural para o português brasileiro com validade de conteúdo e de face (tradução inicial, síntese, retrotradução, comitê de especialistas, painel com 11 especialistas, pré-teste com população geral e revisão final), conduzida pelo grupo do Programa Ambulatorial do Jogo (IPq-HC-FMUSP). Não é ainda a validação psicométrica completa da versão brasileira. Ajuste de redação decorrente: README §12 e D-07 falam em "versão validada em português"; trocar por "versão brasileira com adaptação transcultural e validade de conteúdo (Moura et al., 2026)" nas tarefas T-21/T-23.

**Título do instrumento em PT-BR**: Índice de gravidade de problemas com apostas.

**Enunciado (stem)**: "Pensando nos últimos 12 meses..."

**Escala de resposta** (confirma a decisão Q2): 0 = Nunca; 1 = Às vezes; 2 = Na maioria das vezes; 3 = Quase sempre.

**Itens (versão final, transcrição literal do quadro "Comparison between the original and final Brazilian Portuguese version of the PGSI")**:

| id | Texto |
|---|---|
| q1 | Você apostou mais do que realmente poderia perder? |
| q2 | Ainda pensando nos últimos 12 meses, você precisou apostar quantias cada vez maiores de dinheiro para ter a mesma sensação de prazer? |
| q3 | Depois de ter apostado, você retorna outro dia para tentar recuperar o dinheiro perdido? |
| q4 | Você pediu dinheiro emprestado ou vendeu alguma coisa para conseguir dinheiro para apostar? |
| q5 | Você achou que poderia ter algum problema com apostas? |
| q6 | Apostar já lhe causou algum problema de saúde, como estresse ou ansiedade? |
| q7 | As pessoas já lhe criticaram por apostar, ou disseram que você tinha problemas com apostar, independentemente de você achar que era verdade ou não? |
| q8 | As suas apostas já causaram algum problema financeiro para você ou sua família? |
| q9 | Você já se sentiu culpado(a) pela maneira como você aposta ou pelo que acontece quando você aposta? |

Observação: o trecho "Ainda pensando nos últimos 12 meses" faz parte do texto do item q2 (espelha o original "Still thinking about the last 12 months..."), não do stem.

**Estrutura proposta para `data/pgsi.json`** (a implementar em T-02):

```json
{
  "instrument": "PGSI",
  "title_pt": "Índice de gravidade de problemas com apostas",
  "stem": "Pensando nos últimos 12 meses...",
  "scale": {"0": "Nunca", "1": "Às vezes", "2": "Na maioria das vezes", "3": "Quase sempre"},
  "source": "Moura CC et al. Rev Saúde Pública. 2026;60:e27. doi:10.11606/s1518-8787.2026060007368. Instrumento original: Ferris & Wynne (2001), CPGI.",
  "items": [{"id": "q1", "text": "Você apostou mais do que realmente poderia perder?"}]
}
```
