# Operations

> How to keep the F1 2026 Viewer running. Server, cron, tests, iPhone
> verification, debugging. Bookmark this.

---

## Server

The viewer is a **static site** served by `python3 -m http.server`, bound
to the Tailscale IP only (not public).

```bash
# Start (foreground)
cd ~/.hermes/workspace/projects/f1-2026-viewer
python3 -m http.server 8081 --bind 100.91.143.50

# Start (background, with logging)
nohup python3 -m http.server 8081 --bind 100.91.143.50 \
  > /tmp/f1-viewer-server.log 2>&1 &
echo $! > /tmp/f1-viewer-server.pid

# Check it's running
curl -sS --max-time 4 http://100.91.143.50:8081/ -o /dev/null \
  -w "status: HTTP %{http_code}\n"
```

**Why Tailscale-only:** Sir's home network is reachable via Tailscale
(100.64.0.0/10). The box has an iptables rule that drops all
non-Tailscale traffic to port 8081. This means:

- Sir's iPhone (on Tailscale): works.
- Sir's other machines (on Tailscale): work.
- Anyone else: blocked at the firewall.

To verify the firewall rule is in place:
```bash
sudo iptables -L INPUT -n | grep 8081
# Expected: tcp dpt:8081 !s 100.64.0.0/10 → DROP
```

If the rule is missing, **re-add it before exposing the port**:
```bash
sudo iptables -I INPUT -p tcp --dport 8081 ! -s 100.64.0.0/10 -j DROP
```

---

## Cron (Sunday 23:00 CAT)

There is **one** cron job that keeps the data fresh.

| Field | Value |
|---|---|
| Cron schedule | `0 21 * * 0` UTC (Sunday 21:00 UTC = Sunday 23:00 CAT) |
| Mode | `no_agent: true` — script-only, no LLM tokens |
| Delivery | Silent on success, alert on failure |
| Job ID | `87ed139da066` |
| Sequence | `update_f1_data.py` → `build_issue_data.py` → `derive_pace.py` |

### Why Sunday 23:00 CAT

Race finishes are typically 17:00-19:00 local Europe time, which is the
same as 17:00-19:00 CAT (UTC+2, no DST in the EU since 2026 reform). By
23:00 CAT (21:00 UTC), the Jolpica results are stable. The 3-round
amendment window means that if R6's results update on Tuesday, the next
Sunday's cron will catch R4-R6 anyway.

### Manually run the data pipeline

If you want to refresh the data **right now** (e.g. after a race ends, or
when developing a new derived dataset):

```bash
cd ~/.hermes/workspace/projects/f1-2026-viewer

# Step 1: fetch latest race + standings + qualifying
python3 scripts/update_f1_data.py

# Step 2: derive car-issues-dnf.json from race results
python3 scripts/build_issue_data.py

# Step 3: derive pace-dashboard.json from race results
python3 scripts/derive_pace.py
```

Each script is **idempotent** — re-running it just rewrites the JSON
files with the latest data. No side effects, no DB.

### Debug a failed cron

If the cron fails, you'll get a Telegram alert from the scheduler. To
debug:

```bash
# Check the cron job definition
hermes cronjob list | grep -A 5 "87ed139da066"

# Run the scripts manually to see errors
cd ~/.hermes/workspace/projects/f1-2026-viewer
python3 scripts/update_f1_data.py 2>&1 | tail -30
```

Common failure modes:
- **Jolpica 5xx** — retry the script in 5 minutes, the API is free-tier
- **JSON parse error** — Jolpica changed their schema. Check
  https://api.jolpi.ca/ergast/f1/2026/6/results.json manually
- **No rounds_covered update** — R7 hasn't finished yet. The cron is
  designed to be a no-op if there's no new round.

---

## Add a new season year (yearly task)

When 2027 starts and 2026 ends:

1. **Update `data/latest.json`** — change `round` to 1 and `updated` to
   the new fetch timestamp.
2. **Update `data/season-summary.json`** — start with an empty object `{}`,
   the cron will populate it as races happen.
3. **Add a new year to `data/regulations.json`**:
   ```bash
   python3 scripts/update_regulations.py --add-year 2027
   ```
   Then hand-edit the scaffolded year entries with 2027 FIA Tech Regs
   changes. See `ROADMAP.md` for what to look for.
4. **Add a new year to `data/regulations.json`** with `active: true` and
   set 2026's `active: false`.
5. **Update README + BUILD-REPORT** with the new season's headline numbers.

---

## Tests (Playwright iOS WebKit)

The test suite is in `scripts/test-*.js`. Each test opens the page in
Playwright with the iPhone 13 device profile, then asserts on the DOM
and console.

### Reference install

Playwright is installed at `/root/.npm/_npx/e41f203b7505f1fb/node_modules/playwright`.
This is a system-level npm cache, not a project dependency (the project
has no `package.json`).

### Run the full suite

```bash
cd ~/.hermes/workspace/projects/f1-2026-viewer
for t in scripts/test-*.js; do
  echo "=== $t ==="
  node "$t"
done
```

### Run a single test

```bash
node scripts/test-regulations.js        # regulations page + REG REWRITE button
node scripts/test-season-buttons.js     # 3 home season-action buttons
node scripts/test-home-stats.js         # 4 home stat cards
node scripts/test-detail-pages.js       # part-changes + car-issues drill-down
node scripts/test-nav-loop.js           # back/forward navigation
node scripts/test-home-layout.js        # 4-stat layout, no horizontal overflow
```

### Add a new test

Pattern (copy `scripts/test-regulations.js`):

```js
const { chromium, devices } = require('/root/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 13'] });
  const page = await ctx.newPage();
  // ... goto, wait, evaluate, assert
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
```

### Why Playwright iPhone 13 WebKit

Sir's primary device is an iPhone. iOS Safari has unique WebKit quirks
that Chrome doesn't reproduce. Testing in iPhone 13 WebKit is the closest
thing to testing on Sir's actual phone, short of doing it manually.

### Cache buster in tests

All page loads use `?v=TESTNAME` to force a fresh fetch. iOS Safari
aggressively caches, and so does Playwright (its HTTP cache mirrors the
real browser).

---

## iPhone verification workflow

The end-to-end verification path, every time:

1. **Make the change.** Edit HTML / JSON / script on the box.
2. **Restart the server** (if you changed the python server, not the
   data files). `kill $(cat /tmp/f1-viewer-server.pid) && nohup python3
   -m http.server 8081 --bind 100.91.143.50 > /tmp/f1-viewer-server.log
   2>&1 &`
3. **Playwright test** — `node scripts/test-FEATURE.js`. Confirm no
   errors, all assertions pass.
4. **Telegram screenshots** — `node scripts/shot-FEATURE.js`, then send
   the PNG to Sir via `send_message` with `MEDIA:/path/...png`.
5. **Sir tests on iPhone** — Sir opens the URL, hard-refreshes (or uses
   `?v=N`), confirms the feature works on his actual device.
6. **Sir signs off** — only then commit + push.

**Why hard-refresh:** iOS Safari caches everything. A deploy that doesn't
include a `?v=N` change won't be visible to Sir until he clears his cache
manually. The cache buster is the safety net.

---

## Common debugging

### "I changed a JSON file but the page shows old data"

- iPhone: hard-refresh (long-press reload, or `?v=N` in URL).
- Local: `curl http://100.91.143.50:8081/data/FILE.json | head` to confirm
  the new content is being served.
- If it's still old: `ps aux | grep "http.server"` to confirm the server
  is running. `python3 -m http.server` doesn't cache.

### "The 3D viewer is showing weird artifacts"

It's not — the 3D viewer is **disabled**. The commented `screen-car` block
in `index.html` is intentional. The actual viewer is `explore-car.html` (SVG).
If you're seeing 3D, you're looking at a stale browser cache or a different
project.

### "The cron fired but nothing updated"

- Check the cron job's recent output: `hermes cronjob list` then
  `hermes cronjob status 87ed139da066`.
- Run the scripts manually — they print to stdout, you'll see exactly
  what they're doing.
- Check the JSON file timestamps: `ls -la data/`. If the mtime is recent,
  the data did update. If not, the script didn't write.

### "I want to add a new page"

1. Copy an existing page (`pace.html` is the simplest pattern).
2. Add a button on home that links to it.
3. Add a section to `ARCHITECTURE.md` and `DATA-REFERENCE.md` if it
   introduces a new data file.
4. Add a `scripts/test-FEATURE.js` Playwright test.
5. Document it in `README.md` (add a row to the pages table).
6. Commit + push.

### "How do I regenerate a derived dataset?"

```bash
cd ~/.hermes/workspace/projects/f1-2026-viewer

# Car issues
python3 scripts/build_issue_data.py

# Pace dashboard
python3 scripts/derive_pace.py

# Season summary (rarely needed, only if season-summary.json is corrupt)
python3 scripts/update_f1_data.py
```

The scripts read `data/r1-australia.json` etc. and write the derived
JSONs. Atomic via `os.replace` so the HTTP server never serves partial
JSON.

---

## Security

- **Tailscale-only** — iptables rule on the box drops non-Tailscale traffic
  to port 8081.
- **No backend, no auth, no DB** — the entire app is read-only static.
- **Polymarket private key** at `~/.hermes/workspace/projects/trading-bot/.env`
  is **not** part of this project. It is in a separate project, in a
  separate directory, on a separate domain. Do not move it, do not
  reference it from this project.
- **No external network calls** from the browser except:
  - Google Fonts (Inter)
  - esm.sh (Three.js, if you re-enable the 3D viewer)
  - Jolpica (during cron, server-side only — never from the browser)
- **No telemetry sent** from the browser.
