from pathlib import Path


def test_placeholder():
    assert Path(".").exists()
