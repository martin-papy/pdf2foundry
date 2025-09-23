from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)


class ProgressReporter:
    """Render multi-step progress for the conversion pipeline using Rich.

    This class consumes on_progress(event, payload) callbacks from pipeline
    components and updates progress bars accordingly.
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            transient=False,
            console=self.console,
        )
        self._tasks: dict[str, TaskID] = {}
        self._totals: dict[str, int] = {}

    # Context manager API
    def __enter__(self) -> ProgressReporter:
        self.progress.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        # Progress.__exit__ has a compatible signature at runtime
        self.progress.__exit__(exc_type, exc, tb)

    # Public helper for callers to create ad-hoc tasks (e.g., writing files)
    def add_step(self, description: str, total: int | None) -> TaskID:
        return self.progress.add_task(description, total=total)

    def finish_task(self, task_id: TaskID) -> None:
        with suppress(Exception):
            self.progress.remove_task(task_id)

    # Callback entry point
    def emit(self, event: str, payload: dict[str, int | str]) -> None:
        try:
            handler = getattr(self, f"_on_{event.replace(':', '_')}", None)
            if callable(handler):
                handler(payload)
        except Exception:
            # Never break the pipeline because of UI errors
            pass

    # Event handlers (docling_parser)
    def _on_load_pdf(self, payload: dict[str, Any]) -> None:
        # Create a spinner task immediately when load begins
        if "load" not in self._tasks:
            self._tasks["load"] = self.add_step("Loading PDF", total=None)

    def _on_load_pdf_success(self, payload: dict[str, Any]) -> None:
        self._finalize_task("load")

    def _on_extract_bookmarks_start(self, payload: dict[str, Any]) -> None:
        # Close loading spinner and show outline detection immediately
        self._finalize_task("load")
        # Placeholder spinner while detecting outline
        if "outline" not in self._tasks:
            self._tasks["outline"] = self.add_step("Detecting outline", total=None)

    def _on_extract_bookmarks_success(self, payload: dict[str, Any]) -> None:
        # Initialize chapter/section totals
        chapters = int(payload.get("chapters", 0) or 0)
        sections = int(payload.get("sections", 0) or 0)
        self._finalize_task("outline")
        if chapters and "chapters" not in self._tasks:
            self._tasks["chapters"] = self.add_step("Chapters", total=chapters)
            self._totals["chapters"] = chapters
        if sections and "sections" not in self._tasks:
            self._tasks["sections"] = self.add_step("Sections", total=sections)
            self._totals["sections"] = sections

    def _on_extract_bookmarks_empty(self, payload: dict[str, Any]) -> None:
        # No outline; will fallback to heuristics
        self._finalize_task("outline")

    def _on_heuristics_start(self, payload: dict[str, Any]) -> None:
        if "heuristics" not in self._tasks:
            self._tasks["heuristics"] = self.add_step("Detecting headings", total=None)

    def _on_heuristics_detected(self, payload: dict[str, Any]) -> None:
        self._finalize_task("heuristics")
        chapters = int(payload.get("chapters", 0) or 0)
        sections = int(payload.get("sections", 0) or 0)
        if chapters and "chapters" not in self._tasks:
            self._tasks["chapters"] = self.add_step("Chapters", total=chapters)
            self._totals["chapters"] = chapters
        if sections and "sections" not in self._tasks:
            self._tasks["sections"] = self.add_step("Sections", total=sections)
            self._totals["sections"] = sections

    def _on_outline_finalized(self, payload: dict[str, Any]) -> None:
        self._finalize_task("outline")

    # Event handlers (content_extractor)
    def _on_content_start(self, payload: dict[str, Any]) -> None:
        pages = int(payload.get("page_count", 0) or 0)
        if pages and "pages" not in self._tasks:
            self._tasks["pages"] = self.add_step("Pages", total=pages)
            self._totals["pages"] = pages

    def _on_page_exported(self, payload: dict[str, Any]) -> None:
        t = self._tasks.get("pages")
        if t is not None:
            self.progress.advance(t, 1)

    def _on_content_finalized(self, payload: dict[str, Any]) -> None:
        self._finalize_task("pages")

    # Event handlers (ir_builder)
    def _on_ir_start(self, payload: dict[str, Any]) -> None:
        if "ir" not in self._tasks:
            self._tasks["ir"] = self.add_step("Building IR", total=None)

    def _on_chapter_assembled(self, payload: dict[str, Any]) -> None:
        t = self._tasks.get("chapters")
        if t is not None:
            self.progress.advance(t, 1)

    def _on_section_assembled(self, payload: dict[str, Any]) -> None:
        t = self._tasks.get("sections")
        if t is not None:
            self.progress.advance(t, 1)

    def _on_ir_finalized(self, payload: dict[str, Any]) -> None:
        # Ensure any remaining counters are completed before closing IR step
        self._finalize_task("chapters")
        self._finalize_task("sections")
        self._finalize_task("ir")

    # Event handlers (ingestion)
    def _on_ingest_converting(self, payload: dict[str, Any]) -> None:
        if "conversion" not in self._tasks:
            pdf_name = Path(str(payload.get("pdf", "PDF"))).name
            self._tasks["conversion"] = self.add_step(f"Converting {pdf_name}", total=None)

    def _on_ingest_converted(self, payload: dict[str, Any]) -> None:
        self._finalize_task("conversion")

    def _on_ingest_conversion_failed(self, payload: dict[str, Any]) -> None:
        self._finalize_task("conversion")

    def _on_ingest_loaded_from_cache(self, payload: dict[str, Any]) -> None:
        if "conversion" not in self._tasks:
            cache_name = Path(str(payload.get("path", "cache"))).name
            self._tasks["conversion"] = self.add_step(f"Loaded from {cache_name}", total=None)
        self._finalize_task("conversion")

    def _on_ingest_cache_load_failed(self, payload: dict[str, Any]) -> None:
        # Show brief feedback that cache failed and we're falling back
        if "conversion" not in self._tasks:
            self._tasks["conversion"] = self.add_step("Cache failed, converting PDF", total=None)

    def _on_ingest_saved_to_cache(self, payload: dict[str, Any]) -> None:
        # Show brief feedback that cache was saved successfully
        cache_name = Path(str(payload.get("path", "cache"))).name
        if "cache_save" not in self._tasks:
            task_id = self.add_step(f"Saved to {cache_name}", total=None)
            # Immediately complete this task since save is done
            self.finish_task(task_id)

    # Utilities
    def _finalize_task(self, key: str) -> None:
        task_id = self._tasks.get(key)
        if task_id is None:
            return
        # If task has a known total, mark done; otherwise remove spinner task
        total = self._totals.get(key)
        if total is not None:
            with suppress(Exception):
                self.progress.update(task_id, completed=total, total=total)
        else:
            with suppress(Exception):
                self.progress.remove_task(task_id)
        # Hide task from mapping so it can be recreated later if needed
        self._tasks.pop(key, None)
