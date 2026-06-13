# Khepri Nyame

**Khepri Nyame** is a local-first, safe-by-default software bug hunting and API penetration testing workbench.

The name combines **Khepri**, the Egyptian scarab associated with transformation and emergence, with **Nyame**, the Akan sky deity associated with broad visibility. The product identity is intentionally subtle: the tool feels like a professional security platform, while the UI includes light mythological motifs and theme palettes.

## Design origin

This MVP was designed from an attached concept describing an AI-powered bug bounty and penetration testing framework with automated reconnaissance, attack-surface discovery, asset enumeration, AI-assisted vulnerability research, multi-model architecture, open extensibility, and local/cloud deployment options.

## Safety boundaries

Khepri Nyame is intended only for assets you own, manage, or have explicit written permission to test.

The first version intentionally avoids:

- exploit execution
- credential attacks
- brute force or password spraying
- destructive payloads
- stealth scanning
- persistence
- lateral movement
- data extraction or exfiltration

The MVP focuses on discovery, exploration, passive analysis, safe validation guidance, and reporting.

## MVP capabilities

- Local FastAPI web application
- CLI interface
- Local JSON storage
- Multi-agent architecture
- Human approval model for future active checks
- Import parsers for:
  - OpenAPI / Swagger
  - Postman collections
  - HAR files
  - Burp XML/text exports
  - GraphQL schemas
  - Raw URL lists
  - Notes
- AI provider abstraction for:
  - local rule-based planning
  - Ollama
  - OpenAI placeholder
  - Claude placeholder
  - DeepSeek placeholder
- Safe analysis agents:
  - Recon Agent
  - API Mapper Agent
  - Authorization Tester Agent
  - Secret Review Agent
  - Risk Prioritization Agent
  - Report Writer Agent
- Report exports:
  - Markdown
  - HTML
  - PDF
  - JSON
  - CSV
  - Executive summary
  - Jira-ready text
  - GitHub issue markdown
- Switchable UI modes:
  - guided wizard
  - autonomous agent
  - modular toolkit
- Switchable UI themes:
  - clean enterprise security platform — desert sand / obsidian
  - bug bounty hacker toolkit — green / bronze
  - cyber operations console — deep blue / gold

## Quick start

```bash
cd khepri-nyame
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8088
```

Open:

```text
http://127.0.0.1:8088
```

## CLI example

```bash
python -m app.cli init \
  --name "Local API Review" \
  --scope "https://api.example.test" \
  --authorization "I own, manage, or have explicit written permission to test this asset using safe validation only."

python -m app.cli list
python -m app.cli import-file <ENGAGEMENT_ID> --source-type openapi --path examples/sample_openapi.yaml
python -m app.cli plan <ENGAGEMENT_ID>
python -m app.cli run <ENGAGEMENT_ID>
python -m app.cli report <ENGAGEMENT_ID> --fmt markdown --output report.md
python -m app.cli report <ENGAGEMENT_ID> --fmt pdf --output report.pdf
```

## API examples

Create an engagement:

```bash
curl -X POST http://127.0.0.1:8088/engagements \
  -H 'content-type: application/json' \
  -d '{
    "name": "Local API Review",
    "scope": ["https://api.example.test"],
    "authorization_statement": "I own, manage, or have explicit written permission to test this asset using safe validation only.",
    "mode": "guided_wizard",
    "theme": "clean_enterprise",
    "provider": "local-rule-based"
  }'
```

Import an OpenAPI spec:

```bash
curl -X POST http://127.0.0.1:8088/engagements/<ENGAGEMENT_ID>/imports \
  -H 'content-type: application/json' \
  -d @examples/import_openapi_request.json
```

Generate a plan:

```bash
curl -X POST http://127.0.0.1:8088/engagements/<ENGAGEMENT_ID>/plan
```

Run safe analysis:

```bash
curl -X POST http://127.0.0.1:8088/engagements/<ENGAGEMENT_ID>/run \
  -H 'content-type: application/json' \
  -d '{"include_active_checks": false}'
```

## Architecture

```text
app/
  main.py                 FastAPI web/API entrypoint
  cli.py                  Typer CLI
  agents/                 Multi-agent analysis workflow
  ai/                     AI provider abstraction
  core/                   Safety and configuration
  integrations/           Human-approved external tool wrappers
  parsers/                OpenAPI/Postman/HAR/Burp/GraphQL/raw URL parsers
  reporting/              Markdown/HTML/PDF/JSON/CSV/Jira/GitHub exporters
  static/                 Web UI and themes
  storage/                Local JSON store
  models/                 Pydantic schemas
```

## External tool integrations

The `ExternalToolRunner` includes conservative wrappers for tools such as Nmap, httpx, nuclei, ffuf, katana, Amass, Subfinder, Burp/ZAP-style workflows, Semgrep, and TruffleHog. In this MVP, those integrations are dry-run unless explicitly approved. Commands are built for inspection and are not automatically executed by the UI.

## Development roadmap

### Version 0.2

- Add authenticated API test profiles with safe test-account boundaries
- Add CORS and rate-limit safe validators
- Add richer GraphQL schema inspection
- Add Postman environment variable redaction
- Add database option: SQLite

### Version 0.3

- Add Burp Suite extension
- Add VS Code extension
- Add Electron desktop wrapper
- Add local evidence viewer and screenshot manager
- Add Jira/GitHub ticket push integrations

### Version 1.0

- Add PostgreSQL and graph storage
- Add policy-as-code scope enforcement
- Add multi-user team mode
- Add cloud/SaaS deployment option
- Add model evaluation and agent telemetry
