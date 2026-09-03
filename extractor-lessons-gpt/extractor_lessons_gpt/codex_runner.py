from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .config import Settings
from .page_prompt import build_page_prompt


class CodexError(RuntimeError):
    pass


class CodexRateLimitError(CodexError):
    pass


_TRANSIENT_PATTERNS = re.compile(
    r"(429|404|rate.?limit|too many requests|quota|capacity|overloaded|"
    r"reconnecting|temporarily unavailable|timeout|connection reset|"
    r"unexpected status|did not write output|empty output)",
    re.IGNORECASE,
)


def _is_transient_error(detail: str) -> bool:
    return bool(_TRANSIENT_PATTERNS.search(detail or ""))


class CodexRunner:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.codex_bin.is_file():
            raise FileNotFoundError(
                f"Codex binary not found at {settings.codex_bin}. "
                "Install ChatGPT.app or set CODEX_BIN in .env"
            )
        if not settings.page_schema.is_file():
            raise FileNotFoundError(f"Output schema not found: {settings.page_schema}")

    def extract_page(
        self,
        *,
        page_number: int,
        image_path: Path,
        work_dir: Path,
        language_hint: str = "Arabic and English textbook content",
    ) -> dict:
        last_error = ""
        for attempt in range(1, self.settings.codex_max_retries + 1):
            try:
                return self._extract_page_once(
                    page_number=page_number,
                    image_path=image_path,
                    work_dir=work_dir,
                    language_hint=language_hint,
                )
            except CodexError as exc:
                last_error = str(exc)
                if attempt >= self.settings.codex_max_retries or not _is_transient_error(last_error):
                    raise
                delay = min(
                    self.settings.codex_retry_base_seconds * (2 ** (attempt - 1)),
                    self.settings.codex_retry_max_seconds,
                )
                print(
                    f"Codex transient error on page {page_number} "
                    f"(attempt {attempt}/{self.settings.codex_max_retries}). "
                    f"Waiting {delay:.0f}s before retry..."
                )
                time.sleep(delay)
        raise CodexRateLimitError(
            f"Codex failed for page {page_number} after {self.settings.codex_max_retries} retries.\n{last_error}"
        )

    def _extract_page_once(
        self,
        *,
        page_number: int,
        image_path: Path,
        work_dir: Path,
        language_hint: str,
    ) -> dict:
        prompt = build_page_prompt(page_number=page_number, language_hint=language_hint)

        work_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix=f"codex_page_{page_number:04d}_",
            delete=False,
            dir=work_dir,
        ) as handle:
            output_path = Path(handle.name)

        cmd = [
            str(self.settings.codex_bin),
            "exec",
            "--skip-git-repo-check",
            "-C",
            str(work_dir),
            "--add-dir",
            str(image_path.parent),
            "--ephemeral",
            "--output-schema",
            str(self.settings.page_schema),
            "-o",
            str(output_path),
            prompt,
        ]
        if self.settings.codex_model:
            cmd.extend(["-m", self.settings.codex_model])
        cmd.extend(["-i", str(image_path)])

        try:
            completed = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise CodexError(f"Failed to launch Codex: {exc}") from exc

        detail = "\n".join(part for part in (completed.stderr, completed.stdout) if part).strip()
        if completed.returncode != 0:
            raise CodexError(
                f"Codex failed for page {page_number} (exit {completed.returncode}).\n{detail}"
            )

        if not output_path.is_file():
            raise CodexError(
                f"Codex did not write output for page {page_number} "
                f"(expected {output_path}).\n{detail}"
            )

        raw = output_path.read_text(encoding="utf-8").strip()
        output_path.unlink(missing_ok=True)
        if not raw:
            raise CodexError(f"Codex returned empty output for page {page_number}.\n{detail}")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CodexError(
                f"Codex output was not valid JSON for page {page_number}: {raw[:400]}"
            ) from exc

        data.setdefault("pdf_page_number", page_number)
        return data
