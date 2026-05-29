# Put the dashboard online (cloud scrape + free hosting)

This turns your local-only setup into a **24/7 online dashboard** that
refreshes itself every weekday **without your Mac being on**.

```
GitHub Actions (cron)  ──daily──▶  runs your 5 scraper.py in the cloud
        │                          → rewrites data.csv / data.js
        │                          → commits the changes back to the repo
        ▼
GitHub Pages  ──serves──▶  https://<you>.github.io/<repo>/   (any device)
```

Everything in this repo is already prepared. You only need to do the parts
that require *your* GitHub login — creating the repo and pushing once.

---

## What's already set up for you

| File | Purpose |
|------|---------|
| `.github/workflows/scrape.yml` | Cloud cron: runs all 5 scrapers weekdays @ 21:10 UTC, commits fresh data |
| `.gitignore` | Whitelist — only the 5 dashboards + combined view are tracked (keeps the 1.2 GB working folder out of git) |
| `index.html` | Redirects the bare site URL → `dashboard.html` |
| `.nojekyll` | Tells GitHub Pages to serve files as-is |

The five scrapers are pure-Python (no installs) and write to their own
folders, so they run unchanged on GitHub's Linux runners.

---

## Step 1 — Create the repo (you do this)

1. Sign in / sign up at <https://github.com> (account is `ctn222@gmail.com` if you have one).
2. Click **New repository**.
3. Name it e.g. `stocks-dashboard`, set it **Public**, **do not** add a README/.gitignore (we already have files), click **Create repository**.
4. Copy the repo URL, e.g. `https://github.com/<you>/stocks-dashboard.git`.

## Step 2 — Push this folder (commands below)

A local git repo with your first commit is **already made**. Connect it to
GitHub and push (replace the URL with yours):

```bash
cd "/Users/cnguyen/Claude/Local Apps"
git remote add origin https://github.com/<you>/stocks-dashboard.git
git branch -M main
git push -u origin main
```

When prompted, log in (a browser popup, or a Personal Access Token as the
password). *(Tell me once the repo exists and I can run the push for you.)*

## Step 3 — Allow the cron job to push data back

GitHub repo → **Settings** → **Actions** → **General** →
**Workflow permissions** → select **Read and write permissions** → **Save**.

> Without this, the daily job can scrape but can't commit the new data.

## Step 4 — Turn on GitHub Pages

GitHub repo → **Settings** → **Pages**:
- **Source:** *Deploy from a branch*
- **Branch:** `main` · folder `/ (root)` → **Save**

After ~1 minute your site is live at:
`https://<you>.github.io/stocks-dashboard/`
(the bare URL auto-redirects to `dashboard.html`).

## Step 5 — Test the cloud scrape now (don't wait for 9 PM)

GitHub repo → **Actions** → **Daily scrape** → **Run workflow** → **Run**.
Watch it run (~1–2 min). What success looks like:
- All 5 steps green, **or** some scrapers green with a red ✗ on others.
- A new commit `data: daily refresh <date>` appears.

**This is the real test** of whether the financial sites accept GitHub's
datacenter IP (see next section).

---

## If a scraper fails in the cloud (the one real risk)

Webull / Barchart may rate-limit or block GitHub's IP ranges differently
than your home IP. If one shows ✗ in the Actions log:

- **The others still work and still publish.** Only the blocked feed goes stale.
- **Hybrid fallback for that one feed:** keep scraping it on your Mac and let
  the Mac push just that folder. Re-enable its launchd job, and after it
  writes `data.js`, push it:
  ```bash
  cd "/Users/cnguyen/Claude/Local Apps"
  git add barchart100/data.js barchart100/data.csv && \
  git commit -m "barchart: local refresh" && git push
  ```
  (Tell me if you hit this and I'll wire up an auto-push for that folder.)

---

## Adjusting the schedule

The job runs **weekdays at 21:10 UTC**. To change it, edit the `cron:` line
in `.github/workflows/scrape.yml`:

| You want (ET) | EDT / summer | EST / winter | Safe year-round |
|---------------|-------------|--------------|-----------------|
| ~just after 4 PM close | `5 20 * * 1-5` | `5 21 * * 1-5` | `10 21 * * 1-5` (current) |

GitHub cron is UTC-only and ignores daylight saving, and may run 5–30 min
late under load — fine for an end-of-day snapshot.

---

## Notes & housekeeping

- **Data grows daily.** `data.csv`/`data.js` are append-style history, so the
  repo grows slowly over time. Fine for years; if it ever bloats, we can trim
  history or switch to date-partitioned files.
- **Local launchd jobs:** once the cloud job is confirmed working, you can stop
  the Mac ones so they don't double-run:
  ```bash
  launchctl unload ~/Library/LaunchAgents/com.barchart100.daily.plist
  launchctl unload ~/Library/LaunchAgents/com.mostactive.daily.plist
  launchctl unload ~/Library/LaunchAgents/com.topgainers1m.daily.plist
  launchctl unload ~/Library/LaunchAgents/com.topoptions.daily.plist
  ```
- **Add another dashboard later:** add a `!/<folder>/` line in `.gitignore`,
  add the folder name to the `for proj in …` list in the workflow, wire it into
  `dashboard.html`, commit, push.
