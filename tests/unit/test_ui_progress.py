from __future__ import annotations

from pdf2foundry.ui.progress import ProgressReporter


def test_progress_pages_flow() -> None:
    with ProgressReporter() as pr:
        pr.emit("content:start", {"page_count": 3})
        assert "pages" in pr._tasks
        assert pr._totals.get("pages") == 3
        pr.emit("page:exported", {"page_no": 1})
        pr.emit("page:exported", {"page_no": 2})
        pr.emit("page:exported", {"page_no": 3})
        pr.emit("content:finalized", {"pages": 3})
        # pages task finalized and removed
        assert "pages" not in pr._tasks


def test_progress_outline_and_counts() -> None:
    with ProgressReporter() as pr:
        pr.emit("extract_bookmarks:start", {"page_count": 10})
        pr.emit("extract_bookmarks:success", {"chapters": 2, "sections": 3})
        # tasks created for chapters and sections
        assert "chapters" in pr._tasks
        assert pr._totals.get("chapters") == 2
        assert "sections" in pr._tasks
        assert pr._totals.get("sections") == 3
        # advance counts
        pr.emit("chapter:assembled", {"chapter": "A"})
        pr.emit("chapter:assembled", {"chapter": "B"})
        pr.emit("section:assembled", {"chapter": "A", "section": "s1"})
        pr.emit("section:assembled", {"chapter": "A", "section": "s2"})
        pr.emit("section:assembled", {"chapter": "B", "section": "s3"})
        # finalize outline spinner
        pr.emit("outline:finalized", {"nodes": 5})


def test_progress_ir_finalize() -> None:
    with ProgressReporter() as pr:
        pr.emit("ir:start", {"doc_title": "D"})
        assert "ir" in pr._tasks
        pr.emit("ir:finalized", {"chapters": 0, "sections": 0})
        assert "ir" not in pr._tasks


def test_progress_heuristics_path() -> None:
    with ProgressReporter() as pr:
        pr.emit("extract_bookmarks:empty", {"page_count": 10})
        pr.emit("heuristics:start", {"page_count": 10})
        pr.emit("heuristics:detected", {"chapters": 1, "sections": 1})
        assert "chapters" in pr._tasks
        assert "sections" in pr._tasks
