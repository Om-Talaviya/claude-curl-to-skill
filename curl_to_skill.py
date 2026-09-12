#!/usr/bin/env python3
"""
curl-to-skill (v1)

Turns ONE curl command into a working Claude Agent Skill folder:
  skill-name/
    SKILL.md
    scripts/run.py

v1 SCOPE (intentionally narrow — see README.md for why):
  - Auth:   Authorization: Bearer <token>   ONLY
  - Body:   a single, flat JSON object passed via -d/--data/--data-raw   ONLY
  - Method: whatever -X says, or POST if there's a body, else GET

Anything else (Basic auth, API-key-in-query, signed requests, multi-step
OAuth, form-encoded bodies, nested JSON, file uploads) is explicitly
detected and REJECTED with a clear message — not silently mangled.

Usage:
    python3 curl_to_skill.py "<curl command>" [--out DIR]
    python3 curl_to_skill.py --file examples/resend.curl
    echo "curl ..." | python3 curl_to_skill.py -
"""
import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse


class UnsupportedCurl(Exception):
    """Raised when the curl command needs a feature v1 doesn't handle."""


# ---------------------------------------------------------------- parsing --

def parse_curl(raw: str) -> dict:
    """Tokenize a curl command and pull out method/headers/data/url.

    Deliberately simple: this is a v1 tool, not a full curl-argument parser.
    """
    cleaned = raw.strip()
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    # collapse line continuations (`\` + newline) used in copy-pasted docs
    cleaned = re.sub(r"\\\s*\n", " ", cleaned)

    try:
        tokens = shlex.split(cleaned)
    except ValueError as e:
        raise UnsupportedCurl(f"couldn't tokenize the command ({e}). "
                               f"Check for unmatched quotes.")

    if not tokens:
        raise UnsupportedCurl("empty command")
    if tokens[0] != "curl":
        raise UnsupportedCurl("command doesn't start with 'curl'")
    tokens = tokens[1:]

    method = None
    headers: dict[str, str] = {}
    data = None
    url = None
    basic_auth = False
    unsupported_flags = []

    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t in ("-X", "--request"):
            method = tokens[i + 1]
            i += 2
            continue

        if t in ("-H", "--header"):
            header_parts = [tokens[i + 1]] if i + 1 < len(tokens) else []
            i += 2
            while i < len(tokens) and not tokens[i].startswith("-") and not tokens[i].startswith("http"):
                header_parts.append(tokens[i])
                i += 1
            raw_header = " ".join(header_parts)
            if ":" in raw_header:
                k, v = raw_header.split(":", 1)
                headers[k.strip()] = v.strip()
            continue

        if t in ("-d", "--data", "--data-raw", "--data-binary"):
            data_parts = [tokens[i + 1]] if i + 1 < len(tokens) else []
            i += 2
            while i < len(tokens) and not (tokens[i].startswith("-") and len(tokens[i]) == 2 and not tokens[i].startswith("--")) and not (data_parts and data_parts[-1].endswith("}")):
                data_parts.append(tokens[i])
                i += 1
            data = " ".join(data_parts)
            continue

        if t in ("-u", "--user"):
            basic_auth = True
            i += 2
            continue

        if t in ("--data-urlencode", "-F", "--form"):
            unsupported_flags.append(t)
            i += 2
            continue

        if t.startswith("http"):
            url = t
            i += 1
            continue

        # unknown flag: assume it takes no value (covers -L, -s, -v, --compressed...)
        if t.startswith("-"):
            i += 1
            continue

        i += 1

    if url is None:
        raise UnsupportedCurl("couldn't find a URL in the command")

    if basic_auth:
        raise UnsupportedCurl(
            "uses HTTP Basic auth (-u). v1 only supports "
            "'Authorization: Bearer <token>' headers."
        )
    if unsupported_flags:
        raise UnsupportedCurl(
            f"uses {', '.join(unsupported_flags)} (form-encoded / multipart data). "
            f"v1 only supports a flat JSON body via -d."
        )

    if method is None:
        method = "POST" if data else "GET"

    return {"method": method.upper(), "headers": headers, "data": data, "url": url}


def extract_bearer_env(headers: dict) -> str | None:
    for k, v in headers.items():
        if k.lower() == "authorization" and v.lower().startswith("bearer "):
            return v.split(" ", 1)[1].strip()
    return None


def parse_json_body(data: str | None) -> list[dict]:
    """Return [{name, type, example}] for a flat JSON object, or raise."""
    if data is None:
        return []
    
    data_clean = data.strip()
    if (data_clean.startswith('"') and data_clean.endswith('"')) or (data_clean.startswith("'") and data_clean.endswith("'")):
        data_clean = data_clean[1:-1].strip()

    # Normalize backslash-escaped quotes commonly found in docs or CLI inputs
    if r'\"' in data_clean:
        data_clean = data_clean.replace(r'\"', '"')
    if r"\'" in data_clean:
        data_clean = data_clean.replace(r"\'", "'")

    obj = None
    # 1. Try standard JSON
    try:
        obj = json.loads(data_clean)
    except json.JSONDecodeError:
        pass

    # 2. Try ast literal eval (for Python dict / single quotes)
    if obj is None:
        try:
            import ast
            parsed_ast = ast.literal_eval(data_clean)
            if isinstance(parsed_ast, dict):
                obj = parsed_ast
        except Exception:
            pass

    # 3. Try recovering unquoted keys/values (common when PowerShell strips nested quotes)
    if obj is None and (data_clean.startswith("{") and data_clean.endswith("}")):
        try:
            fixed = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', data_clean)
            fixed = re.sub(r':\s*([a-zA-Z0-9_@\.\-\+!]+)(\s*[,}])', r':"\1"\2', fixed)
            obj = json.loads(fixed)
        except Exception:
            pass

    if obj is None or not isinstance(obj, dict):
        raise UnsupportedCurl(
            "the -d body isn't valid JSON (looks form-encoded, e.g. "
            "'key=value'). v1 only supports a JSON object body."
        )

    fields = []
    for k, v in obj.items():
        if isinstance(v, bool):
            t = "boolean"
        elif isinstance(v, (int, float)):
            t = "number"
        elif isinstance(v, str):
            t = "string"
        else:
            raise UnsupportedCurl(
                f"field '{k}' is a nested object/array. v1 only supports "
                f"flat (non-nested) JSON bodies."
            )
        fields.append({"name": k, "type": t, "example": v})
    return fields


# ------------------------------------------------------------- naming ----

_STOPWORDS = {"api", "www", "com", "org", "io", "net", "co", "dev", "app", "v1", "v2"}


def service_name(url: str) -> str:
    host = urlparse(url).netloc.split(":")[0]
    for part in host.split("."):
        if part.lower() not in _STOPWORDS:
            return re.sub(r"[^a-z0-9]", "", part.lower()) or "service"
    return re.sub(r"[^a-z0-9]", "", host.split(".")[0].lower()) or "service"


def _singularize(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def resource_name(url: str) -> str:
    path = urlparse(url).path.strip("/")
    segments = [s for s in path.split("/") if s and not s.isdigit()
                and not re.match(r"^[{:<].*[}:>]?$", s)]
    leaf = segments[-1] if segments else ""
    leaf = re.sub(r"[^a-zA-Z0-9]+", "-", leaf).strip("-").lower()
    return _singularize(leaf) if leaf else ""


_VERB_BY_METHOD = {"POST": "create", "GET": "get", "PUT": "update",
                    "PATCH": "update", "DELETE": "delete"}


def make_skill_name(service: str, resource: str, method: str) -> str:
    verb = _VERB_BY_METHOD.get(method, "call")
    parts = [service, verb] + ([resource] if resource else [])
    name = "-".join(parts)
    return re.sub(r"-+", "-", name).strip("-")


# ------------------------------------------------------------- rendering -

SKILL_MD_TEMPLATE = '''---
name: {name}
description: Call the {service} API ({method} {path}) - {verb_phrase} {resource_phrase}. Use this whenever the user asks to {trigger_phrase} via {service}.
---

# {title}

Calls `{method} {url}`.

Auto-generated by curl-to-skill (v1) from a single curl example. It only
handles Bearer-token auth and a flat JSON body - see LIMITATIONS below
before relying on it for anything more complex.

## Setup

This skill needs an API key in the `{env_var}` environment variable:

```bash
export {env_var}="your-api-key-here"
```

## Usage

Run the bundled script with the required fields as flags:

```bash
python3 scripts/run.py{example_args}
```

## Parameters

| Field | Type | Example |
|---|---|---|
{param_rows}

## Limitations (v1)

- Auth: Bearer token only (no OAuth, no signed requests like AWS SigV4, no Basic auth).
- Body: flat JSON object only (no nested objects, arrays, or file uploads).
- No pagination, retries, or rate-limit handling.
- Generated from one example call - re-check against the real API docs for
  anything this doesn't cover.
'''

RUN_PY_TEMPLATE = '''#!/usr/bin/env python3
"""Auto-generated by curl-to-skill (v1). {method} {url}"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_KEY_ENV = "{env_var}"
URL = "{url}"
METHOD = "{method}"
FIELDS = {fields!r}


def main():
    parser = argparse.ArgumentParser(description="Call {service}: {method} {url}")
    for f in FIELDS:
        parser.add_argument(f"--{{f}}", required=True, help=f"value for '{{f}}'")
    parser.add_argument("--api-key", default=os.environ.get(API_KEY_ENV), help=f"API key (default: from {{API_KEY_ENV}} env var)")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key:
        print(f"Error: provide --api-key or set the {{API_KEY_ENV}} environment variable first.", file=sys.stderr)
        sys.exit(1)

    body = {{f: getattr(args, f) for f in FIELDS}}
    data = json.dumps(body).encode() if FIELDS else None

    req = urllib.request.Request(URL, data=data, method=METHOD)
    req.add_header("Authorization", f"Bearer {{api_key}}")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            print(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP {{e.code}}: {{e.read().decode()}}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def render_skill(parsed: dict, out_dir: Path) -> Path:
    method, url, headers, data = parsed["method"], parsed["url"], parsed["headers"], parsed["data"]

    token = extract_bearer_env(headers)
    if token is None:
        raise UnsupportedCurl(
            "no 'Authorization: Bearer <token>' header found. "
            "v1 only supports Bearer-token auth."
        )

    fields = parse_json_body(data)

    service = service_name(url)
    resource = resource_name(url)
    skill_name = make_skill_name(service, resource, method)
    env_var = f"{service.upper()}_API_KEY"
    path = urlparse(url).path

    param_rows = "\n".join(
        f"| `{f['name']}` | {f['type']} | `{f['example']}` |" for f in fields
    ) or "| _(none — no body fields)_ | | |"

    example_args = "".join(f' --{f["name"]} "{f["example"]}"' for f in fields)

    resource_phrase = resource.replace("-", " ") if resource else "resource"
    article = "an" if resource_phrase[:1].lower() in "aeiou" else "a"
    verb = _VERB_BY_METHOD.get(method, "call")
    verb_phrase = {"create": f"create {article}", "get": f"fetch {article}",
                   "update": f"update {article}", "delete": f"delete {article}",
                   "call": "call the"}.get(verb, "call the")
    trigger_phrase = f"{verb} {article} {resource_phrase}".strip()

    skill_dir = out_dir / skill_name
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    skill_md = SKILL_MD_TEMPLATE.format(
        name=skill_name,
        service=service,
        method=method,
        path=path,
        verb_phrase=verb_phrase,
        resource_phrase=resource_phrase,
        trigger_phrase=trigger_phrase,
        title=skill_name.replace("-", " ").title(),
        url=url,
        env_var=env_var,
        example_args=example_args,
        param_rows=param_rows,
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    run_py = RUN_PY_TEMPLATE.format(
        env_var=env_var, url=url, method=method,
        fields=[f["name"] for f in fields], service=service,
    )
    run_path = scripts_dir / "run.py"
    run_path.write_text(run_py, encoding="utf-8")
    try:
        run_path.chmod(0o755)
    except Exception:
        pass

    return skill_dir


# ------------------------------------------------------------------ CLI --

def main():
    ap = argparse.ArgumentParser(description="Convert one curl command into a Claude Skill.")
    ap.add_argument("curl_command", nargs="*", help="the curl command, quoted. Use '-' to read from stdin.")
    ap.add_argument("--file", help="read the curl command from a file instead")
    ap.add_argument("--out", default="./skills", help="output directory (default: ./skills)")
    args = ap.parse_args()

    if args.file:
        raw = Path(args.file).read_text(encoding="utf-8")
    elif args.curl_command and args.curl_command[0] == "-":
        raw = sys.stdin.read()
    elif not args.curl_command and not sys.stdin.isatty():
        raw = sys.stdin.read()
    elif args.curl_command:
        raw = " ".join(args.curl_command)
    else:
        ap.error("provide a curl command, --file, or pipe one in via stdin")

    try:
        parsed = parse_curl(raw)
        skill_dir = render_skill(parsed, Path(args.out))
    except UnsupportedCurl as e:
        print(f"[-] Can't generate a skill from this curl command: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"[+] Generated skill: {skill_dir}")
    print(f"  - {skill_dir / 'SKILL.md'}")
    print(f"  - {skill_dir / 'scripts' / 'run.py'}")


if __name__ == "__main__":
    main()
