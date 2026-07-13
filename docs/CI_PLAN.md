# docs/CI_PLAN.md: plano de integração contínua (GitHub Actions)

Planejamento da configuração de CI para o jogo-limpo-triagem. Este documento é o resultado da sessão P-004 (ver `docs/prompts.md`). Nenhum workflow foi criado nesta sessão: apenas o design, o backlog e as decisões abertas.

---

## 1. Resumo do entendimento

O projeto roda hoje com `uv run pytest` (198 testes), sempre offline: a fixture autouse `offline_env` em `tests/conftest.py` força `TRIAGE_FAKE_LLM=1` e apaga `TRIAGE_LLM_BASE_URL`/`TRIAGE_LLM_MODEL`, então a suíte nunca precisa de secret do GitHub. `pyproject.toml` exige `Python >=3.11`, com `langgraph`, `langchain-openai` e `pydantic` travados por teto de versão; `uv.lock` tem 133 pacotes com hashes íntegros (auditado na I-001). Não existe `.github/` nem nenhuma ferramenta de lint/format configurada. O repositório é público (`ernestodeoliveira/jogo-limpo-triagem`), branch padrão `main`, o que habilita branch protection no plano gratuito do GitHub. O objetivo desta sessão é desenhar um workflow de CI mínimo, seguro (menor privilégio, actions pinadas por hash) e fiel ao comando local, mais o backlog para uma sessão futura implementar.

## 2. Opções consideradas e descartadas

**Setup de Python/uv**
- `actions/setup-python` + `pip install`: ignora `uv.lock`; duplicaria a fonte de verdade de dependências e reintroduziria o problema de builds não reprodutíveis que o projeto já resolveu com uv. Descartado.
- `actions/setup-python` + `astral-sh/setup-uv` juntos: redundante. O `setup-uv` já instala o Python certo via uv a partir do input `python-version`, sem precisar de uma segunda action. Descartado.
- Instalar uv via `curl -LsSf https://astral.sh/uv/install.sh | sh`: sem pinagem por hash de commit, sem cache integrado, contraria a postura de supply chain já adotada no projeto (hashes no `uv.lock`). Descartado.
- **Escolhido**: `astral-sh/setup-uv`, ação oficial mantida pelos autores do uv, com cache de dependências embutido e input dedicado para pinar a versão do uv.

**Cache de dependências**
- `actions/cache` manual sobre `~/.cache/uv`: reimplementa o que `setup-uv` já faz com `enable-cache: true` (inclusive com poda automática do cache). Descartado por redundância.
- **Escolhido**: cache embutido do `setup-uv`, com `cache-dependency-glob` default (já cobre `pyproject.toml` e `uv.lock`).

**Pinagem de actions de terceiros**
- Tag semver móvel (ex. `@v8` ou `@v8.3.2`): tags podem ser reapontadas pelo mantenedor (inclusive por comprometimento de conta), o que quebra a garantia de imutabilidade. Descartado.
- **Escolhido**: pinagem por SHA de commit completo, com a tag em comentário ao lado (`@<sha> # v8.3.2`), mesma lógica dos hashes de pacote no `uv.lock`.

**Gatilhos**
- Só `pull_request`: mais barato, mas nunca valida o estado da `main` após um merge direto ou squash-merge (o diff mergeado pode diferir do diff revisado). Descartado como única opção.
- `push` em todas as branches: redundante com o gatilho de PR no fluxo do projeto (branches curtas, sempre via PR), dobra o consumo de minutos sem ganho de sinal. Descartado.
- `schedule` (cron periódico): útil para detectar drift de dependências ao longo do tempo, mas o projeto congela em 19/07/2026 (v0.1) e não terá janela de vida para isso ser útil. Descartado.
- **Escolhido**: `pull_request` contra `main` (obrigatório) + `push` em `main` (pós-merge, decisão do usuário) + `workflow_dispatch` (reexecução manual sem custo de manutenção).

**Versões de Python**
- Matriz 3.11/3.12/3.13: custo 3x de minutos de CI para um protótipo que declara e trava em `>=3.11` sem qualquer teste ou uso real em versões mais novas. Descartado.
- Matriz 3.11 + 3.13 (mínima + mais recente): custo 2x, mesmo argumento acima. Descartado.
- **Escolhido**: só Python 3.11, decisão do usuário (ver §5, pergunta 1).

**Branch protection**
- Rulesets (API nova do GitHub): mais flexível para regras complexas (múltiplos branches, deploys), mas mais peças móveis do que o caso de uso atual precisa (um único branch, um único check). Descartado por ora.
- **Escolhido**: proteção clássica de branch (`branches/main/protection`), com `required_status_checks` no job de testes.

## 3. Proposta recomendada

### Nome e badge

- Nome do workflow: `CI` (arquivo `.github/workflows/ci.yml`, job único `tests`).
- Badge de status no topo do `README.md`, decisão do usuário (§5, pergunta 2): `![CI](https://github.com/ernestodeoliveira/jogo-limpo-triagem/actions/workflows/ci.yml/badge.svg)`.

### Gatilhos e permissões

- `pull_request` para `main`, `push` em `main`, `workflow_dispatch`.
- `permissions: contents: read` no nível do workflow: o job só lê o repositório e roda testes, nunca escreve (sem publicação de pacote, sem comentário em PR, sem push).
- `concurrency` com `cancel-in-progress: true`, chave por `github.workflow`+`github.ref`: evita acumular runs obsoletos quando um PR recebe vários pushes seguidos.

### Setup do uv e execução dos testes

- `astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990 # v8.3.2`, com `version: "0.10.2"` (pina o uv na mesma versão usada localmente pelo mantenedor), `python-version: "3.11"`, `enable-cache: true`.
- `uv sync --locked`: instala exatamente o que está em `uv.lock` e falha se o lock estiver desatualizado em relação ao `pyproject.toml` (detecta lock esquecido de regenerar).
- `uv run --no-sync pytest`: roda a suíte sem tentar resolver dependências de novo (já sincronizadas no passo anterior).
- Nenhuma variável de ambiente é definida no workflow. A fixture autouse `offline_env` (`tests/conftest.py:11`) já força `TRIAGE_FAKE_LLM=1` e limpa `TRIAGE_LLM_BASE_URL`/`TRIAGE_LLM_MODEL` para todo teste, então o job roda em um runner limpo, sem nenhum secret configurado, e isso prova na prática o requisito de modo offline (RNF-02/RNF-04) a cada execução.

### Lint/format

- Decisão do usuário (§5, pergunta 3): não entra nesta CI inicial. Vira backlog condicional (C-04/C-05) para uma sessão futura, com `ruff` como ferramenta escolhida (lint + format em uma dependência só, mantendo o `pyproject.toml` enxuto).

### Esboço do workflow (ilustrativo; não criado nesta sessão)

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0

      - uses: astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990 # v8.3.2
        with:
          version: "0.10.2"
          python-version: "3.11"
          enable-cache: true

      - name: Install dependencies (locked)
        run: uv sync --locked

      - name: Run tests
        run: uv run --no-sync pytest
```

### Branch protection

Decisão do usuário (§5, pergunta 4): configurar via `gh api`, na sessão de implementação, depois do primeiro run verde na `main`, com aprovação explícita do usuário antes de executar (mudança de configuração do repositório, não versionada em arquivo). Esboço do comando:

```bash
gh api --method PUT repos/ernestodeoliveira/jogo-limpo-triagem/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["tests"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

Após isso, o fluxo de merge do projeto passa a usar `gh pr merge --auto --squash` (ou equivalente), aguardando o check `tests` antes de completar o merge, em vez do `gh pr merge` imediato usado nas sessões I-001 a I-004.

## 4. Backlog de implementação

| ID | Tarefa | Arquivos | Teste/Verificação | Commit sugerido |
|---|---|---|---|---|
| C-01 | Workflow CI: gatilhos `pull_request`/`push`/`workflow_dispatch`, `permissions: contents: read`, `concurrency`, `actions/checkout` e `astral-sh/setup-uv` pinados por SHA, uv 0.10.2, Python 3.11, `uv sync --locked` + `uv run --no-sync pytest`, sem env/secret | `.github/workflows/ci.yml` | Abrir PR de teste dispara o run; `gh run watch` conclui verde; log confirma os 198 testes coletados e nenhuma variável `TRIAGE_LLM_BASE_URL`/`GOOGLE_API_KEY` presente no ambiente do job | `ci: add github actions workflow running tests offline` |
| C-02 | Badge de status no topo do `README.md`, apontando para o workflow `CI` na `main` | `README.md` | Badge renderiza "passing" no GitHub após o primeiro run verde na `main` (pós-merge do C-01) | `docs(readme): add ci status badge` |
| C-03 | Exigir o check `tests` antes de merge na `main` (proteção clássica de branch, `strict: true`, `enforce_admins: true`) via `gh api PUT repos/.../branches/main/protection`, executado só após o primeiro run verde na `main` e com aprovação explícita do usuário na hora; atualizar o fluxo de merge do projeto para `gh pr merge --auto` | n/a (configuração do repositório, não versionada) | `gh api repos/.../branches/main/protection --jq .required_status_checks.contexts` retorna `["tests"]`; um PR de teste não conclui o merge automático enquanto o check está pendente | n/a (sem commit de código; decisão e execução registradas no resultado da sessão de implementação em `docs/prompts.md`) |
| C-04 (condicional à decisão de lint) | Adicionar `ruff` ao grupo `dev` em `pyproject.toml` (com teto de versão) e configuração mínima (`[tool.ruff]`); corrigir os apontamentos encontrados no código existente | `pyproject.toml`, `uv.lock`, arquivos apontados pelo ruff | `uv run ruff check .` e `uv run ruff format --check .` limpos localmente; nova auditoria de supply chain do `uv.lock` (dependência nova) | `chore: add ruff lint and format check` |
| C-05 (condicional à decisão de lint) | Job `lint` no workflow, paralelo ao job `tests`, rodando `uv run ruff check .` e `uv run ruff format --check .` | `.github/workflows/ci.yml` | Run do PR mostra os dois jobs (`tests` e `lint`) verdes de forma independente | `ci: add lint job with ruff` |

**Ordem de execução sugerida**: C-01 e C-02 no mesmo pull request (o badge só passa a mostrar dado real depois do merge na `main`, mas o texto já pode entrar junto); C-03 é uma ação pós-merge, fora de qualquer PR; C-04 e C-05, se aprovados no backlog geral do projeto, formam um segundo pull request independente, depois que C-01/C-02 estiverem mergeados e o primeiro run verde na `main` tiver acontecido.

## 5. Perguntas abertas

### 1. Quais versões de Python o CI deve testar?

**Recomendação**: só Python 3.11 (versão mínima e única declarada em `requires-python`; protótipo v0.1 sem uso real em versões mais novas).

**Decisão do usuário**: só 3.11.

### 2. O workflow deve rodar também em `push` na `main`, e vale adicionar badge de status no README?

**Recomendação**: sim para os dois. O run em `push` valida o estado real da `main` após cada merge (squash-merge pode gerar um diff levemente diferente do revisado no PR); o badge expõe esse status publicamente com custo desprezível (um run extra por merge).

**Decisão do usuário**: sim, ambos.

### 3. Vale incluir lint/format (ruff) neste mesmo lote de CI?

**Recomendação**: não. O CI base (testes) deve entrar primeiro e ficar estável; lint vira tarefa separada do backlog (C-04/C-05), em PR próprio, só se houver tempo antes do congelamento de 19/07/2026. Evita misturar a introdução de uma ferramenta nova (que pode gerar dezenas de apontamentos a corrigir) com a entrega do CI mínimo.

**Decisão do usuário**: tarefa separada, depois do CI base verde.

### 4. Vale exigir o check da CI como obrigatório antes de merge (branch protection)?

**Recomendação**: sim, configurado via `gh api` na própria sessão de implementação, mas só depois do primeiro run verde na `main` e com aprovação explícita do usuário no momento da execução (é mudança de configuração do repositório, não um arquivo versionado, e mexe em como merges futuros acontecem).

**Decisão do usuário**: sim, via `gh api` na sessão de implementação, com aprovação explícita na hora.
