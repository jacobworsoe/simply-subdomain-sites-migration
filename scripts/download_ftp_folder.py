#!/usr/bin/env python3
"""
Download a folder from the same FTP account used by migrate_ftp_sites_to_github_pages.py.

Usage:
  python scripts/download_ftp_folder.py /size-monitor sites/size-monitor
"""
from __future__ import annotations

import sys
from pathlib import Path

# Reuse credential + download helpers from migration script
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from migrate_ftp_sites_to_github_pages import (  # noqa: E402
    ftp_connect,
    ftp_download_tree,
    load_ftp_creds,
)


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/download_ftp_folder.py <remote_path> <local_dir>",
            file=sys.stderr,
        )
        return 2
    remote = sys.argv[1].rstrip("/") or "/"
    if not remote.startswith("/"):
        remote = "/" + remote
    local = Path(sys.argv[2]).resolve()
    local.mkdir(parents=True, exist_ok=True)

    creds = load_ftp_creds()
    print(f"Connecting to {creds['host']} …")
    ftp = ftp_connect(creds)
    n = ftp_download_tree(ftp, remote, local)
    ftp.quit()
    print(f"Downloaded {n} files into {local}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
