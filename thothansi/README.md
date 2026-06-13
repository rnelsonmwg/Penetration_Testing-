# Thothansi 𓂀

**AI-assisted passive reconnaissance & triage for _authorized_ security testing.**

Thothansi pairs **Anansi** (the weaver) with **Thoth** (the scribe-god of wisdom):
it spins out an engagement's attack surface through passive recon, then acts as the
analyst that records and weighs what was found. It is built for solo bug-bounty work
and small red/blue-team engagements against web apps, cloud, and APIs.

> ## ⚠️ Authorized use only
> Thothansi is for reconnaissance against systems you **own or have explicit written
> authorization to test**. Every module is gated behind a hard scope file: anything
> not declared in scope is refused before a single packet is sent. The bundled
> techniques are passive (public DNS, certificate-transparency logs, passive-DNS
> sources) plus a single low-touch HTTP request for fingerprinting. There is no
> exploitation, fuzzing, or intrusive scanning, and the AI triage prompt explicitly
> forbids generating exploit code or payloads. You are responsible for staying within
> the bounds of your authorization and the law.

---

## What it does

- **Passive recon / OSINT**
  - DNS enumeration (A/AAAA/MX/NS/TXT/CNAME/SOA/CAA)
  - Subdomain discovery via Certificate Transparency (crt.sh) and passive-DNS sources
  - Web technology fingerprinting + missing-security-header checks (one HTTP GET)
- **AI-assisted triage** — the active model re-ranks findings, explains why each
  matters for this surface, and suggests a non-destructive verification step.
- **Pluggable AI from day one** — local and hosted models behind one interface:
  Ollama (local), Claude, OpenAI, Groq, DeepSeek, Grok/xAI.
- **Three interfaces** — a Rich CLI, a Textual TUI, and a FastAPI web dashboard.
- **Two run modes** — fully automated end-to-end, or interactive/step-gated where you
  approve each phase (recon → triage → report).
- **Themeable** — a clean modern dashboard, or a gold-on-black *mythic* theme with
  hieroglyph and spider-web motifs.

## Install

```bash
pip install -e .          # from the project root
thothansi init            # scaffolds config/config.yaml and config/scope.yaml
```

Then edit `config/scope.yaml` with the targets you are authorized to test, and put
any API keys in a `.env` (see `.env.example`). Local Ollama needs no key.

## Quickstart

```bash
# Inspect / extend the authorized scope
thothansi scope show
thothansi scope add "api.example.com" --note "authorized via ticket-123"

# Check which AI providers are configured
thothansi providers

# Run the full pipeline (recon -> triage -> report)
thothansi run example.com --report report.md

# Step-gated run: approve each phase
thothansi run example.com --interactive

# Skip AI triage, or pick a provider for this run
thothansi run example.com --no-triage
thothansi run example.com --provider claude

# Re-render a saved run
thothansi report run-20260101-120000

# Launch the interfaces
thothansi tui
thothansi serve            # web dashboard at http://127.0.0.1:8000
```

## Scope: the safety core

The scope file is a human-readable allow-list. Wildcards match **subdomains only**;
an apex entry matches the apex and all subdomains; an `out_of_scope` deny-list
overrides everything.

```yaml
engagement: "acme-bbp"
authorized_by: "you / HackerOne handle"
in_scope:
  - value: "example.com"            # apex + subdomains
  - value: "*.staging.example.com"  # subdomains only
  - value: "203.0.113.0/24"         # an authorized range
out_of_scope:
  - value: "blog.example.com"       # overrides the allow-list
```

Targets can be added on the fly from the CLI (`scope add`), the TUI (the sidebar
input), or the dashboard — every addition is recorded in an audit log.

## AI providers

Set the active provider in `config.yaml` (`active_provider:`) or per run with
`--provider`. Keys are read from the environment:

| Provider | Type   | Env var             | Default model               |
| -------- | ------ | ------------------- | --------------------------- |
| ollama   | local  | _(none)_            | `llama3.1`                  |
| claude   | remote | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6`         |
| openai   | remote | `OPENAI_API_KEY`    | `gpt-4o-mini`               |
| groq     | remote | `GROQ_API_KEY`      | `llama-3.3-70b-versatile`   |
| deepseek | remote | `DEEPSEEK_API_KEY`  | `deepseek-chat`             |
| grok     | remote | `XAI_API_KEY`       | `grok-2-latest`             |

Adding a provider is one subclass + a `@register` decorator in
`thothansi/providers/__init__.py`; nothing else needs to change.

## Docker

```bash
cp .env.example .env                       # add keys if using hosted models
cp config/config.example.yaml config/config.yaml
cp config/scope.example.yaml config/scope.yaml   # then edit your scope
docker compose -f docker/docker-compose.yml up --build
```

The dashboard is served on `:8000`. An optional Ollama service is included for
fully-offline triage. For one-off CLI use:

```bash
docker run --rm -it -v "$PWD/config:/app/config" thothansi:0.1.0 run example.com
```

## Architecture

```
thothansi/
  core/        models, scope (authorization), config, engine, store
  providers/   AI abstraction + Ollama/Claude/OpenAI/Groq/DeepSeek/Grok
  recon/       dns, crtsh, subdomains, fingerprint (all scope-gated)
  triage/      AI analyzer (strict-JSON, graceful fallback)
  report/      Markdown + JSON reporting
  cli.py       Typer + Rich CLI
  tui/         Textual terminal UI
  web/         FastAPI backend + static dashboard
```

The engine is UI-agnostic: recon → triage → report is one code path that emits
progress events, so the CLI, TUI, and dashboard all drive the same pipeline.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Released under the MIT License (see `LICENSE`), with an authorized-use notice.
Use it only where you have permission.
