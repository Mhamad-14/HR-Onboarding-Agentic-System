"""Deterministic, reversible Jinja2 document generation."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .schemas import OnboardingRequest, WorkerResult


class DraftRenderer:
    def __init__(self, template_dir: Path, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.environment = Environment(
            loader=FileSystemLoader(template_dir),
            undefined=StrictUndefined,
            autoescape=select_autoescape(enabled_extensions=("html", "xml")),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _write(self, filename: str, content: str) -> str:
        safe_name = Path(filename).name
        path = self.output_dir / safe_name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def render_case_drafts(
        self,
        request: OnboardingRequest,
        worker_results: dict[str, WorkerResult],
    ) -> list[str]:
        proposed_actions: list[str] = []
        risk_flags: list[str] = []
        sources: list[str] = []
        for result in worker_results.values():
            proposed_actions.extend(result.recommendations)
            risk_flags.extend(result.risk_flags)
            sources.extend(citation.source for citation in result.citations)

        context = request.model_dump(mode="json") | {
            "proposed_actions": proposed_actions,
            "risk_flags": sorted(set(risk_flags)),
            "sources": sorted(set(sources)),
        }
        summary = self.environment.get_template("onboarding_summary.md.j2").render(**context)
        notification = self.environment.get_template("contract_notification.md.j2").render(
            **context
        )
        return [
            self._write(f"{request.case_id}_onboarding_proposal.md", summary),
            self._write(f"{request.case_id}_contract_notification_DRAFT.txt", notification),
        ]
