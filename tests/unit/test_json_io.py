from __future__ import annotations

from pathlib import Path

from pdf2foundry.ingest.json_io import atomic_write_text, doc_from_json, doc_to_json


class _NativeDoc:
    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def to_json(self) -> dict[str, object]:
        # Return a dict with unsorted keys to test determinism
        return self._data


class _FallbackDoc:
    def __init__(self, pages: int) -> None:
        self._pages = pages

    def num_pages(self) -> int:
        return self._pages


def test_doc_to_json_native_is_deterministic() -> None:
    d = _NativeDoc({"b": 1, "a": 2})
    j1 = doc_to_json(d, pretty=True)
    j2 = doc_to_json(d, pretty=True)
    assert j1 == j2
    # Sorted keys expected
    assert j1.index('\n  "a"') < j1.index('\n  "b"')


def test_doc_to_json_fallback_is_deterministic() -> None:
    d = _FallbackDoc(3)
    j1 = doc_to_json(d, pretty=True)
    j2 = doc_to_json(d, pretty=True)
    assert j1 == j2
    assert '"num_pages": 3' in j1


def test_doc_to_json_native_string_wrapped_when_not_json() -> None:
    class _NativeStringDoc:
        def to_json(self) -> str:
            return "not-a-json-string"

    d = _NativeStringDoc()
    j = doc_to_json(d)
    # Expect wrapper key present
    assert '"_native"' in j


def test_doc_to_json_native_raises_falls_back() -> None:
    class _NativeRaises:
        def to_json(self) -> str:
            raise RuntimeError("boom")

    d = _NativeRaises()
    j = doc_to_json(d)
    assert '"schema_version"' in j and '"num_pages"' in j


def test_doc_from_json_fallback_sets_num_pages() -> None:
    text = '{"num_pages": 5}'
    doc = doc_from_json(text)
    assert doc.num_pages() == 5


def test_doc_to_json_pretty_flag_controls_indentation() -> None:
    d = _FallbackDoc(2)
    pretty = doc_to_json(d, pretty=True)
    compact = doc_to_json(d, pretty=False)
    assert "\n" in pretty
    assert "\n" not in compact


def test_atomic_write_text(tmp_path: Path) -> None:
    path = tmp_path / "file.json"
    data = '{"k": 1}'
    atomic_write_text(path, data)
    assert path.exists()
    assert path.read_text(encoding="utf-8") == data
