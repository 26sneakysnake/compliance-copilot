# Data catalog

Generated from `contracts/*.yaml` and `governance/access_roles.yaml` by `python -m ccp.cli risk-register`. Fictional organisation, synthetic data.

| Dataset | Databricks table | Classification | Personal data | Owner | Contract |
|---|---|---|---|---|---|
| claims_raw | `workspace.compliance_copilot.bronze_claims_raw` | restricted | True | claims-operations (fictional) | v1.0.0 |
| claims_silver | `workspace.compliance_copilot.silver_claims` | internal | pseudonymised | claims-operations (fictional) | v1.0.0 |
| regulatory_chunks | `workspace.compliance_copilot.silver_regulatory_chunks` | public | False | compliance-data-team (fictional) | v1.1.0 |

## claims_raw

Claims declared by policyholders of the fictional insurer "Assurances du Vexin". Contains direct identifiers and possibly health data in free text (travel cancellations for illness), so access is restricted and the table never leaves the bronze layer.

Legal basis: performance of the insurance contract (GDPR Art. 6(1)(b)). 
Retention: 5 years after claim closure (illustrative).

| Column | Type | Required | Rules | Personal data |
|---|---|---|---|---|
| `claim_id` | string | yes | pattern=^CLM-\d{4}-\d{6}$; unique |  |
| `policy_id` | string | yes | pattern=^POL-\d{6}$ |  |
| `insurer` | string | yes |  |  |
| `customer_name` | string | yes |  | direct |
| `customer_email` | string | yes | pattern=^[^@\s]+@example\.org$ | direct |
| `customer_phone` | string | yes |  | direct |
| `iban` | string | yes |  | direct |
| `line_of_business` | string | yes | enum=['auto', 'home', 'liability', 'travel'] |  |
| `channel` | string | yes | enum=['web', 'phone', 'agent'] |  |
| `policy_start_date` | date | yes |  |  |
| `incident_date` | date | yes |  |  |
| `report_date` | date | yes |  |  |
| `amount_claimed_eur` | float | yes | min=0; max=1000000 |  |
| `description` | string | yes | min_length=10 |  |
| `is_synthetic` | boolean | yes | equals=True |  |

## claims_silver

Claims after anonymisation: direct identifiers removed or pseudonymised, free text redacted. Pseudonymised data is still personal data under the GDPR (Art. 4(5)), so the table is internal, not public. This is the only claims table the copilot and analysts may read.

Retention: 5 years after claim closure (illustrative).

| Column | Type | Required | Rules | Personal data |
|---|---|---|---|---|
| `claim_id` | string | yes | pattern=^CLM-\d{4}-\d{6}$; unique |  |
| `customer_pseudo_id` | string | yes | pattern=^psd_[0-9a-f]{16}$ |  |
| `line_of_business` | string | yes | enum=['auto', 'home', 'liability', 'travel'] |  |
| `channel` | string | yes | enum=['web', 'phone', 'agent'] |  |
| `policy_start_date` | date | yes |  |  |
| `incident_date` | date | yes |  |  |
| `report_date` | date | yes |  |  |
| `report_delay_days` | integer | yes | min=0 |  |
| `amount_claimed_eur` | float | yes | min=0 |  |
| `description_redacted` | string | yes | no personal data pattern |  |
| `is_synthetic` | boolean | yes | equals=True |  |

Forbidden columns: customer_name, customer_email, customer_phone, iban.

## regulatory_chunks

One row per article (or article part) of a regulatory text. Source of record is EUR-Lex or the EBA website. The committed sample corpus contains paraphrases (text_type = paraphrase) for offline testing only.

Retention: keep until superseded by a newer version of the act.

| Column | Type | Required | Rules | Personal data |
|---|---|---|---|---|
| `chunk_id` | string | yes | pattern=^[A-Z][A-Z_]+-[a-z0-9]+(?:-[a-z0-9]+)*$; unique |  |
| `regulation` | string | yes | enum=['AI_ACT', 'AI_ACT_OMNIBUS', 'GDPR', 'DORA', 'EBA_GL_ICT', 'EBA_GL_OUTSOURCING'] |  |
| `celex` | string | yes |  |  |
| `article` | string | yes |  |  |
| `title` | string | yes | min_length=3 |  |
| `text` | string | yes | min_length=80 |  |
| `source_url` | string | yes | pattern=^https://(eur-lex\.europa\.eu¦www\.eba\.europa\.eu)/ |  |
| `text_type` | string | yes | enum=['paraphrase', 'official'] |  |
| `language` | string | yes | enum=['en', 'fr'] |  |

## Access by role

| Role | API permissions | Databricks privileges |
|---|---|---|
| analyst | ask | silver_regulatory_chunks: SELECT; gold_eval_runs: SELECT |
| claims_handler | triage | silver_claims: SELECT; gold_claims_triage: SELECT |
| auditor | read_audit, read_metrics | gold_eval_runs: SELECT; gold_claims_triage: SELECT; audit_log: SELECT |
| data_engineer | - | bronze_claims_raw: SELECT, MODIFY; silver_claims: SELECT, MODIFY; silver_regulatory_chunks: SELECT, MODIFY |
