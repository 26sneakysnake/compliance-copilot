# Risk register

Generated from `governance/risk_register.yaml` (v1.0.0, last review 2026-10-14). Do not edit by hand: run `python -m ccp.cli risk-register`.

Fictional organisation, synthetic data. Scores are likelihood × impact on 1-5 scales (high ≥ 15, medium ≥ 8).

## AI Act classification of the systems

| System | Role | Classification | Rationale | References |
|---|---|---|---|---|
| **SYS-1** Compliance copilot (RAG question answering) | deployer (and provider of the in-house system) | not high-risk | Not an Annex III use case and not a product safety component. It supports, and does not replace, the assessment of a qualified person. Transparency duties of Article 50(1) still apply because users interact with an AI system, and the AI literacy duty of Article 4 applies to the staff using it. | AI_ACT-6, AI_ACT-50, AI_ACT-4 |
| **SYS-2** Claims triage (property and casualty) | deployer (and provider of the in-house system) | not high-risk, under conditions | Annex III point 5(c) covers risk assessment and pricing for natural persons in life and health insurance only. Routing property and casualty claims is not listed, and the system only performs a preparatory task (Article 6(3)). It never rejects a claim nor sets an indemnity, so no decision is based solely on automated processing (GDPR Article 22). Re-assess before any extension to health insurance, to pricing, or to automatic rejection: each of these would change the classification. | AI_ACT-annex-iii-5, AI_ACT-6, GDPR-22 |

## Risks

| ID | System | Risk | Inherent | Residual | Owner | Status | References |
|---|---|---|---|---|---|---|---|
| R01 | SYS-1 | **Hallucinated or unsupported answer**: The model states an obligation that is not in the regulation, and staff act on it. | 16 (high) | 6 (low) | Product owner, compliance copilot | mitigated | AI_ACT-15, AI_ACT-9 |
| R02 | SYS-1 | **Outdated legal content**: An amendment (for example the Digital Omnibus on AI) changes dates or duties and the corpus is not updated. | 12 (medium) | 6 (low) | Compliance data team | mitigated | AI_ACT-113, AI_ACT_OMNIBUS-summary |
| R03 | SYS-1 | **Users over-rely on the copilot (automation bias)**: Staff copy answers into policies without checking the official text. | 9 (medium) | 6 (low) | Head of compliance (fictional) | partially mitigated (AI literacy training plan not in scope of this repo) | AI_ACT-50, AI_ACT-4, AI_ACT-14 |
| R04 | SYS-1 | **Prompt injection through the question**: A user tries to override the rules to obtain unsupported content or the system prompt. | 6 (low) | 4 (low) | Product owner, compliance copilot | mitigated (pattern-based, not exhaustive) | AI_ACT-15 |
| R05 | SYS-2 | **Personal data sent to the model provider or exposed to analysts**: Names, phone numbers, IBANs or health details in claim texts leave the perimeter or reach unauthorised staff. | 16 (high) | 8 (medium) | Data protection officer (fictional) | partially mitigated (regex redaction misses free-text identifiers) | GDPR-5, GDPR-25, GDPR-32, GDPR-9 |
| R06 | SYS-2 | **A claim that needs a human is fast-tracked**: Injury, an uninhabitable home or fraud signals are missed and the claim is handled as routine. | 12 (medium) | 6 (low) | Head of claims (fictional) | mitigated on synthetic data, to be confirmed on real claims | AI_ACT-14, GDPR-22 |
| R07 | SYS-2 | **Unfair treatment of some customers**: Routing differs by customer group in ways not justified by the claim. | 8 (medium) | 4 (low) | AI governance lead (fictional) | monitored | AI_ACT-10, GDPR-22 |
| R08 | SYS-1 | **No trace of who asked what**: Without logs the bank cannot investigate an incident or show accountability to a supervisor. | 9 (medium) | 2 (low) | Product owner, compliance copilot | mitigated (WORM storage planned for production) | AI_ACT-12, AI_ACT-26, GDPR-5 |
| R09 | SYS-1 | **Third-party model provider outage or change**: The LLM API is unavailable, changes behaviour, or changes price. | 9 (medium) | 4 (low) | IT third-party risk manager (fictional) | mitigated | DORA-28, DORA-30 |

## Controls and evidence

### R01 Hallucinated or unsupported answer

- Answers are generated only from retrieved passages; refusal when no passage scores high enough. Evidence: [`ccp/rag.py`](../ccp/rag.py), [`config/rag.yaml`](../config/rag.yaml), [`tests/test_rag.py`](../tests/test_rag.py)
- Every sentence must cite a retrieved passage; invented citations are stripped, uncited answers refused. Evidence: [`ccp/rag.py`](../ccp/rag.py), [`tests/test_rag.py`](../tests/test_rag.py)
- Golden set with out-of-scope questions; CI fails if refusal recall or citation metrics regress. Evidence: [`eval/golden_set.yaml`](../eval/golden_set.yaml), [`eval/thresholds.yaml`](../eval/thresholds.yaml), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

### R02 Outdated legal content

- Corpus versioned under a data contract with a quarterly review SLA and a last_reviewed date. Evidence: [`contracts/regulatory_chunks.yaml`](../contracts/regulatory_chunks.yaml), [`data/corpus/sample_corpus.yaml`](../data/corpus/sample_corpus.yaml)
- Official texts re-fetched from EUR-Lex with source links kept on every chunk. Evidence: [`ccp/eurlex.py`](../ccp/eurlex.py), [`tests/test_eurlex.py`](../tests/test_eurlex.py)

### R03 Users over-rely on the copilot (automation bias)

- Disclaimer and AI disclosure on every answer and every HTTP response. Evidence: [`ccp/rag.py`](../ccp/rag.py), [`ccp/api.py`](../ccp/api.py), [`tests/test_api.py`](../tests/test_api.py)
- Model card states intended use, limits and that answers are not legal advice. Evidence: [`docs/model_card.md`](../docs/model_card.md)

### R04 Prompt injection through the question

- Input guard refuses instruction-override patterns; the prompt instructs the model to ignore them. Evidence: [`ccp/rag.py`](../ccp/rag.py), [`prompts/compliance_answer/v2.yaml`](../prompts/compliance_answer/v2.yaml), [`tests/test_rag.py`](../tests/test_rag.py)
- Adversarial items in the golden set. Evidence: [`eval/golden_set.yaml`](../eval/golden_set.yaml)

### R05 Personal data sent to the model provider or exposed to analysts

- Redaction of identifiers before any model call and in the silver layer; customer ids pseudonymised. Evidence: [`ccp/redact.py`](../ccp/redact.py), [`ccp/pipeline.py`](../ccp/pipeline.py), [`tests/test_redact.py`](../tests/test_redact.py)
- Silver data contract forbids identifier columns and checks free text for personal data patterns. Evidence: [`contracts/claims_silver.yaml`](../contracts/claims_silver.yaml), [`tests/test_contracts.py`](../tests/test_contracts.py)
- Raw claims readable only by the data engineering role; API roles never see bronze data. Evidence: [`governance/access_roles.yaml`](../governance/access_roles.yaml), [`databricks/03_gold_and_governance.py`](../databricks/03_gold_and_governance.py)

### R06 A claim that needs a human is fast-tracked

- Deterministic routing policy; high urgency, review signals and unreadable input always go to human review. Evidence: [`ccp/triage.py`](../ccp/triage.py), [`tests/test_triage.py`](../tests/test_triage.py)
- CI gate requires human_review_recall = 1.0 and zero missed human reviews on the evaluation set. Evidence: [`eval/thresholds.yaml`](../eval/thresholds.yaml), [`ccp/eval/metrics.py`](../ccp/eval/metrics.py)

### R07 Unfair treatment of some customers

- No customer attributes are used by the triage; only the claim text, amount and dates. Evidence: [`ccp/triage.py`](../ccp/triage.py)
- Re-classification trigger documented if the scope extends to health insurance or pricing. Evidence: [`governance/risk_register.yaml`](../governance/risk_register.yaml)

### R08 No trace of who asked what

- Hash-chained audit log of every question and triage, with pseudonymised users and redacted text. Evidence: [`ccp/audit.py`](../ccp/audit.py), [`tests/test_audit.py`](../tests/test_audit.py)
- Traces with latency, tokens, cost and prompt version, exportable over OpenTelemetry. Evidence: [`ccp/tracing.py`](../ccp/tracing.py), [`tests/test_tracing.py`](../tests/test_tracing.py)

### R09 Third-party model provider outage or change

- Extractive offline mode as fallback; model and prompt pinned and recorded in every trace. Evidence: [`ccp/rag.py`](../ccp/rag.py), [`ccp/prompts.py`](../ccp/prompts.py), [`config/pricing.yaml`](../config/pricing.yaml)
- Evaluation must be re-run and pass the gate before any model or prompt change. Evidence: [`eval/thresholds.yaml`](../eval/thresholds.yaml), [`.github/workflows/eval-llm.yml`](../.github/workflows/eval-llm.yml)
