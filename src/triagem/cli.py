"""Interactive CLI session for the PGSI triage agent (T-17)."""

from uuid import uuid4

from langgraph.types import Command

from triagem.graph import build_agent, initial_state, read_interrupt_payload

WELCOME = (
    "Olá! Sou o agente de triagem do Jogo Limpo Lab. Aplico o questionário "
    "PGSI, com 9 perguntas sobre os últimos 12 meses, e indico uma faixa "
    "educacional de risco com encaminhamentos. Não é diagnóstico. "
    "Diga 'quero começar' para iniciar, ou pergunte sobre o teste."
)
GOODBYE = "Sessão encerrada. Cuide-se; se precisar de apoio, o CVV atende no 188."


def load_dotenv_if_available() -> None:
    """Optional .env loading: only if python-dotenv happens to be installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def render_question(payload) -> str:
    lines = []
    if payload["hint"]:
        lines.append(payload["hint"])
    lines.append(f"Pergunta {payload['index'] + 1} de {payload['total']}: {payload['text']}")
    lines.append("Escala: " + ", ".join(f"{k} = {v}" for k, v in payload["scale"].items()))
    return "\n".join(lines)


def render_offer(payload) -> str:
    return payload["text"]


def render_payload(payload) -> str:
    return render_question(payload) if payload["kind"] == "question" else render_offer(payload)


def main() -> int:
    load_dotenv_if_available()
    try:
        app = build_agent()  # get_llm() resolve fake/real pelo ambiente
    except RuntimeError as exc:  # envs do endpoint ausentes no modo real
        print(f"Erro de configuração: {exc}")
        return 2
    config = {"configurable": {"thread_id": uuid4().hex}}
    print(f"Agente: {WELCOME}\n")
    try:
        result = app.invoke(initial_state(input("Você: ")), config)
        while (payload := read_interrupt_payload(result)) is not None:
            print(f"\nAgente:\n{render_payload(payload)}\n")
            result = app.invoke(Command(resume=input("Você: ")), config)
        print(f"\nAgente:\n{result['final_answer']}")
        return 0
    except (EOFError, KeyboardInterrupt):
        print(f"\n{GOODBYE}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
