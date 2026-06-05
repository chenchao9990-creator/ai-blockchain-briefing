# Telegram Channel Setup

This site can push each new daily briefing to a Telegram Channel after the HTML/PDF files are published.

## Recommended setup

Use a Telegram Channel as the public reading entry point and keep the full article on GitHub Pages.

- Telegram Channel: short daily notification and link.
- Website: full mobile-first briefing.
- PDF: archive and storage.

## Create the bot

1. Open Telegram and message `@BotFather`.
2. Run `/newbot`.
3. Choose a bot name and username.
4. Copy the bot token. Do not put this token in code or commit it to GitHub.

## Create the channel

1. Create a Telegram Channel.
2. Give it a clear name, for example `AI & Blockchain Briefing`.
3. If possible, set a public username. Public channels can use `@channel_username` as the chat ID.
4. Add the bot as an administrator.
5. Give the bot permission to post messages.

## Add GitHub Actions secrets

In the GitHub repository, open:

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

Add these two secrets:

- `TELEGRAM_BOT_TOKEN`: the BotFather token.
- `TELEGRAM_CHAT_ID`: your channel username, for example `@ai_blockchain_briefing`.

For a private channel, use the numeric channel chat ID instead of a public username.

## Test it

1. Open GitHub `Actions`.
2. Select `Telegram briefing push`.
3. Click `Run workflow`.
4. First run with `dry_run = true` to preview the message in the workflow log.
5. Run again with `dry_run = false` after the bot token and chat ID are configured.

After setup, commits with a message containing `daily briefing` and updated briefing files will trigger a Telegram push automatically.
