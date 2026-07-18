# PRD: Agente de Triagem PGSI

Status: Aprovado para implementação. Marco v0.1 (publicação e congelamento): 19/07/2026.

## 1. Contexto e problema

Ver README §1. Em uma frase: automatizar, como agente conversacional, o processo de triagem de risco de jogo que hoje não tem ponto de entrada estruturado, aplicando instrumento validado (PGSI) e encaminhando para recursos reais.

## 2. Objetivo e não-objetivos

**Objetivo**: agente funcional, demonstrável e documentado que conduz a triagem multi-turno, calcula score por ferramenta, classifica faixa e entrega saída estruturada + relatório em arquivo.

**Não-objetivos (fora de escopo)**: qualquer funcionalidade clínica ou terapêutica, interface web, persistência em banco, autenticação, deploy, WhatsApp, multi-idioma.

## 3. Diretrizes de engenharia

Padrões que valem para o projeto inteiro, independentes de funcionalidade:

- Histórico de commits semânticos em branches curtas (`feat(scope):`, `test:`, `docs:`, `chore:`), com merges pequenos e frequentes (sequência sugerida em docs/PLAN.md).
- Documentação executável: o README deve permitir a qualquer pessoa rodar o projeto em menos de 5 minutos, em máquina limpa e sem chave de API.
- Registro contínuo de prompts em `docs/prompts.md` (planejamento, prompts de sistema do agente e sessões de implementação).
- Exemplos reais versionados em `examples/` (transcritos de execução) e um relatório de amostra em `reports/`.
- Testes sempre executáveis offline; nenhum segredo versionado.
- Validação em três pontos: entrada do usuário (RF-05), insumos da ferramenta (RF-07) e saída final (RNF-05).

## 4. Requisitos funcionais

- **RF-01 Gate de crise**: toda entrada passa primeiro por `safety_gate`; em sinal de emergência ou risco à própria vida, o agente interrompe o fluxo com acolhimento breve, entrega CVV 188, SAMU 192 e orientação de buscar ajuda imediata, marca `crisis_flag` e encerra a triagem daquela sessão.
- **RF-02 Classificação de intenção**: `classify_intent` com saída estruturada (Pydantic) em `iniciar | responder | duvida | fora_dominio`; `fora_dominio` → fallback educado; `duvida` → nó informativo estático (o que é o teste, como funciona a escala, privacidade).
- **RF-03 Questionário PGSI**: 9 itens carregados de `data/pgsi.json`; uma pergunta por vez, com número da pergunta e escala explicada.
- **RF-04 Ciclo multi-turno**: pergunta pausa com `interrupt()`; resposta retoma via `Command(resume=...)`; checkpointer `InMemorySaver`; `thread_id` por sessão do CLI.
- **RF-05 Validação de resposta**: parser determinístico texto→0-3 (tabela em ARCHITECTURE §5); resposta inválida gera re-pergunta com dica; máximo 3 tentativas por item, depois oferta de encerrar; instruções embutidas na resposta ("ignore as regras...") são tratadas como inválidas.
- **RF-06 Acúmulo no estado**: respostas em `answers` com reducer (`operator.or_`); `current_question` avança apenas com resposta válida.
- **RF-07 Score por função controlada**: `compute_pgsi_score` exige exatamente 9 valores inteiros 0-3; retorna `ScoreResult`; qualquer violação gera erro claro, nunca score parcial.
- **RF-08 Classificação de faixa**: 0 sem_risco; 1-2 baixo; 3-7 moderado; 8-27 alto.
- **RF-09 Relatório**: `write_triage_report` grava Markdown + JSON em `reports/` com timestamp, faixa, score, as 9 respostas e os encaminhamentos; recusa sobrescrever arquivo existente; retorna o caminho.
- **RF-10 Saída final estruturada**: faixa + explicação em linguagem acolhedora + encaminhamentos fixos (Autoexclusão gov.br, CVV 188, CAPS/SUS) + disclaimer não clínico + caminho do relatório.

## 5. Requisitos não funcionais

- **RNF-01 Segredos**: nenhuma chave no repositório; `.env.example` traz apenas os nomes das variáveis de configuração (`TRIAGE_FAKE_LLM`, `TRIAGE_LLM_BASE_URL`, `TRIAGE_LLM_MODEL`, `TRIAGE_REPORTS_DIR`); `OPENAI_API_KEY` é suportada como token Bearer opcional para endpoints locais que exigem autenticação, sem valor versionado; `.gitignore` cobre `.env`.
- **RNF-02 Modo offline**: `TRIAGE_FAKE_LLM=1` executa CLI e testes com FakeLLM determinístico, sem rede e sem chave.
- **RNF-03 Injeção**: conteúdo do usuário nunca vai para prompt de sistema; LLM de fallback recebe a resposta como dado com saída restrita a `Literal[0,1,2,3]`.
- **RNF-04 Testes**: `uv run pytest` verde sem chave de API; cobertura dos caminhos críticos (score, parsing, crise, roteamento, relatório).
- **RNF-05 Verificabilidade**: relatório contém os insumos do cálculo; nenhum número na saída final é gerado por LLM.
- **RNF-06 Idioma e tom**: PT-BR, linguagem acolhedora e neutra, sem promessa terapêutica.

## 6. Critérios de aceite (v0.1)

1. `TRIAGE_FAKE_LLM=1 uv run python -m triagem.cli` completa uma triagem de ponta a ponta e grava relatório.
2. Resposta inválida ("talvez", "42") gera re-pergunta; três inválidas seguidas ofertam encerrar.
3. Frase de crise no meio do questionário aciona RF-01 imediatamente.
4. `uv run pytest` verde em máquina limpa sem `.env`.
5. README permite a qualquer pessoa executar tudo em menos de 5 minutos, em máquina limpa.
6. `docs/prompts.md` contém os prompts de planejamento e os prompts de sistema finais.

## 7. Marcos (12/07 a 19/07)

| Dia | Marco |
|---|---|
| 13/07 | Scaffold + estado + `load_pgsi_questions` + `compute_pgsi_score` com testes |
| 14/07 | Grafo core + ciclo de 9 perguntas com interrupt (decisão A/B até o fim do dia) |
| 15/07 | Parser + validação + gate de crise com testes |
| 16/07 | Relatório + saída final + CLI completo |
| 17/07 | README final + prompts.md + examples/ com transcritos reais |
| 18/07 | Slides + revisão final contra os critérios de aceite |
| 19/07 | Publicação (tag v0.1) e congelamento do repositório |

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Ciclo com `interrupt` instável no CLI | Plano B por turno (`invoke` por mensagem com mesmo `thread_id`); decidir dia 14 após 2 h de tentativa |
| Indisponibilidade/latência do endpoint local (oMLX) | Modo offline como caminho principal de demo; LLM real só na gravação final de exemplos |
| Escopo crescer (mock API, web) | Extensões só após critérios de aceite 1-6 fechados |
| Documentação incompleta na publicação | Revisão final contra os critérios de aceite no dia 18 |
