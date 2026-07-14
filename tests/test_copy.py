"""Locks the literal wording of every fixed user-facing message (F-01, D-08)."""

from triagem.cli import GOODBYE, WELCOME
from triagem.nodes import (
    ABORT_MESSAGE,
    BAND_EXPLANATIONS,
    BAND_LABELS,
    FALLBACK_MESSAGE,
    INFO_MESSAGE,
    OFFER_MESSAGE,
    RETRY_HINT,
)
from triagem.parsing import normalize
from triagem.safety import CRISIS_MESSAGE
from triagem.tools import DISCLAIMER, REFERRALS


def test_welcome_message():
    assert WELCOME == (
        "Olá! Sou o agente de triagem do Jogo Limpo Lab. Aplico o questionário "
        "PGSI, com 9 perguntas sobre os últimos 12 meses, e indico uma faixa "
        "educacional de risco com encaminhamentos. Não é diagnóstico. "
        "Nesta sessão eu respondo a uma única mensagem inicial: diga 'quero "
        "começar' para iniciar a triagem agora, ou faça uma pergunta sobre o "
        "teste (nesse caso a sessão termina em seguida, e você precisa rodar "
        "de novo para começar a triagem)."
    )


def test_goodbye_message():
    assert GOODBYE == (
        "Sessão encerrada. Cuide-se; se precisar de apoio, o CVV atende no 188."
    )


def test_info_message():
    assert INFO_MESSAGE == (
        "Este é o PGSI (Índice de gravidade de problemas com apostas), um "
        "questionário de triagem com 9 perguntas sobre os últimos 12 meses. Cada "
        "resposta usa uma escala de 0 a 3 (0 nunca, 1 às vezes, 2 na maioria das "
        "vezes, 3 quase sempre). O resultado indica uma faixa educacional de risco "
        "e não é um diagnóstico. Nada além das suas 9 respostas é usado no "
        "resultado. Quando quiser começar, é só dizer."
    )


def test_fallback_message():
    assert FALLBACK_MESSAGE == (
        "Eu consigo ajudar apenas com a triagem educacional sobre o uso de apostas "
        "(questionário PGSI). Se quiser, podemos começar agora: são 9 perguntas "
        "rápidas sobre os últimos 12 meses."
    )


def test_abort_message():
    assert ABORT_MESSAGE == (
        "Não consegui entender as respostas depois de algumas tentativas, então vou "
        "encerrar a triagem por aqui. Você pode recomeçar quando quiser, respondendo "
        "com um número de 0 a 3 para cada pergunta. Se estiver precisando de apoio "
        "agora, o CVV atende pelo telefone 188, todos os dias, 24 horas."
    )


def test_retry_hint():
    assert RETRY_HINT == (
        "Não consegui entender sua resposta. Responda com um número de 0 a 3, ou "
        "com as palavras da escala: 0 nunca, 1 às vezes, 2 na maioria das vezes, "
        "3 quase sempre."
    )


def test_offer_message():
    assert OFFER_MESSAGE == (
        "Não consegui entender suas respostas. Você quer tentar essa pergunta de "
        "novo ou prefere encerrar por aqui?"
    )


def test_band_labels():
    assert BAND_LABELS == {
        "sem_risco": "sem indicativo de risco",
        "baixo": "risco baixo",
        "moderado": "risco moderado",
        "alto": "risco alto",
    }


def test_band_explanations():
    assert BAND_EXPLANATIONS == {
        "sem_risco": (
            "Suas respostas não indicam sinais de risco relacionados a apostas "
            "neste momento. Vale seguir atento ao seu bem-estar."
        ),
        "baixo": (
            "Suas respostas indicam um risco baixo relacionado a apostas. Pode "
            "ser útil observar se o seu padrão de uso muda com o tempo."
        ),
        "moderado": (
            "Suas respostas indicam um risco moderado relacionado a apostas. "
            "Buscar mais informações ou conversar com alguém de confiança pode "
            "ajudar."
        ),
        "alto": (
            "Suas respostas indicam um risco alto relacionado a apostas. Buscar "
            "apoio especializado pode fazer diferença, e você não precisa lidar "
            "com isso sozinho."
        ),
    }


def test_disclaimer():
    assert DISCLAIMER == (
        "Este resultado é uma triagem educacional e não constitui diagnóstico "
        "nem substitui avaliação profissional."
    )


def test_referrals():
    assert REFERRALS == (
        "Plataforma centralizada de autoexclusão de apostas: gov.br",
        "CVV: ligue 188, gratuito, 24 horas por dia, todos os dias",
        "Rede CAPS/SUS: procure a unidade de saúde mais próxima",
    )


def test_crisis_message():
    assert CRISIS_MESSAGE == (
        "Percebi que você pode estar passando por um momento muito difícil. Sua "
        "segurança é mais importante do que esta triagem, então vou encerrar por "
        "aqui. Você pode ligar para o CVV pelo telefone 188 (gratuito, 24 horas "
        "por dia, todos os dias) para conversar com alguém agora, ou para o SAMU "
        "pelo telefone 192 em caso de emergência. Você não precisa passar por "
        "isso sozinho ou sozinha."
    )


# Written already in normalize()'s output form (lowercase, unaccented, no
# punctuation): reusing triagem.parsing.normalize on both sides means accent
# and case variants ("você tem" vs "voce tem") don't need to be hand-listed,
# the same discipline ANSWER_TABLE relies on in parsing.py.
_FORBIDDEN_CLINICAL_TERMS = (
    "transtorno",
    "patologia",
    "voce tem",
    "voce sofre",
    "doenca mental",
    "quadro clinico",
)

_ALL_USER_COPY = (
    WELCOME,
    GOODBYE,
    INFO_MESSAGE,
    FALLBACK_MESSAGE,
    ABORT_MESSAGE,
    RETRY_HINT,
    OFFER_MESSAGE,
    *BAND_LABELS.values(),
    *BAND_EXPLANATIONS.values(),
    DISCLAIMER,
    *REFERRALS,
    CRISIS_MESSAGE,
)


def test_no_clinical_claims_in_user_copy():
    assert "não constitui diagnóstico" in DISCLAIMER
    assert "188" in CRISIS_MESSAGE
    assert "192" in CRISIS_MESSAGE
    for text in _ALL_USER_COPY:
        normalized = normalize(text)
        for forbidden in _FORBIDDEN_CLINICAL_TERMS:
            assert forbidden not in normalized, (
                f"forbidden term {forbidden!r} found in: {text!r}"
            )
