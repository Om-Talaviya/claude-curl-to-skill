# claude-curl-to-skill

Turn one curl command from API docs into a working Claude Agent Skill —
a `SKILL.md` plus a runnable script — in one shot.

<p align="center">
  <img src="assets/demo.gif" alt="curl-to-skill Demo" width="100%" />
</p>

```
curl -H "Authorization: Bearer ..." -d '{...}' https://api.example.com/thing
                    │
                    ▼
example-thing/
├── SKILL.md          ← natural-language trigger + params doc
└── scripts/run.py    ← real script that makes the real call
```

## Deliberate v1 scope

This handles exactly one case, done properly, rather than many cases done
shakily:

- **Auth:** `Authorization: Bearer <token>` only.
- **Body:** a single flat JSON object via `-d`/`--data`/`--data-raw` only.
- **Everything else is rejected with a clear message**, not silently
  mangled: HTTP Basic auth (`-u`), form-encoded bodies, nested JSON,
  file uploads (`-F`), and anything without a URL.

Tested against 3 real docs examples in `examples/`:

| Source | Result |
|---|---|
| Resend (`emails`, Bearer + JSON) | ✅ generates a working skill |
| GitHub (`issues`, Bearer + JSON, extra headers/flags) | ✅ generates a working skill |
| Stripe (`customers`, Basic auth + form body) | ❌ correctly rejected, not mangled |

Run `python3 test_curl_to_skill.py` to re-check all three anytime you change
the parser.

## Usage

```bash
# from a quoted string
python3 curl_to_skill.py "curl https://api.resend.com/emails -H 'Authorization: Bearer re_123' -d '{\"to\":\"a@b.com\"}'"

# from a file (handles the multi-line \ continuations docs pages use)
python3 curl_to_skill.py --file examples/github.curl

# from stdin
pbpaste | python3 curl_to_skill.py -
```

Output goes to `./skills/<generated-name>/` by default (`--out` to change it).

Then actually use the generated skill:

```bash
export RESEND_API_KEY="your-real-key"
python3 skills/resend-create-email/scripts/run.py \
  --from "onboarding@resend.dev" --to "you@example.com" --subject "Hello"
```

## Why it's scoped this way

Real API docs are messier than the textbook Bearer+JSON case (OAuth,
SigV4 signing, Basic auth, multipart uploads). A tool that half-handles
those quietly produces broken skills, which is worse than a tool that
does 30% of cases correctly and says "not supported yet" for the rest.
v2 candidates, in rough order of how often they'd come up: query-param
API keys, Basic auth, and one level of nested JSON.

## Status

Built and dogfooded on 3 real endpoints, not yet posted anywhere. Next
step per the plan: use it on a couple more of your own APIs, then a
single focused post (Show HN / one tweet with a GIF) — not a mass
cross-post — before deciding whether it's worth expanding scope.
