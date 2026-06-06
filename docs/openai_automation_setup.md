# OpenAI Automation Setup

The site now supports two OpenAI-backed automation modes:

- Daily auto briefing: generates the full HTML/PDF newsletter every day at 08:30 UTC.
- Breaking news monitor: checks every 30 minutes and sends Telegram alerts only when a story is important enough.

Both modes use OpenAI only through GitHub Secrets. Do not commit API keys.

## Required secret

Add this repository secret:

- `OPENAI_API_KEY`

GitHub path:

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

## Optional variables

GitHub path:

`Settings` -> `Secrets and variables` -> `Actions` -> `Variables`

Optional variables:

- `OPENAI_MODEL`: defaults to `gpt-5`.
- `ENABLE_DAILY_AUTO_BRIEFING`: set to `true` only when you want the daily workflow to run automatically.
- `ENABLE_BREAKING_NEWS`: set to `true` only when you want high-frequency breaking monitoring.
- `BREAKING_THRESHOLD`: defaults to `8`. Higher means fewer alerts.

## Daily briefing workflow

Workflow:

`Daily auto briefing`

Schedule:

`08:30 UTC` every day.

The scheduled run is skipped unless `ENABLE_DAILY_AUTO_BRIEFING` is set to `true`.

Manual test:

1. Open GitHub Actions.
2. Select `Daily auto briefing`.
3. Run with `dry_run = true` first. This calls OpenAI and prints preview JSON without writing files or sending Telegram.
4. Run with `dry_run = false` when the output style looks acceptable.

## Breaking news workflow

Workflow:

`Breaking news monitor`

Schedule:

Every 30 minutes.

The scheduled run is skipped unless `ENABLE_BREAKING_NEWS` is set to `true`.

Manual test:

1. Open GitHub Actions.
2. Select `Breaking news monitor`.
3. Run with `dry_run = true` to preview candidate alerts.
4. Set `ENABLE_BREAKING_NEWS = true` only after the alert quality looks good.

## Editorial guardrails

The automation prioritizes:

- Reuters, Financial Times, Bloomberg, CNBC, The Verge, WSJ, TechCrunch, CoinDesk, Cointelegraph.
- Official company blogs.
- Regulator and government websites.

It should avoid:

- Pure gossip.
- Weak price-only moves.
- Duplicate stories.
- Minor product tweaks without business or policy impact.
