---
marp: true
paginate: true
title: "Jogo Limpo: Agente de Triagem PGSI"
style: |
  section {
    font-size: 22px;
  }
---

# Jogo Limpo: Agente de Triagem PGSI

## O problema

- Brasil regulamentou as apostas, mas falta um ponto de entrada acolhedor para quem está preocupado com o próprio jogo.
- Faltam triagens com um instrumento validado que classifiquem o risco e encaminhem para ajuda real.

## Processo automatizado escolhido

- Triagem estruturada com o PGSI (Problem Gambling Severity Index): 9 itens validados, um por vez, respostas na escala 0-3.

## Proposta do agente

- Agente conversacional LangGraph que acolhe, aplica o PGSI, classifica a faixa de risco e encaminha; triagem educacional, não diagnóstico.

---

## Entrada, saída e ferramentas

- **Entrada**: mensagens de texto em linguagem natural ou na escala 0-3.
- **Saída**: faixa de risco, explicação, encaminhamentos + relatório `.md`/`.json` em `reports/`.
- `load_pgsi_questions`: carrega e valida os 9 itens de `data/pgsi.json`.
- `compute_pgsi_score`: função controlada; valida 9 respostas 0-3 e calcula o score (0-27).
- `write_triage_report`: grava o relatório `.md`/`.json` em `reports/`; recusa sobrescrever.

## Fluxo LangGraph

- `safety_gate` (gate de crise) → `classify_intent` → ciclo `ask_question`/`validate_answer` com `interrupt()`.
- Respostas inválidas repetidas: `retry_offer` (tentar de novo) ou `abort_node` (encerrar).
- `score_node` → `band_node` → `report_node` → resposta final.
