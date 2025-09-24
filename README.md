# iPhone Pickup Checker (GitHub Pages + Actions)

This repo checks Apple Store pickup availability for iPhone models via a **headless browser (Playwright)** from GitHub Actions, writes `docs/data/latest.json`, and serves a static UI via **GitHub Pages** (`/` and `/es/`).

## Quick start

1. **Create a new GitHub repo** and upload this folder's contents.
2. Go to **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main` → Folder: **/docs** → Save.
3. Go to **Actions**, run **iPhone Pickup Check** once (the `check.yml` workflow).  
   This will generate `docs/data/latest.json` and commit it.
4. Open your Pages URL: `https://<username>.github.io/<repo>/` (English) or `/es/` (Spanish).

## Configure city & alerts

- In `.github/workflows/check.yml`, set:
  - `ZIP_CODES: "33172"` (single ZIP or comma-separated list)
  - `PART_NOTES`: free label shown in UI/alerts
- Optional alerts:
  - Add **repo secrets** under **Settings → Secrets and variables → Actions**:
    - `TELEGRAM_BOT_TOKEN`
    - `TELEGRAM_CHAT_ID`
    - (optional) `SLACK_WEBHOOK`

## Notes
- GitHub-hosted cron minimum is every **5 minutes**.
- For per-minute checks, use a **self-hosted runner** and change cron to `* * * * *`.
- If `docs/data/latest.json` doesn’t update, check Actions logs. Screenshots are saved to `docs/data/` when modal open fails.
