import zakura_tui


def test_package_exposes_version() -> None:
    assert zakura_tui.__version__ == "0.1.0"
