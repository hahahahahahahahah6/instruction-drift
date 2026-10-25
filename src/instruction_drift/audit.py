"""Deterministic, offline comparison of lexical claims with disk contents."""
from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase
import os
from pathlib import Path
import re
from .extract import extract

DEFAULT_FILES = ('AGENTS.md', 'CLAUDE.md', 'MUSE.md', 'CONTRIBUTING.md')
SKIP = {'node_modules', 'dist', '__pycache__', 'venv'}

@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    kind: str
    claim: str
    severity: str
    detail: str


def imports(root, excluded):
    identifiers = set()
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIP
                         and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.resolve() in excluded or path.suffix not in ('.py', '.js', '.ts'):
                continue
            try:
                content = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                continue
            if path.suffix == '.py':
                for match in re.finditer(r'^\s*(?:from\s+([\w.]+)\s+import\b|import\s+([^\n;#]+))', content, re.M):
                    if match.group(1):
                        identifiers.add(match.group(1))
                    else:
                        identifiers.update(part.strip().split()[0] for part in
                                           match.group(2).split(',') if part.strip())
            else:
                identifiers.update(re.findall(r'''(?:require\(\s*|\bfrom\s*)['"]([^'"]+)['"]''', content))
    return identifiers


def audit(repo='.', files=None, ignore=(), fail_on='high'):
    root = Path(repo).resolve()
    names = list(DEFAULT_FILES if files is None else files)
    report = dict(files_read=[], findings=[], ignored=0, parse_errors=[], truncated=False)
    if not root.is_dir():
        report['parse_errors'].append({'file': str(repo), 'detail': 'Repository is not a directory'})
    excluded = {(root / name).resolve() for name in names}
    used = imports(root, excluded) if root.is_dir() else set()
    targets = None
    seen = set()
    threshold_hit = False
    for name in names if root.is_dir() else []:
        path = root / name
        if files is None and not path.exists():
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            report['parse_errors'].append({'file': name, 'detail': str(error)})
            continue
        report['files_read'].append(name)
        for item in extract(content):
            key = (name, item.line, item.kind, item.claim)
            if key in seen:
                continue
            seen.add(key)
            if any(fnmatchcase(item.claim, pattern) for pattern in ignore):
                report['ignored'] += 1
                continue
            severity, detail = 'HIGH', ''
            if item.kind == 'prohibition-contradiction':
                if item.claim not in used:
                    continue
                severity = 'MEDIUM'
                detail = 'Identifier appears in source imports; verify manually.'
            elif item.claim.startswith('make '):
                makefile = root / 'Makefile'
                if not makefile.exists():
                    continue
                if targets is None:
                    try:
                        targets = set(re.findall(r'^([A-Za-z0-9_.-]+)\s*:(?!=)', makefile.read_text(encoding='utf-8'), re.M))
                    except (OSError, UnicodeError) as error:
                        report['parse_errors'].append({'file': 'Makefile', 'detail': str(error)})
                        targets = set()
                if item.claim[5:] in targets:
                    continue
                detail = 'Target not found in root Makefile.'
            else:
                candidate = root / item.claim
                try:
                    candidate.resolve().relative_to(root)
                except ValueError:
                    continue
                exists = candidate.is_dir() if item.claim.endswith('/') else candidate.exists()
                if exists:
                    continue
                detail = 'Referenced path does not exist' + (' as a directory.' if item.claim.endswith('/') else '.')
            threshold_hit = threshold_hit or severity == 'HIGH' or fail_on == 'medium'
            if len(report['findings']) < 500:
                report['findings'].append(asdict(Finding(name, item.line, item.kind, item.claim, severity, detail)))
            else:
                report['truncated'] = True
    findings = report['findings']
    report['totals'] = {'kind': {k: sum(f['kind'] == k for f in findings) for k in
                               ('referenced-file', 'script-in-command', 'prohibition-contradiction')},
                        'severity': {s: sum(f['severity'] == s for f in findings) for s in ('HIGH', 'MEDIUM')}}
    failed = report['parse_errors'] or threshold_hit
    report['exit_code'] = 2 if failed else (1 if findings else 0)
    report['verdict'] = {0: 'PASS', 1: 'WARN', 2: 'FAIL'}[report['exit_code']]
    report['parse_error_count'] = len(report['parse_errors'])
    return report
