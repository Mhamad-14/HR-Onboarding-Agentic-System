# Security and privacy notes

OnboardAI is a synthetic academic demonstration that starts **after** a person has already been
marked as hired.

- It does not make hiring, salary, termination, legal, or protected-characteristic decisions.
- Protected attributes are not part of the Pydantic input model.
- Résumé text is used only for the current onboarding request and is not written to long-term Store.
- Retrieved text is delimited as untrusted reference data and cannot override system instructions.
- Generated HR documents remain drafts until a human approves them.
- Privileged access is flagged and cannot be approved autonomously.
- Groq and LangSmith keys are read from Colab Secrets/environment variables only.
- `.gitignore` excludes runtime databases, generated drafts, model caches, and secret files.
