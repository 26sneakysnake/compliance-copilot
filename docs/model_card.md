# Model card: compliance copilot

Format adapted from Mitchell et al., "Model Cards for Model Reporting" (2019), with the items that
AI Act Article 13 asks providers to give deployers (capabilities, limitations, accuracy metrics,
human oversight, logging). The organisation is **fictional** and all claims data is **synthetic**.

## System overview

| | |
|---|---|
| Name | Compliance copilot, version 0.1.0 |
| Type | Retrieval-augmented generation (RAG) with mandatory citations and refusal without source |
| Components | BM25 retriever (`ccp/retrieval.py`), generator (extractive offline mode or Claude via API), citation validator (`ccp/rag.py`) |
| Default generator | `extractive`: quotes the best sentence of the top passages. Deterministic, free, cannot invent content |
| LLM generator | `claude-haiku-5-5` by default (configurable), prompt `compliance_answer@v2` (`prompts/`) |
| Knowledge | EU AI Act (incl. Digital Omnibus 2026/1744), GDPR, DORA, two EBA guidelines. Sample corpus = paraphrases; official corpus = EUR-Lex texts |
| Companion system | Claims triage (`ccp/triage.py`): rules or LLM reading of the text + deterministic routing policy |
| Owner | AI governance lead (fictional) |

## Intended use

- **Users**: compliance analysts of a fictional bank and insurer.
- **Task**: find the relevant provision quickly and get a short, cited summary to read in the official text.
- **Out of scope**: legal advice; customer-facing use; decisions about individuals; questions on texts not
  in the corpus (MiCA, CRR, Solvency II, NIS2, national law...), which the system is designed to refuse.

## AI Act position

Not high-risk: not an Annex III use case and no product safety function (Article 6). Transparency duties of
Article 50(1) apply: the API states it is an AI system on every response (`X-AI-Generated` header, notice and
disclaimer). AI literacy (Article 4) applies to the staff who use it. Full reasoning in
[`risk_register.md`](risk_register.md).

## Evaluation

Golden set: 61 hand-written questions (`eval/golden_set.yaml`), 47 answerable and 14 that must be refused
(other regulations, off-topic, prompt injection). Thresholds are tuned on the `dev` split only.
Extractive generator, sample corpus, commit of this card:

| Metric | dev (31) | test (30) | all (61) |
|---|---|---|---|
| Retrieval hit rate @4 | 1.00 | 0.96 | 0.98 |
| Mean reciprocal rank | 0.97 | 0.78 | 0.88 |
| Answer rate on answerable questions | 1.00 | 0.87 | 0.94 |
| Refusal recall on unanswerable questions | 1.00 | 0.86 | 0.93 |
| Refusal precision | 1.00 | 0.67 | 0.81 |
| Answer cites an expected passage | 0.96 | 1.00 | 0.98 |
| Key-fact recall | 0.63 | 0.95 | 0.77 |
| End-to-end accuracy | 0.71 | 0.83 | 0.77 |
| Invented citations | 0 | 0 | 0 |

The gap between dev and test on refusal is the honest number to look at: on unseen questions, one
out-of-scope question in seven was answered and three answerable ones were refused (see
`results/rag_extractive_errors.jsonl`). The extractive mode quotes one sentence per passage, which explains
the low key-fact recall on dev; the LLM mode is meant to close that gap and is evaluated with the same gate
(`.github/workflows/eval-llm.yml`). **LLM results are not reported here until that run is done.**

Claims triage (rules reader, 300 synthetic claims, seed 11): category accuracy 0.82, urgency 0.82, route
agreement 0.83, and 100% of the claims that need a human are routed to one (no missed human review).

## Limitations

- The sample corpus is paraphrased and covers selected articles only. Answers point to the official text,
  which remains the only authentic version.
- Lexical retrieval misses questions phrased very differently from the text (e.g. "talking to a chatbot").
- Refusal thresholds are calibrated on 31 questions: they will need recalibration on real traffic.
- Synthetic, templated claims are far easier than real ones; triage numbers say nothing about real performance.
- Redaction is regex-based and misses free-text identifiers; it is a safeguard, not certified anonymisation.

## Human oversight and monitoring

- The copilot never acts: it answers with citations or refuses. The triage never rejects a claim.
- Every request is traced (latency, tokens, cost, prompt version) and logged in a hash-chained audit log
  readable by the auditor role only.
- Any change of model, prompt or corpus must pass the CI evaluation gate before deployment.
