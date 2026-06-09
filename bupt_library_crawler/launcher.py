from __future__ import annotations

import sys
import traceback
from pathlib import Path

from bupt_library_crawler.cli import build_parser, crawl


def main() -> None:
    root = Path.cwd()
    default_args = [
        "--full",
        "--resume",
        "--delay",
        "1.2",
        "--db",
        str(root / "data" / "bupt_library.sqlite3"),
        "--output",
        str(root / "output" / "bupt_library_holdings.xlsx"),
        "--batch-upload-mb",
        "90",
        "--repo-root",
        str(root),
        "--cleanup-after-upload",
        "--log-level",
        "INFO",
    ]

    parser = build_parser()
    args = parser.parse_args(default_args + sys.argv[1:])
    try:
        crawl(args)
    except KeyboardInterrupt:
        print("\nStopped. Progress has been saved; run the exe again to resume.")
    except Exception:
        traceback.print_exc()
        input("\nAn error occurred. Press Enter to close...")
        raise


if __name__ == "__main__":
    main()
