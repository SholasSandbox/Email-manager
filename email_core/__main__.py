"""Package entry point for the current dry-run CLI."""

from .run_daily_review import main


if __name__ == "__main__":
    raise SystemExit(main())
