# simply-subdomain-sites-migration

Migrate static sites hosted on FTP (Simply.dk / UnoEuro) to GitHub Pages with custom subdomains.

## Sites

| Site | FTP path | Custom domain | GitHub repo |
|------|----------|---------------|-------------|
| aarhus-ejerlejlighed | `/aarhus-ejerlejlighed.dk` | `aarhus-ejerlejlighed.jacobworsoe.dk` | [jacobworsoe/aarhus-ejerlejlighed](https://github.com/jacobworsoe/aarhus-ejerlejlighed) |
| sprinklertesten | `/sprinklertesten` | `sprinklertesten.jacobworsoe.dk` | [jacobworsoe/sprinklertesten](https://github.com/jacobworsoe/sprinklertesten) |

## Prerequisites

- Python 3.8+
- `git` on PATH
- `gh` (GitHub CLI) installed and authenticated (`gh auth login`)
- FTP credentials in `scripts/.ftp-credentials` (gitignored) or environment variables

## Setup

1. Copy the credentials template and fill in your values:

```
cp scripts/ftp-credentials.example scripts/.ftp-credentials
```

2. Or set environment variables:

```
export FTP_HOST=linux12.unoeuro.com
export FTP_USER=your-ftp-user
export FTP_PASSWORD=your-password
```

## Usage

### Full migration (all sites)

```
python scripts/migrate_ftp_sites_to_github_pages.py
```

### Dry run (download and inspect without pushing)

```
python scripts/migrate_ftp_sites_to_github_pages.py --dry-run
```

### Single site

```
python scripts/migrate_ftp_sites_to_github_pages.py --site sprinklertesten
python scripts/migrate_ftp_sites_to_github_pages.py --site aarhus-ejerlejlighed
```

## What the script does

1. Connects to FTP using credentials
2. Downloads the full site directory tree to a temporary folder
3. Writes a `CNAME` file with the custom subdomain
4. Creates a public GitHub repo (if it doesn't already exist)
5. Initializes a git repo, commits all files, and force-pushes to `main`
6. Enables GitHub Pages on the `main` branch root
7. Sets the custom domain via the GitHub API

The script is idempotent: re-running it will re-download and force-push, updating the repo to match FTP.

## DNS setup

After running the migration, add these DNS records:

| Type | Name | Value |
|------|------|-------|
| CNAME | `aarhus-ejerlejlighed` | `jacobworsoe.github.io.` |
| CNAME | `sprinklertesten` | `jacobworsoe.github.io.` |

Verify with:

```
nslookup aarhus-ejerlejlighed.jacobworsoe.dk
nslookup sprinklertesten.jacobworsoe.dk
curl -sI https://aarhus-ejerlejlighed.jacobworsoe.dk
curl -sI https://sprinklertesten.jacobworsoe.dk
```
