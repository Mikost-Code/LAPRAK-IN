"""Structured outputs the browser must return. Everything the model says is validated here before storage."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RESULTS = ("unknown", "success", "failed", "partial")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fact(Strict):
    type: str = Field(description="Kategori singkat, misalnya 'perintah', 'nilai', 'status'.")
    value: str
    source: Literal["visible", "user_note", "document"] = "visible"
    reviewed: bool = False


class EvidenceAnalysis(Strict):
    """Facts visible in the images of one step."""
    facts: list[Fact] = Field(default_factory=list)
    narrative: str = ""
    unknown: list[str] = Field(default_factory=list)
    result: Literal["unknown", "success", "failed", "partial"] = "unknown"


class StepDescription(Strict):
    """Report-ready description of one step."""
    narrative: str
    caption_suggestions: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)


class OutlineStep(Strict):
    title: str
    instruction: str = ""
    page: int | None = None
    needs_evidence: bool = True


class DocumentOutline(Strict):
    """Structure extracted from an optional source document (module, SOP, brief)."""
    title: str = ""
    objectives: list[str] = Field(default_factory=list)
    theory: str = ""
    tools: list[str] = Field(default_factory=list)
    steps: list[OutlineStep] = Field(default_factory=list)
    unknown_pages: list[int] = Field(default_factory=list)


class Assignment(Strict):
    evidence_id: str
    step_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


class ProposedStep(Strict):
    title: str
    evidence_ids: list[str]


class EvidenceMatch(Strict):
    """Which image belongs to which step, in which order."""
    assignments: list[Assignment] = Field(default_factory=list)
    proposed_steps: list[ProposedStep] = Field(default_factory=list)


class SectionDraft(Strict):
    content: str
    sources: list[str] = Field(default_factory=list, description="ID langkah yang dipakai sebagai dasar.")


class SlotGuess(Strict):
    slot: str
    file: str
    line: int | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


class TemplateSlots(Strict):
    """Where identity, documentation, and narrative sections live inside a LaTeX template."""
    identity_commands: dict[str, str] = Field(default_factory=dict, description="command -> makna (name, nim, title, ...)")
    slots: list[SlotGuess] = Field(default_factory=list)


class ConnectionProbe(Strict):
    echo: str
    image_text: str = ""


SCHEMAS: dict[str, type[Strict]] = {
    "analyze_evidence": EvidenceAnalysis,
    "describe_step": StepDescription,
    "outline_document": DocumentOutline,
    "match_evidence": EvidenceMatch,
    "draft_section": SectionDraft,
    "scan_template": TemplateSlots,
    "probe": ConnectionProbe,
}
