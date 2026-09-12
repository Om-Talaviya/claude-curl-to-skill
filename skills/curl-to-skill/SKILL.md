---
name: curl-to-skill
description: Converts API curl commands from documentation into fully functional Claude Agent Skills (complete with natural-language triggers, YAML frontmatter, parameter documentation, and a standalone executable runner script). Use whenever the user provides a curl command, asks to wrap a curl request into a skill, or asks to generate an agent skill from an API endpoint.
---

# curl-to-skill

Turn one `curl` command from API documentation into a working Claude Agent Skill — generating both a `SKILL.md` instruction file and a runnable Python script (`scripts/run.py`).

## Core Capabilities

1. **Automatic Schema & Parameter Inference**: Parses URL, HTTP method, headers (`Authorization: Bearer`), and JSON request bodies to construct structured argument tables.
2. **Deterministic Code Generation**: Produces a self-contained, typed Python runner script with built-in CLI flags (`argparse`) and environment variable guards.
3. **Agent Trigger Generation**: Formats semantic trigger phrases and clear operational guidance into the generated `SKILL.md`.

## CLI Usage

Run the synthesizer directly from the workspace:

```bash
# Direct command line input
python curl_to_skill.py "curl https://api.resend.com/emails -H 'Authorization: Bearer re_123' -d '{\"from\":\"a@b.com\",\"to\":\"c@d.com\",\"subject\":\"Hi\"}'"

# From a file with line continuations
python curl_to_skill.py --file examples/resend.curl

# Specify custom output directory
python curl_to_skill.py --file examples/github.curl --out ./generated-skills
```

## Supported Scope (v1 Standard)

- **Authentication**: `Authorization: Bearer <TOKEN>` (mapped to environment variables e.g., `<SERVICE>_API_KEY`).
- **Body**: Flat JSON payload passed via `-d`, `--data`, `--data-raw`, or `--data-binary`.
- **Validation**: Strict boundary rejection for unsupported formats (Basic Auth, multi-part form uploads) to avoid silent failures.
