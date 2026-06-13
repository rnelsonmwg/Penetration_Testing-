# Khepri Nyame Design Notes

## Product identity

**Khepri Nyame** combines Egyptian and African mythology in a subtle product identity:

- **Khepri**: Egyptian scarab symbolizing emergence, transformation, and discovery.
- **Nyame**: Akan sky deity symbolizing wide visibility and perspective.

The brand should feel mysterious without becoming theatrical. The UI uses motif-level hints, not a fully themed fantasy interface.

## User-selected experience modes

The first screen asks the operator to choose one of three modes:

1. **Guided wizard** — step-by-step safe workflow for newer users or training labs.
2. **Autonomous agent** — AI-assisted planning and prioritization, still human-gated for active checks.
3. **Modular toolkit** — experienced operators select specific importers, agents, and reports.

## Themes

1. **Clean enterprise security platform**
   - Palette: desert sand / obsidian
   - Use case: internal enterprise testing and leadership reporting

2. **Bug bounty hacker toolkit**
   - Palette: green / bronze
   - Use case: bug bounty hunting, recon review, personal lab workflows

3. **Cyber operations console**
   - Palette: deep blue / gold
   - Use case: red-team style operations, SOC/IR collaboration, executive demos

## Core architecture

```text
Khepri Nyame
├── UI Layer
│   ├── FastAPI web dashboard
│   ├── CLI
│   ├── future VS Code extension
│   ├── future Burp extension
│   └── future Electron desktop app
├── Workflow Layer
│   ├── guided wizard
│   ├── autonomous planner
│   └── modular toolkit runner
├── Agent Layer
│   ├── Recon Agent
│   ├── API Mapper Agent
│   ├── AuthZ Tester Agent
│   ├── Secret Review Agent
│   ├── Risk Prioritization Agent
│   └── Report Writer Agent
├── AI Provider Layer
│   ├── local rule-based planner
│   ├── Ollama
│   ├── OpenAI placeholder
│   ├── Claude placeholder
│   └── DeepSeek placeholder
├── Import Layer
│   ├── OpenAPI / Swagger
│   ├── Postman
│   ├── HAR
│   ├── Burp
│   ├── GraphQL
│   └── raw URLs / notes
├── Safety Layer
│   ├── authorization statement
│   ├── scope tracking
│   ├── human approval gate
│   ├── blocked action terms
│   └── secret redaction
├── Storage Layer
│   └── local JSON
└── Reporting Layer
    ├── Markdown
    ├── HTML
    ├── PDF
    ├── JSON
    ├── CSV
    ├── executive summary
    ├── Jira text
    └── GitHub issue markdown
```

## Safe-by-default testing model

The first version does not execute exploits. It performs passive and static analysis over imported artifacts and produces safe validation guidance.

Examples:

- It identifies BOLA/BFLA candidates from ID-bearing routes.
- It identifies SSRF/open redirect review candidates from URL-like parameters.
- It identifies injection review candidates from search/filter/query parameters.
- It identifies mass-assignment review candidates from request bodies and sensitive mutable field names.
- It identifies possible secrets in imported artifacts and redacts evidence.

## Explicitly excluded from MVP execution

- brute force
- password spraying
- credential stuffing
- exploit execution
- payloads intended to modify, destroy, or extract data
- stealth scanning
- persistence
- evasion
- lateral movement
- production data access beyond approved testing

## Versioning plan

### v0.1 current scaffold

- Local FastAPI app
- CLI
- Local JSON store
- Static UI with mode/theme radio buttons
- Import parsers
- Passive multi-agent workflow
- Report exporters

### v0.2

- Authenticated test profile manager
- Safe CORS/rate-limit validators
- Better GraphQL inspection
- SQLite optional storage
- Evidence vault with screenshot metadata

### v0.3

- Burp Suite extension
- VS Code extension
- Electron desktop shell
- Jira/GitHub push integrations
- Model provider settings UI

### v1.0

- PostgreSQL and graph storage
- Team mode
- SaaS/cloud option
- Policy-as-code scope enforcement
- Agent telemetry and model evaluation
