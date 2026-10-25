"""Command-line interface; commands mentioned in instructions are never run."""
import argparse
import json
from . import __version__
from .audit import audit


def main(argv=None):
    parser = argparse.ArgumentParser(prog='instruction-drift', description='Check repository instruction claims offline.')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('audit', help='Audit instruction claims against repository files')
    check.add_argument('repo', nargs='?', default='.')
    check.add_argument('--files', nargs='+', action='extend')
    check.add_argument('--ignore', nargs='+', action='extend', default=[])
    check.add_argument('--json', action='store_true')
    check.add_argument('--fail-on', choices=('high', 'medium'), default='high')
    args = parser.parse_args(argv)
    report = audit(args.repo, args.files, args.ignore, args.fail_on)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print('Instruction files read: ' + (', '.join(report['files_read']) or 'none (no instruction files read)'))
        for finding in report['findings']:
            print('{file}:{line}: {severity} {kind}: {claim} — {detail}'.format(**finding))
        for error in report['parse_errors']:
            print('{file}: parse error: {detail}'.format(**error))
        print('Totals: ' + json.dumps(report['totals'], sort_keys=True))
        print('Ignored: {}; parse errors: {}'.format(report['ignored'], report['parse_error_count']))
        if report['truncated']:
            print('Report truncated at 500 findings.')
        print(report['verdict'])
    return report['exit_code']
