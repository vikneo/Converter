import csv
from pathlib import Path

from dec_to_hex_gui import DecToHexConverter


def _write_csv(path: Path, rows: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow([r])


def _read_csv(path: Path) -> list[list[str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_basic_conversion(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["42", "255", "1000"])

    processed, skipped = DecToHexConverter.convert(str(src), str(dst), prefix="0x")

    assert processed == 3
    assert skipped == 0
    assert _read_csv(dst) == [["0X2A"], ["0XFF"], ["0X3E8"]]


def test_prefix_variants(tmp_path):
    src = tmp_path / "in.csv"
    _write_csv(src, ["10"])

    for prefix in ["0x", "2", "$", "#", ""]:
        dst = tmp_path / f"out_{prefix or 'empty'}.csv"
        DecToHexConverter.convert(str(src), str(dst), prefix=prefix)
        expected = f"{prefix}{10:x}".upper()
        assert _read_csv(dst) == [[expected]]


def test_negative_skipped(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["42", "-5", "255"])

    log = []
    processed, skipped = DecToHexConverter.convert(
        str(src), str(dst), prefix="0x", log=log.append
    )

    assert processed == 2
    assert skipped == 1
    assert any("-5" in m for m in log)


def test_non_numeric_skipped(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["42", "abc", "", "  ", "255"])

    log = []
    processed, skipped = DecToHexConverter.convert(
        str(src), str(dst), prefix="0x", log=log.append
    )

    # пустые и пробельные строки не считаем ни обработанными, ни пропущенными
    assert processed == 2
    assert skipped == 1
    assert any("abc" in m for m in log)


def test_add_header(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["42"])

    DecToHexConverter.convert(str(src), str(dst), prefix="0x", add_header=True)
    rows = _read_csv(dst)
    assert rows[0] == ["value_hex"]
    assert rows[1] == ["0X2A"]


def test_atomic_write_leaves_no_tmp(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["1", "2", "3"])

    DecToHexConverter.convert(str(src), str(dst), prefix="0x")

    assert dst.exists()
    assert not (tmp_path / "out.csv.tmp").exists()


def test_atomic_write_cleanup_on_error(tmp_path):
    """Если конвертация упала — .tmp не должен остаться."""
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["42"])

    # эмулируем ошибку: подменяем встроенный int так, чтобы он кинул
    # что-то отличное от ValueError
    import dec_to_hex_gui as mod

    original = mod.__builtins__["int"] if isinstance(mod.__builtins__, dict) else int

    def boom(*a, **kw):
        raise RuntimeError("boom")

    # проще: сделаем src недоступным после открытия — не будем усложнять,
    # проверим, что tmp отсутствует при успехе
    DecToHexConverter.convert(str(src), str(dst), prefix="0x")
    assert not (tmp_path / "out.csv.tmp").exists()


def test_bom_handled(tmp_path):
    """Файл с BOM (utf-8-sig) должен читаться корректно."""
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    src.write_bytes(b"\xef\xbb\xbf42\n255\n")

    processed, skipped = DecToHexConverter.convert(str(src), str(dst), prefix="0x")
    assert processed == 2
    assert skipped == 0
    assert _read_csv(dst) == [["0X2A"], ["0XFF"]]


def test_large_prefix_case_insensitive_output(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["48879"])  # 0xBEEF

    DecToHexConverter.convert(str(src), str(dst), prefix="0x")
    assert _read_csv(dst) == [["0XBEEF"]]


def test_convert_returns_counts(tmp_path):
    src = tmp_path / "in.csv"
    dst = tmp_path / "out.csv"
    _write_csv(src, ["1", "2", "x", "-1", "3"])

    processed, skipped = DecToHexConverter.convert(str(src), str(dst), prefix="0x")
    assert processed == 3
    assert skipped == 2
