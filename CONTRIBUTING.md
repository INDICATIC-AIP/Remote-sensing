# How to contribute

Thanks for reading — contributions (code, tests, docs) are welcome.

Quick start
- Read `README.md` for project context and Jetson-specific notes.
- Browse Issues and pick one labeled `good first issue` or `help wanted`.
- If nothing fits, open an issue describing what you'd like to do.

Report a bug
- Search existing issues first.
- Include: short title, steps to reproduce, expected vs actual behavior, environment (OS, Python, Jetson model), and relevant logs.

Request an enhancement
- Open an issue with motivation and a short suggested approach. Use the `enhancement` label.

Submit a change (PR)
- Fork → branch (`fix/...` or `feature/...`) → commit → push → open a PR.
- Commit message style:

```bash
git commit -m "Short summary

Longer description explaining what changed and why."
```
- In the PR body, describe how to test the change and link related issues (e.g., `Closes #123`).

Minimal PR checklist
- I read `README.md` and this guide.
- I ran formatters/linting and fixed warnings (see below).
- Tests pass locally or manual verification steps are provided.

Code style and linting (essentials)

Python
- Target: Python 3.10+.
- Format with `black`; sort imports with `isort`; lint with `ruff` or `flake8`.
- Minimal commands:

```bash
pip3 install --user black isort ruff
black code/ INDIcode/ NAScode/ AutoRun/
isort code/ INDIcode/ NAScode/ AutoRun/
ruff check code/ INDIcode/ NAScode/ AutoRun/
```

If tools cannot be installed on a device, ensure files compile:

```bash
python3 -m py_compile <file.py>
python3 -m pip check
```

Shell scripts
- Prefer POSIX-compatible shell; `bash` is acceptable when needed.
- Use `set -euo pipefail` for non-trivial scripts.
- Quick checks:

```bash
bash -n <script.sh>
shellcheck <script.sh>
```

Security note
- Encryption/decryption code is intentionally excluded. Do not commit keys or credentials. Document how encrypted data is handled and tested locally.

Contacts
- Dr. Jose Robles — `jrobles@indicatic.org.pa` (technical/scientific)
- Jose Jaen — `jose.jaenj08@hotmail.com` (code)
- Alexandre Olivie — `alexandre.olivie@bordeaux-inp.fr` (code)

If you want, I can add very small PR and issue templates and a basic `.pre-commit-config.yaml` to the repo — tell me which and I'll add them.

Thank you — small fixes, tests and documentation are very helpful.
