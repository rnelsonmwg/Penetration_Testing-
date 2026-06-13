"""Templates written by `thothansi init`."""

CONFIG_TEMPLATE = """\
# Thothansi configuration
# Secrets (API keys) belong in the environment / .env — never here.

active_provider: ollama          # ollama | claude | openai | groq | deepseek | grok
provider_model:                  # leave blank to use the provider default
provider_base_url:               # override API/Ollama base URL if needed
temperature: 0.2
max_tokens: 1500

theme: modern                    # modern | mythic
interactive: false               # true = step-gate each pipeline phase

data_dir: ./thothansi-data

recon:
  enabled_modules: [dns, crtsh, subdomains, fingerprint]
  request_timeout: 15.0
  max_concurrency: 8
  passive_only: true
  user_agent: "Thothansi/0.1 (+authorized-recon)"
"""

SCOPE_TEMPLATE = """\
# AUTHORIZED SCOPE
# Thothansi refuses to act on anything not listed here.
# Only add targets you have explicit written authorization to test.

engagement: "example-engagement"
authorized_by: "your-name / authorization-reference"

in_scope:
  - value: "example.com"          # apex + all subdomains
    note: "primary target"
  - value: "*.staging.example.com"  # subdomains only
  # - value: "203.0.113.0/24"     # an authorized IP range

out_of_scope:
  # Names/ranges that override in_scope (shared infra, third parties, etc.)
  - value: "blog.example.com"
"""
