"""Interactive CLI session for the PGSI triage agent (T-17)."""

from uuid import uuid4

from langgraph.types import Command

from triagem.graph import build_agent, initial_state, read_interrupt_payload
from triagem.nodes import OfferPayload, QuestionPayload

WELCOME = (
    "Olá! Sou o agente de triagem do Jogo Limpo Lab. Aplico o questionário "
    "PGSI, com 9 perguntas sobre os últimos 12 meses, e indico uma faixa "
    "educacional de risco com encaminhamentos. Não é diagnóstico. "
    "Nesta sessão eu respondo a uma única mensagem inicial: diga 'quero "
    "começar' para iniciar a triagem agora, ou faça uma pergunta sobre o "
    "teste (nesse caso a sessão termina em seguida, e você precisa rodar "
    "de novo para começar a triagem)."
)
GOODBYE = "Sessão encerrada. Cuide-se; se precisar de apoio, o CVV atende no 188."


def load_dotenv_if_available() -> None:
    """Optional .env loading: only if python-dotenv happens to be installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def render_question(payload: QuestionPayload) -> str:
    """Format a question payload as the hint (if any), prompt and scale legend."""
    lines = []
    if payload["hint"]:
        lines.append(payload["hint"])
    lines.append(f"Pergunta {payload['index'] + 1} de {payload['total']}: {payload['text']}")
    lines.append("Escala: " + ", ".join(f"{k} = {v}" for k, v in payload["scale"].items()))
    return "\n".join(lines)


def render_offer(payload: OfferPayload) -> str:
    """Format a retry-offer payload as its plain text."""
    return payload["text"]


def render_payload(payload: QuestionPayload | OfferPayload) -> str:
    """Dispatch to render_question or render_offer based on payload['kind']."""
    return render_question(payload) if payload["kind"] == "question" else render_offer(payload)


def main() -> int:
    """Run one interactive session end to end.

    EOFError and KeyboardInterrupt get their own branch because Ctrl-D/Ctrl-C
    are ordinary ways to leave a terminal session and deserve the GOODBYE
    message rather than an error. The broader Exception clause below is a
    final safety net: without it, any other runtime failure inside the graph
    (e.g. a PermissionError from report_node when TRIAGE_REPORTS_DIR is not
    writable) would propagate as a raw traceback instead of degrading
    gracefully like the config-error and EOF/interrupt cases already do.
    """
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
    except Exception as exc:  # noqa: BLE001 - last-resort guard against raw tracebacks
        print(f"\nErro inesperado: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
