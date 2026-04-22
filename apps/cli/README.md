# Ouroboros CLI

Command-line client for the Ouroboros API. Wraps the same `/api` endpoints used by the web UI, authenticated with a long-lived session token stored in your OS keyring.

## Install

```bash
cd apps/cli
pip install -e .
```

## Usage

```bash
# Sign in with email + password
ouroboros login --email you@example.com

# Or with GitHub OAuth (opens a browser; paste the ob_session cookie back)
ouroboros login --github

# Inspect the active session
ouroboros whoami

# Sign out (revokes the session and removes it from the keyring)
ouroboros logout
```

By default the CLI talks to `http://localhost:8000`; override with `--api` or
`OUROBOROS_API_URL`.

The token is stored in the OS keyring under the service `ouroboros-cli` keyed
by the API URL. If keyring is unavailable, the CLI falls back to writing the
token to `~/.config/ouroboros/cli.json` with mode `0600`.
