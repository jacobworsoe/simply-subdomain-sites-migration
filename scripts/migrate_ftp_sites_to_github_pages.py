#!/usr/bin/env python3
"""
Migrate static sites from FTP to GitHub Pages with custom subdomains.

Downloads each site from FTP, creates a GitHub repo if missing,
commits all files, enables GitHub Pages, and sets up a CNAME.

Prerequisites:
  - Python 3.8+
  - git on PATH
  - gh (GitHub CLI) authenticated (`gh auth login`)
  - FTP credentials in scripts/.ftp-credentials or env vars FTP_HOST/FTP_USER/FTP_PASSWORD

Usage:
  python scripts/migrate_ftp_sites_to_github_pages.py
  python scripts/migrate_ftp_sites_to_github_pages.py --dry-run
  python scripts/migrate_ftp_sites_to_github_pages.py --site sprinklertesten
"""
from __future__ import annotations

import argparse
import ftplib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CREDS_FILE = SCRIPTS_DIR / ".ftp-credentials"

GITHUB_OWNER = "jacobworsoe"

SITES = [
    {
        "name": "aarhus-ejerlejlighed",
        "ftp_path": "/aarhus-ejerlejlighed.dk",
        "cname": "aarhus-ejerlejlighed.jacobworsoe.dk",
    },
    {
        "name": "sprinklertesten",
        "ftp_path": "/sprinklertesten",
        "cname": "sprinklertesten.jacobworsoe.dk",
    },
]


def load_ftp_creds() -> dict[str, str]:
    env = {
        "host": os.environ.get("FTP_HOST", "").strip(),
        "user": os.environ.get("FTP_USER", "").strip(),
        "password": os.environ.get("FTP_PASSWORD", "").strip(),
    }
    if env["host"] and env["user"] and env["password"]:
        return env
    if not CREDS_FILE.exists():
        sys.exit(
            "Set FTP_HOST/FTP_USER/FTP_PASSWORD or create scripts/.ftp-credentials"
        )
    for line in CREDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip().lower().replace(" ", "_")
            v = v.strip()
            if "host" in k:
                env["host"] = v
            elif "user" in k or "bruger" in k:
                env["user"] = v
            elif "pass" in k or "adgang" in k:
                env["password"] = v
    if not all(env.values()):
        sys.exit("scripts/.ftp-credentials must contain host, user, and password")
    return env


def ftp_connect(creds: dict[str, str]) -> ftplib.FTP:
    ftp = ftplib.FTP()
    ftp.connect(creds["host"], timeout=120)
    ftp.login(creds["user"], creds["password"])
    ftp.set_pasv(True)
    return ftp


def ftp_download_tree(ftp: ftplib.FTP, remote_path: str, local_dir: Path) -> int:
    """Recursively download a directory tree. Returns file count."""
    ftp.cwd(remote_path)
    count = 0
    entries = []
    for name, facts in ftp.mlsd():
        if name in (".", ".."):
            continue
        entries.append((name, facts))

    for name, facts in sorted(entries):
        t = (facts.get("type") or "").lower()
        local_path = local_dir / name
        if t == "dir":
            local_path.mkdir(parents=True, exist_ok=True)
            child_remote = f"{remote_path.rstrip('/')}/{name}"
            count += ftp_download_tree(ftp, child_remote, local_path)
            ftp.cwd(remote_path)
        else:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {name}", f.write)
            count += 1
    return count


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"CMD FAILED: {' '.join(cmd)}", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result


def gh_repo_exists(owner: str, name: str) -> bool:
    r = run(["gh", "repo", "view", f"{owner}/{name}", "--json", "name"], check=False)
    return r.returncode == 0


def gh_create_repo(owner: str, name: str) -> None:
    run([
        "gh", "repo", "create", f"{owner}/{name}",
        "--public",
        "--description", f"Static site: {name}",
    ])
    print(f"  Created repo {owner}/{name}")


def gh_enable_pages(owner: str, name: str) -> None:
    """Enable GitHub Pages from the default branch root via the API."""
    run([
        "gh", "api",
        f"repos/{owner}/{name}/pages",
        "-X", "POST",
        "-f", "build_type=legacy",
        "-f", "source[branch]=main",
        "-f", "source[path]=/",
    ], check=False)


def gh_set_custom_domain(owner: str, name: str, cname: str) -> None:
    """Set the custom domain via the API (supplements the CNAME file)."""
    run([
        "gh", "api",
        f"repos/{owner}/{name}/pages",
        "-X", "PUT",
        "-f", f"cname={cname}",
        "-f", "build_type=legacy",
        "-f", "source[branch]=main",
        "-f", "source[path]=/",
    ], check=False)


def migrate_site(site: dict, creds: dict[str, str], dry_run: bool = False) -> None:
    name = site["name"]
    ftp_path = site["ftp_path"]
    cname = site["cname"]

    print(f"\n{'='*60}")
    print(f"Migrating: {name}")
    print(f"  FTP path : {ftp_path}")
    print(f"  CNAME    : {cname}")
    print(f"  Repo     : {GITHUB_OWNER}/{name}")
    print(f"{'='*60}")

    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir) / name
        site_dir.mkdir()

        # Download from FTP
        print("  Downloading from FTP ...")
        ftp = ftp_connect(creds)
        count = ftp_download_tree(ftp, ftp_path, site_dir)
        ftp.quit()
        print(f"  Downloaded {count} files")

        # Write CNAME
        (site_dir / "CNAME").write_text(cname + "\n", encoding="utf-8")
        print(f"  Wrote CNAME: {cname}")

        if dry_run:
            print("  [DRY RUN] Would create repo and push. Files downloaded to temp dir.")
            for p in sorted(site_dir.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(site_dir)
                    print(f"    {rel}  ({p.stat().st_size} bytes)")
            return

        # Create repo if needed
        if gh_repo_exists(GITHUB_OWNER, name):
            print(f"  Repo {GITHUB_OWNER}/{name} already exists")
        else:
            gh_create_repo(GITHUB_OWNER, name)

        # Init git, commit, push
        run(["git", "init", "-b", "main"], cwd=site_dir)
        run(["git", "add", "."], cwd=site_dir)
        run(["git", "commit", "-m", f"Initial commit: {name} site from FTP"], cwd=site_dir)
        run([
            "git", "remote", "add", "origin",
            f"https://github.com/{GITHUB_OWNER}/{name}.git",
        ], cwd=site_dir)
        run(["git", "push", "-u", "origin", "main", "--force"], cwd=site_dir)
        print("  Pushed to GitHub")

        # Enable Pages
        print("  Enabling GitHub Pages ...")
        gh_enable_pages(GITHUB_OWNER, name)

        # Set custom domain
        print("  Setting custom domain ...")
        gh_set_custom_domain(GITHUB_OWNER, name, cname)

    print(f"  Done: https://github.com/{GITHUB_OWNER}/{name}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Migrate FTP static sites to GitHub Pages."
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Download and show files without creating repos or pushing",
    )
    ap.add_argument(
        "--site", choices=[s["name"] for s in SITES],
        help="Migrate a single site instead of all",
    )
    args = ap.parse_args()

    creds = load_ftp_creds()
    print(f"FTP host: {creds['host']}")

    targets = [s for s in SITES if s["name"] == args.site] if args.site else SITES

    for site in targets:
        migrate_site(site, creds, dry_run=args.dry_run)

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("\nDNS records to add (CNAME):")
    for site in targets:
        print(f"  {site['cname']}  CNAME  {GITHUB_OWNER}.github.io.")
    print("\nAfter DNS propagation, verify with:")
    for site in targets:
        print(f"  nslookup {site['cname']}")
        print(f"  curl -sI https://{site['cname']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
