# compliance-copilot

A generative AI assistant (RAG) that answers compliance questions on the **EU AI Act, DORA and the GDPR**
with **citations to the source article**, refuses when no source supports an answer, and comes with the
governance around it: data contracts, quality gates, evaluation in CI, tracing and cost monitoring,
an audit log, a risk register mapped to the AI Act, a model card and a Data & AI roadmap.

It also triages **synthetic** insurance claims, under the same rule as
[clinical-notes-eval](https://github.com/26sneakysnake/clinical-notes-eval): the system suggests, a person decides.
The evaluation bench is carried over from that project (per-item scoring, error files, decision agreement).

> **Scope and honesty.** The bank ("Banque du Vexin") and the insurer ("Assurances du Vexin") are fictional.
> All claims are synthetic: invented names, `example.org` e-mails, phone numbers from the ranges reserved for
> fiction, IBANs that fail the checksum. The committed regulatory corpus is a **paraphrase** written for testing,
> clearly labelled as such; the official texts are fetched from EUR-Lex with `ccp fetch-official`.
> Nothing here is legal advice.

## What each gap became

| Gap | What is built | Where |
|---|---|---|
| Data platforms | Bronze/silver/gold Delta tables and notebooks for **Databricks Free Edition**; API container deployed to **Azure Container Apps** (free grant, scale to zero) by GitHub Actions | `databricks/`, `infra/`, `.github/workflows/deploy.yml` |
| Data quality and governance | YAML **data contracts** compiled to **Pandera** schemas and to Delta `CHECK` constraints; pipeline stops on violation; generated **data catalog**; **access roles** enforced by the API and as Unity Catalog `GRANT`s; column masks on raw identifiers | `contracts/`, `ccp/contracts.py`, `ccp/catalog_sql.py`, `docs/data_catalog.md`, `governance/access_roles.yaml` |
| MLOps / LLMOps | 61-question golden set, **non-regression gate in CI** against `main`; **versioned prompts** with hashes; **OpenTelemetry tracing** (Langfuse-ready) with tokens, **cost and latency**; manual LLM evaluation workflow | `eval/`, `ccp/eval/`, `prompts/`, `ccp/tracing.py`, `.github/workflows/` |
| Trusted AI and compliance | **Model card**; **risk register** classified under the AI Act and checked in CI (every control must point to existing evidence); **refusal without source**; citation validation; **hash-chained audit log**; **anonymisation** before the silver layer and before any model call | `docs/model_card.md`, `governance/risk_register.yaml`, `docs/risk_register.md`, `ccp/rag.py`, `ccp/audit.py`, `ccp/redact.py` |
| Banking and insurance | Compliance Q&A for a bank; **property & casualty claims triage** that never rejects a claim | `ccp/triage.py`, `ccp/synthetic.py` |
| Roadmap and prioritisation | 8-slide deck for a fictional bank: 8 use cases scored on impact, effort and risk, three waves aligned with the AI Act calendar | `docs/roadmap/` |
| API and containers | FastAPI with role-based keys, Docker image (non-root, health check), automatic deployment | `ccp/api.py`, `Dockerfile` |

## How a question is answered

```
question ─► input guard ─► BM25 retrieval ─► retrieval gate ─► generator ─► citation check ─► answer + sources
              │ (empty, too long,     │ (regulation      │ (score and      │ (extractive   │ (every sentence must
              │  instruction override)│  named = filter) │  coverage)      │  or Claude)   │  cite a retrieved passage)
              └────────── refuse ◄────┴──────────────────┴── refuse ◄────┴───────────────┴── refuse if nothing valid
every call ─► trace (latency, tokens, cost, prompt version) ─► audit log (hash chain, redacted, pseudonymised)
```

- **Extractive mode** (default): quotes the most relevant sentence of the best passages. Free, deterministic,
  cannot invent content, runs in CI and on the free Azure deployment.
- **LLM mode**: Claude (`claude-haiku-5-5` by default) or any OpenAI-compatible endpoint (a local model with
  Ollama), with the versioned prompt `prompts/compliance_answer/v2.yaml`. The model must cite passage ids or
  reply `INSUFFICIENT_CONTEXT`; invented ids are stripped and uncited sentences dropped.

## Quickstart

```bash
pip install -r requirements.txt
python -m pytest -q                         # 71 tests, no network, no API key
python -m ccp.cli pipeline                  # bronze -> silver, data contracts enforced
python -m ccp.cli ask "How fast must a personal data breach be notified under the GDPR?"
python -m ccp.cli eval --gate               # golden set + claims triage + non-regression gate
python -m ccp.cli risk-register             # check evidence and references, render docs
python -m ccp.cli traces                    # latency, cost and refusal summary

# LLM mode (a few cents for the whole golden set with Haiku 5.5)
pip install anthropic && export ANTHROPIC_API_KEY=...
python -m ccp.cli eval --target rag --generator anthropic --gate

# Official texts from EUR-Lex (source of record)
python -m ccp.cli fetch-official            # writes data/corpus/official/*.jsonl
```

API:

```bash
CCP_DEMO_KEYS=1 python -m ccp.cli serve      # http://127.0.0.1:8000/docs
curl -s localhost:8000/ask -H "X-API-Key: demo-analyst" -H "Content-Type: application/json" \
  -d '{"question": "Who is ultimately responsible for ICT risk under DORA?"}'
```

| Role (demo key) | Can | Cannot |
|---|---|---|
| `analyst` (`demo-analyst`) | `POST /ask` | triage, read the audit log |
| `claims_handler` (`demo-claims`) | `POST /triage` | ask, read the audit log |
| `auditor` (`demo-auditor`) | `GET /audit`, `GET /metrics` | ask or triage (separation of duties) |

## Results (extractive generator, sample corpus)

Thresholds were tuned on the `dev` split only. `test` is the number to trust.

| Metric | dev (31) | test (30) |
|---|---|---|
| Retrieval hit rate @4 | 1.00 | 0.96 |
| Answer rate on answerable questions | 1.00 | 0.87 |
| Refusal recall on out-of-scope questions | 1.00 | 0.86 |
| Answer cites an expected passage | 0.96 | 1.00 |
| Key-fact recall | 0.63 | 0.95 |
| End-to-end accuracy | 0.71 | 0.83 |
| Invented citations | 0 | 0 |
| Latency p95 | < 2 ms | < 2 ms |
| Cost | 0 | 0 |

Claims triage, rules reader, 300 synthetic claims (seed 11, not the seed the rules were written on):
category accuracy 0.82, urgency 0.82, route agreement 0.83, **0 claims needing a human sent elsewhere**.

The **LLM column is deliberately empty**: I will not fill it with estimates. The LLM path is covered by tests
with fake clients and by the manual `eval-llm` workflow, which applies the same gate.

### What the errors say (`results/*_errors.jsonl`)

- Three answerable test questions are refused because their wording shares too few terms with the text
  ("talking to a chatbot" vs "interacting with an AI system"). That is the limit of lexical retrieval and the
  first argument for an embedding retriever, which must beat BM25 on this gate to be adopted.
- One out-of-scope question ("ECB interest rate") gets answered from DORA because "financial interests" matches.
  A calibrated refusal on real traffic would need more than 31 dev questions.
- The extractive generator quotes one sentence per passage, so it misses facts spread over two sentences
  (key-fact recall 0.63 on dev). That is what the LLM mode is for.
- Triage: the rules confuse "vol" (flight) with "vol" (theft) and miss reworded claims ("la porte était
  forcée"). The routing policy absorbs these errors on the safe side: every uncertain case goes to a person.

## Governance in short

- **AI Act classification** (`docs/risk_register.md`): the copilot is **not high-risk** (internal support tool,
  not in Annex III) but falls under the transparency duty of Article 50 and the AI literacy duty of Article 4.
  The claims triage is **not high-risk under conditions**: Annex III 5(c) covers life and health insurance
  only, and the system performs a preparatory task without rejecting claims. Extending it to health insurance,
  pricing or automatic rejection would change the classification; the register says so.
- **Dates**: the corpus includes the Digital Omnibus on AI (Regulation (EU) 2026/1744, in force 27 July 2026),
  which moved Annex III obligations to 2 December 2027.
- **Personal data**: raw claims are `restricted` and only the data engineering role reads them; the silver
  contract forbids identifier columns and checks free text; users are pseudonymised in the audit log.
- **Change control**: a prompt is never edited in place; a new version must pass the gate. The model, prompt
  version and prompt hash are recorded in every trace and audit entry.

## Deploy

- **Azure**: `infra/README.md` (Container Apps consumption plan, GitHub OIDC, no stored secret).
  The deploy workflow stays dormant until the repository variable `AZURE_DEPLOY` is `true`.
- **Databricks**: `databricks/README.md` (Free Edition, Git folder, three notebooks).
- **Tracing**: set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`, or any `OTEL_EXPORTER_OTLP_ENDPOINT`.

Free tiers checked on 14 October 2026: Databricks Free Edition (serverless only, fair-use quotas, no commercial
use) and the Azure Container Apps monthly free grant. Check that they still apply to your account.

## Repository map

```
ccp/                 package: corpus, retrieval, rag, triage, contracts, pipeline, tracing, audit, api, eval
contracts/           data contracts (YAML)
config/              retrieval thresholds, model prices
prompts/             versioned prompts
eval/                golden set and gate thresholds
results/             committed evaluation baselines and error files
governance/          risk register and access roles (source)
docs/                model card, generated risk register and data catalog, roadmap deck
databricks/          notebooks for Databricks Free Edition
infra/               Azure setup and deployment guide
```

## Limitations

- Paraphrased sample corpus covering selected articles; the EUR-Lex parser is tested on a fixture that
  mimics EUR-Lex markup, not yet on a live download.
- Lexical retrieval only; no reranker; English questions only.
- Regex anonymisation; pattern-based injection guard. Both are safeguards, not guarantees.
- Synthetic, templated claims; real claims are longer, contradictory and multilingual.
- Tamper-evident audit log, not tamper-proof: production needs WORM storage.

## Next steps

1. Run and record the LLM column; compare cost and latency per question with the extractive floor.
2. Load the official EUR-Lex corpus and re-run the gate on it.
3. Add an embedding retriever behind the same interface and keep it only if it beats BM25 on `test`.
4. French questions (EUR-Lex publishes every act in French).

## En bref (français)

Copilote de conformité (RAG) sur l'AI Act, DORA et le RGPD : réponses citées, refus sans source, et la
gouvernance autour (contrats de données, tests de qualité, évaluation continue en CI, traçage et coût,
journal d'audit, registre des risques classé selon l'AI Act, fiche modèle). Cas d'usage assurance : tri de
réclamations synthétiques qui ne rejette jamais. Feuille de route Data & IA pour une banque fictive dans
`docs/roadmap/`. Données synthétiques, organisations fictives.

## License

MIT
