# Contributing to curl-to-skill

Thank you for your interest in improving `curl-to-skill`!

## Development Guidelines

1. **Keep it Minimal and Deterministic**: Follow the YAGNI principle. Avoid complex dependencies where Python standard libraries (`urllib.request`, `argparse`, `shlex`, `re`) suffice.
2. **Strict Failure Boundaries**: When an incoming curl command contains unsupported constructs (e.g., multipart files, basic auth), reject early with helpful error messaging rather than producing corrupted skills.
3. **Run Regression Tests**:
   Before submitting any changes or opening a PR, always ensure tests pass:
   ```bash
   python test_curl_to_skill.py
   ```
