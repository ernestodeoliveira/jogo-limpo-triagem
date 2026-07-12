# DECISIONS: registro de decisões do projeto

Formato curto: Decisão / Racional / Trade-off aceito. Alimenta a seção "principais decisões" do README.

## D-01: Repositório do zero, não fork do stack-sentinel

**Decisão**: criar `jogo-limpo-triagem` novo; usar o repositório `stack-sentinel-senai` apenas como referência de padrões, citado no README.
**Racional**: o histórico de commits deve contar a evolução deste projeto desde o primeiro commit; a maior parte do stack-sentinel (mock API de tickets/builds, MCP server, nós de fetch) resolve outro domínio e viraria peso morto a remover; padrões idiomáticos se recriam em minutos e ficam citados nas referências.
**Trade-off**: ~30 minutos de scaffold manual.

## D-02: Ciclo do questionário com interrupt() (plano B: um invoke por turno)

**Decisão**: `ask_question` pausa com `interrupt()`; o CLI retoma com `Command(resume=...)`; checkpointer obrigatório.
**Racional**: é o padrão idiomático de human-in-the-loop do LangGraph, evidencia memória de sessão e mantém o questionário como um único run auditável.
**Trade-off**: padrão mais novo, menos material de apoio; por isso o plano B (invoke por turno com mesmo `thread_id`) está especificado e o prazo de decisão é o dia 14.

## D-03: Parser determinístico antes de LLM

**Decisão**: respostas 0-3 são interpretadas por tabela de normalização; LLM só como fallback, com saída restrita a `Literal[0,1,2,3] | None`.
**Racional**: determinismo torna a validação testável sem chave de API, reduz custo/latência e trata prompt injection por construção (o parser não obedece instruções, só reconhece valores).
**Trade-off**: respostas muito coloquiais podem cair no fallback ou serem rejeitadas; aceitável para o escopo.

## D-04: Gate de crise com precedência absoluta

**Decisão**: toda entrada passa por `safety_gate` antes de intenção ou questionário; sinal de emergência interrompe a triagem e entrega CVV 188, SAMU 192 e orientação de ajuda imediata.
**Racional**: o domínio (risco de jogo) tem sobreposição real com sofrimento agudo; um agente que continua aplicando questionário por cima de um pedido de socorro é um defeito ético e de produto, não um detalhe.
**Trade-off**: falsos positivos interrompem a triagem; aceitável, a pessoa pode recomeçar.

## D-05: Modo offline com fakes determinísticos

**Decisão**: `TRIAGE_FAKE_LLM=1` roda CLI e testes com `FakeClassifier`/`FakeAnswerParser` (mesma interface do modelo real).
**Racional**: qualquer pessoa executa e testa sem chave, em máquina limpa; padrão consolidado no repo de referência (`fakes.py`).
**Trade-off**: os fakes precisam ser mantidos em sincronia com as interfaces reais.

## D-06: Saída verificável, LLM não calcula

**Decisão**: score e faixa vêm exclusivamente da função controlada; o relatório inclui as 9 respostas usadas; nenhum número da saída final é gerado por LLM.
**Racional**: princípio herdado do produto Jogo Limpo (quem redige não calcula); elimina a classe de erro mais grave em um resultado de triagem.
**Trade-off**: textos finais menos "criativos"; irrelevante aqui.

## D-07: PGSI como instrumento, com atribuição e sem paráfrase

**Decisão**: usar os 9 itens da versão validada em português em `data/pgsi.json`, com citação (Ferris & Wynne, 2001, CPGI); não reescrever itens.
**Racional**: a validade do instrumento está na redação original; parafrasear inventaria um questionário sem validade.
**Trade-off**: nenhum relevante.

## D-08: Sem claim clínico em nenhum texto

**Decisão**: toda saída carrega o disclaimer de triagem educacional; tom acolhedor e neutro; encaminhamentos fixos (Autoexclusão gov.br, CVV 188, CAPS/SUS).
**Racional**: coerência com as restrições do produto real e postura responsável no domínio.
**Trade-off**: nenhum.

## D-09: Opção A confirmada: multi-turno com interrupt() e Command(resume=...)

**Decisão**: adotar em definitivo a opção A da ARCHITECTURE §4 (`interrupt()` dentro de `ask_question`, retomada via `Command(resume=...)`, checkpointer obrigatório); a opção B (um invoke por turno) fica descartada.
**Racional**: o spike `tests/test_interrupt_spike.py` (T-07, langgraph 1.2.9) comprovou dentro do timebox de 2h: `result["__interrupt__"]` é uma sequência (lista na 1.2.9) de `Interrupt` com `.value` (payload) e `.id`; `Command(resume=texto)` retoma o interrupt pendente preservando tipo e ordem; 2 ciclos completos de pausa e retomada funcionam; na retomada o nó reexecuta desde o início (contador `[0, 0, 1, 1]` em 2 perguntas), sem duplicar escritas de estado; threads com `thread_id` distintos são isolados no mesmo app compilado.
**Trade-off**: nós que chamam `interrupt()` precisam ser idempotentes antes da pausa, porque efeitos colaterais pré-interrupt duplicam na retomada (mitigação do R-02: `ask_question` só monta payload, efeitos ficam em `validate_answer`); o acesso ao payload fica isolado em um helper único (`read_interrupt_payload`, mitigação do R-03).
