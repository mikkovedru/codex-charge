"""PyInstaller entry for codex-charge CLI (absolute imports only)."""

from codex_charge.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
