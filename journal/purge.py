"""Delete the journal entries past their retention period.

    python -m journal.purge [--days N]

Meant to run daily (a scheduled task in Coolify, inside the api container).
"""

import argparse

from app.core.config import settings
from journal.store import purge


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=settings.answer_log_retention_days)
    args = parser.parse_args()
    print(f"{purge(args.days)} entries deleted (older than {args.days} days)")


if __name__ == "__main__":
    main()
