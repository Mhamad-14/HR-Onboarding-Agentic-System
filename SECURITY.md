# Security, privacy, and responsible-use notes

## Intended use

OnboardAI is a synthetic academic demonstration of post-hire administration. It is not an applicant
tracking system, employment decision system, legal document generator, or production identity
provider.

## Threats and controls

| Threat | Control |
|---|---|
| API-key disclosure | Environment variables/Colab Secrets, `.env` ignored, `.env.example` empty |
| Prompt injection in résumé/policies | Retrieved text delimited and labelled untrusted; system instructions forbid following it |
| Protected-trait discrimination | No protected fields; Pydantic rejects unknown fields; prompts prohibit inference |
| Hallucinated policy or course | Approved RAG sources and citations; mandatory items are retrieved deterministically |
| Excessive IT privilege | Approved role matrix, risk flags, least privilege, human approval |
| Unapproved communication | Jinja2 files are labelled DRAFT; no email-sending integration |
| Duplicate side effects on resume | Side effects live in `@task`; IT ticket uses unique `case_id` upsert |
| Hidden unexpected failures | Anticipated errors handled explicitly; unexpected exceptions bubble up |
| Sensitive long-term memory | Store contains only safe language/training preferences and completion status |

## Data policy

- Use only the included synthetic profiles or properly anonymized replacements.
- Never put national identifiers, banking data, medical information, or private employee records in
  the repository, prompt traces, or Store.
- LangSmith traces can contain prompts. Do not run real employee data with tracing enabled.
- Draft and database runtime artifacts are ignored by Git.

## Secret incident procedure

If a key is ever committed, deleting the line is insufficient. Revoke it at the provider, create a
new key, remove the credential from Git history using an approved history-rewrite procedure, and
verify the repository before sharing it.

