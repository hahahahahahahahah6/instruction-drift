# instruction-drift

An offline, deterministic, stdlib-only Python CLI that checks concrete instruction
claims against repository files. A finding means **check this claim**. It does
not establish that an instruction is wrong. No daemon, LLM, network, or keys.

Requires Python 3.9+. Install a locally built wheel with `pip install
/path/to/instruction_drift-0.1.0-py3-none-any.whl`.

```sh
instruction-drift audit .
instruction-drift audit examples/sample-repo --json
instruction-drift audit . --files AGENTS.md CONTRIBUTING.md --ignore 'docs/*'
instruction-drift audit . --fail-on medium
instruction-drift --version
instruction-drift --help
```

The repository defaults to the current directory. Default instruction files,
in order, are root AGENTS.md, CLAUDE.md, MUSE.md, and CONTRIBUTING.md. Missing
default files are skipped; an empty repository passes with a note. `--files`
replaces that list with paths relative to the repository. Missing explicitly
requested files, unreadable files, and invalid UTF-8 produce parse errors.
`--files` and `--ignore` accept multiple arguments and can be repeated.

Checks are heuristic:

- **referenced-file (HIGH):** missing path tokens containing `/` and ending in
  .py, .js, .ts, .md, .json, .yaml, .yml, .toml, .sh, .go, .rs, or .txt;
  also directory references rooted under src/, tests/, docs/, examples/,
  scripts/, or bin/. Trailing `/` requires a directory. Paths resolve relative
  to the repository root. URLs, tokens containing `*`, and paths resolving
  outside the repository are skipped.
- **script-in-command (HIGH):** missing path tokens in backticked commands;
  missing `make target` targets when a root Makefile exists. Simple literal
  target definitions are recognized; Makefile variables and comments are not
  definitions. A command path is reported once rather than also as a reference.
- **prohibition-contradiction (MEDIUM):** “do not use”, “never use”, “must not
  use”, or “avoid using” followed by an identifier also found in a Python
  import/from import or JS/TS require/from import. Verify manually: exceptions
  and test fixtures may be intentional. Instruction files are excluded from
  source search. Hidden directories, .git, node_modules, dist, __pycache__,
  .venv, and venv are skipped, as are symlinked directories.

The report includes files read, file:line locations, kinds, claims, severities,
details, totals by kind and severity, ignored count, parse-error count, and a
PASS/WARN/FAIL verdict. `--json` exposes the same information as valid JSON.
Claims matching `--ignore` glob patterns are excluded and counted before
checking their validity. Findings are deduplicated by file, line, kind, and
claim. At most 500 findings are retained in instruction-file and line order;
additional findings set the truncation flag. Totals describe retained findings. Failure thresholds still apply to findings
beyond the display cap.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | PASS: no findings and no parse errors |
| 1 | WARN: findings exist, but none reach the failure threshold |
| 2 | FAIL: a finding reaches the threshold, or any parse error occurs |

The default threshold is HIGH; `--fail-on medium` also fails MEDIUM findings.
For example, the synthetic sample repo cites a renamed script and moved test
directory, and prohibits an identifier imported in src/app.py. Auditing it
returns two HIGH findings, one MEDIUM finding, and exit code 2. Its illustrative
import does not require an installed dependency because commands are never run.

## Limitations

This is pattern matching, not semantic judgement. Paraphrased claims are not
checked. A MEDIUM contradiction needs human review. Commands are not executed;
only path tokens and simple Makefile target names are checked. Dynamic imports,
complex shell syntax, generated paths, multiline imports, Makefile includes and
computed targets, and language-specific resolution are not interpreted.
Lexical import patterns may match comments or strings and may miss real imports.
Source files that cannot be decoded or read are skipped; this can hide import
matches. Instruction-file read failures always produce parse errors. A truncated
report is incomplete. Filesystem changes during a scan can affect its results.

## Differentiation

- **startup-trust-guard** audits TRUST: can an attacker plant or rewrite the
  instruction file? instruction-drift audits TRUTH: is what it says still true
  about the on-disk repository?
- **rules-doctor** audits rule-file health and structure. This tool cross-checks
  instruction claims against the on-disk repo.
- **edit-guard** blocks edits made on stale reads. This tool finds stale
  instructions that can cause those edits.
- **context-mode / heavy runtimes:** this is an offline stdlib CLI with no
  daemon, no LLM, and no network.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m build
```

Building requires setuptools, wheel, and the build frontend already installed
for offline use. Runtime and tests use only the Python standard library.
