"""Small, deliberately lexical instruction-claim extractors."""
from dataclasses import dataclass
import re

EXTENSIONS = ('.py', '.js', '.ts', '.md', '.json', '.yaml', '.yml',
              '.toml', '.sh', '.go', '.rs', '.txt')
ROOTS = ('src/', 'tests/', 'docs/', 'examples/', 'scripts/', 'bin/')
TOKEN = re.compile(r"[^\s`\"'<>|;()]+")
BACKTICK = re.compile(r'`([^`]+)`')
PROHIBITION = re.compile(
    r'\b(?:do not use|never use|must not use|avoid using)\s+`?([\w@][\w.\-@]*)',
    re.IGNORECASE)

@dataclass(frozen=True)
class Claim:
    line: int
    kind: str
    claim: str


def path_token(token):
    """Return a normalized path claim, or None for unsupported tokens."""
    token = token.lstrip(',:!?[]{}').rstrip('.,:!?[]{}')
    if '*' in token or '://' in token:
        return None
    bare = token[2:] if token.startswith('./') else token
    if '/' in bare and (bare.endswith(EXTENSIONS) or bare.startswith(ROOTS)):
        return token
    return None


def extract(text):
    """Extract claims in line order; command paths have a single kind."""
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        spans = list(BACKTICK.finditer(line))
        for match in TOKEN.finditer(line):
            path = path_token(match.group())
            if path:
                command = any(s.start(1) <= match.start() < s.end(1)
                              and (len(s.group(1).split()) > 1 or s.group(1).startswith('./'))
                              for s in spans)
                result.append(Claim(number, 'script-in-command' if command else
                                    'referenced-file', path))
        for span in spans:
            words = span.group(1).split()
            if len(words) >= 2 and words[0] == 'make' and not words[1].startswith('-'):
                result.append(Claim(number, 'script-in-command', 'make ' + words[1]))
        for match in PROHIBITION.finditer(line):
            result.append(Claim(number, 'prohibition-contradiction',
                                match.group(1).rstrip('.')))
    return list(dict.fromkeys(result))
