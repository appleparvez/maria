"""Smoke test — verify the package is importable."""


def test_version():
    """MARIA package should expose a version string."""
    from maria import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_entry_point():
    """The main entry point should be callable without error."""
    from maria.__main__ import main

    # main() prints to stdout; just verify it doesn't raise.
    main()
