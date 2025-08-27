from pdf2foundry.ids import compute_deterministic_id


def test_compute_deterministic_id_stability() -> None:
    a = compute_deterministic_id("mod-x", "ch/01", "sec/02")
    b = compute_deterministic_id("mod-x", "ch/01", "sec/02")
    assert a == b
    assert len(a) == 16


def test_compute_deterministic_id_without_section() -> None:
    a = compute_deterministic_id("mod-x", "ch/01")
    b = compute_deterministic_id("mod-x", "ch/01")
    assert a == b
    assert len(a) == 16
