from __future__ import annotations

import json
from pathlib import Path

from .config import settings
from .pdf_reader import PageData
from .prompts import (
    VISUAL_SYSTEM,
    VISUAL_VERIFY_SYSTEM,
    visual_asset_prompt,
    visual_verify_prompt,
)
from .schemas import BookMetadata, ExtractedBlock, HierarchyContext, VisualAnalysis, VisualVerification
from .vlm_client import OpenAICompatibleVLM


class UniversalVisualAnalyzer:
    """Deep, open-ended analysis of any cropped educational visual asset."""

    def __init__(self, vlm: OpenAICompatibleVLM, output_dir: Path):
        self.vlm = vlm
        self.output_dir = output_dir
        self.analysis_dir = output_dir / "asset_analysis"
        self.verification_dir = output_dir / "asset_verification"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.verification_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def image_data_url(path: Path) -> str:
        import base64

        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        suffix = path.suffix.lower()
        mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
        return f"data:{mime};base64,{b64}"

    def analyze(
        self,
        *,
        asset_id: str,
        crop_path: Path,
        page: PageData,
        printed_page_number: str | None,
        block: ExtractedBlock,
        metadata: BookMetadata,
        hierarchy: HierarchyContext,
        context: str,
        resume: bool = True,
    ) -> VisualAnalysis:
        analysis_path = self.analysis_dir / f"{asset_id}.json"
        if resume and analysis_path.exists():
            try:
                return VisualAnalysis.model_validate_json(analysis_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        retry_feedback: str | None = None
        final_analysis: VisualAnalysis | None = None
        for attempt in range(settings.max_visual_retries + 1):
            enriched_context = (
                f"Hierarchy: unit={hierarchy.unit_title}; chapter={hierarchy.chapter_title}; "
                f"lesson={hierarchy.lesson_title}; section={hierarchy.section_title}\n" + context
            )
            raw = self.vlm.chat_json(
                VISUAL_SYSTEM,
                visual_asset_prompt(
                    asset_id=asset_id,
                    broad_type=block.content_type.value,
                    page_number=page.pdf_page_number,
                    printed_page_number=printed_page_number,
                    block_title=block.title,
                    block_caption=block.caption,
                    block_text=block.verbatim_text,
                    context=enriched_context,
                    book_meta=metadata.model_dump(),
                    retry_feedback=retry_feedback,
                ),
                [self.image_data_url(crop_path)],
            )
            analysis = VisualAnalysis.model_validate(raw)

            if settings.verify_visual_analysis:
                verification = self.verify(asset_id, crop_path, analysis, enriched_context)
                analysis.verification = verification
            else:
                analysis.verification = VisualVerification(status="unverified", confidence=0.0)

            final_analysis = analysis
            if analysis.verification.status not in {"needs_retry", "failed"}:
                break
            retry_feedback = "\n".join(
                analysis.verification.unsupported_claims
                + analysis.verification.contradictions
                + analysis.verification.notes
            )[:8000]

        assert final_analysis is not None
        analysis_path.write_text(final_analysis.model_dump_json(indent=2), encoding="utf-8")
        return final_analysis

    def verify(self, asset_id: str, crop_path: Path, analysis: VisualAnalysis, context: str) -> VisualVerification:
        raw = self.vlm.chat_json(
            VISUAL_VERIFY_SYSTEM,
            visual_verify_prompt(asset_id, analysis.model_dump(mode="json"), context),
            [self.image_data_url(crop_path)],
        )
        verification = VisualVerification.model_validate(raw)
        (self.verification_dir / f"{asset_id}.json").write_text(
            verification.model_dump_json(indent=2), encoding="utf-8"
        )
        return verification
