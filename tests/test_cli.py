import json
from pathlib import Path

import pytest

from cachemaxxing.cli import main
from cachemaxxing.usage import record


def write(path: Path, obj: object) -> str:
    path.write_text(json.dumps(obj))
    return str(path)


def test_diff_exit_codes_and_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = write(tmp_path / "a.json", {"model": "m", "system": "Now: 2026-10-30T10:00:00Z"})
    b = write(tmp_path / "b.json", {"model": "m", "system": "Now: 2026-10-30T10:05:00Z"})
    assert main(["diff", a, b]) == 1
    assert "timestamp" in capsys.readouterr().out
    assert main(["diff", a, a]) == 0


def anthropic_resp(read: int) -> dict[str, object]:
    return {
        "type": "message",
        "model": "claude-haiku-5-5",
        "usage": {"input_tokens": 100, "cache_read_input_tokens": read, "output_tokens": 5},
    }


def test_report_table_drift_and_gate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lines = [
        record("chat", {"model": "m", "system": f"Now: 2026-10-30T10:0{i}:00Z"}, anthropic_resp(0)) for i in range(3)
    ]
    lines += [record("faq", {"model": "m", "system": "stable"}, anthropic_resp(r)) for r in (0, 900, 900)]
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert main(["report", str(log)]) == 0
    out = capsys.readouterr().out
    assert "chat" in out and "system (timestamp) x2" in out and "faq" in out
    assert main(["report", str(log), "--min-hit-rate", "0.5"]) == 1
    assert "chat" in capsys.readouterr().err


def test_report_flags_identical_prefix_without_cache_read(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lines = [record("s", {"model": "m", "system": "same"}, anthropic_resp(0)) for _ in range(2)]
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(x) for x in lines))
    main(["report", str(log)])
    assert "prefix ok, no cache read" in capsys.readouterr().out


def test_bad_input_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["diff", str(tmp_path / "missing.json"), str(tmp_path / "x.json")]) == 2
    assert "cachemaxxing:" in capsys.readouterr().err
