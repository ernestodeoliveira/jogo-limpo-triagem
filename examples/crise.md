# Transcrito de execução: crise no meio do questionário

- Data: 2026-07-18
- Modo: LLM real (endpoint local OpenAI-compatible servido pelo oMLX)
- Modelo: Qwen3.6-35B-A3B-4bit (mlx-community)

Sessão completa da CLI (`uv run python -m triagem.cli`); a frase de crise na pergunta 3 aciona o gate imediatamente, o questionário é interrompido e o agente entrega os canais de apoio (CVV 188, SAMU 192). Nenhum relatório é gravado.

```text
Agente: Olá! Sou o agente de triagem do Jogo Limpo Lab. Aplico o questionário PGSI, com 9 perguntas sobre os últimos 12 meses, e indico uma faixa educacional de risco com encaminhamentos. Não é diagnóstico. Nesta sessão eu respondo a uma única mensagem inicial: diga 'quero começar' para iniciar a triagem agora, ou faça uma pergunta sobre o teste (nesse caso a sessão termina em seguida, e você precisa rodar de novo para começar a triagem).

Você: quero começar

Agente:
Pergunta 1 de 9: Você apostou mais do que realmente poderia perder?
Escala: 0 = Nunca, 1 = Às vezes, 2 = Na maioria das vezes, 3 = Quase sempre

Você: nunca

Agente:
Pergunta 2 de 9: Ainda pensando nos últimos 12 meses, você precisou apostar quantias cada vez maiores de dinheiro para ter a mesma sensação de prazer?
Escala: 0 = Nunca, 1 = Às vezes, 2 = Na maioria das vezes, 3 = Quase sempre

Você: 0

Agente:
Pergunta 3 de 9: Depois de ter apostado, você retorna outro dia para tentar recuperar o dinheiro perdido?
Escala: 0 = Nunca, 1 = Às vezes, 2 = Na maioria das vezes, 3 = Quase sempre

Você: não aguento mais, isso está acabando comigo

Agente:
Percebi que você pode estar passando por um momento muito difícil. Sua segurança é mais importante do que esta triagem, então vou encerrar por aqui. Você pode ligar para o CVV pelo telefone 188 (gratuito, 24 horas por dia, todos os dias) para conversar com alguém agora, ou para o SAMU pelo telefone 192 em caso de emergência. Você não precisa passar por isso sozinho ou sozinha.
```
