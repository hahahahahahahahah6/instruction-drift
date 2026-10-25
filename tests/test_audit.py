from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from instruction_drift.audit import audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, content=''):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def check(self, content, **kwargs):
        self.write('AGENTS.md', content)
        return audit(self.root, **kwargs)

    def test_empty(self):
        self.assertEqual(audit(self.root)['exit_code'], 0)

    def test_exists(self):
        self.write('src/app.py')
        self.assertEqual(self.check('src/app.py')['findings'], [])

    def test_missing(self):
        r = self.check('src/missing.py')
        self.assertEqual((r['exit_code'], r['totals']['severity']['HIGH']), (2, 1))

    def test_directory_exists(self):
        (self.root / 'tests/unit').mkdir(parents=True)
        self.assertEqual(self.check('tests/unit/')['exit_code'], 0)

    def test_directory_missing(self):
        self.assertEqual(self.check('tests/old/')['exit_code'], 2)

    def test_directory_is_file(self):
        self.write('tests/unit')
        self.assertEqual(self.check('tests/unit/')['exit_code'], 2)

    def test_url_glob(self):
        self.assertEqual(self.check('https://site/a.py src/*.py')['findings'], [])

    def test_absolute_outside(self):
        self.assertEqual(self.check('/outside/missing.py')['findings'], [])

    def test_absolute_inside(self):
        self.assertEqual(self.check(str(self.root / 'missing.py'))['exit_code'], 2)

    def test_parent_outside(self):
        self.assertEqual(self.check('../outside/a.py')['exit_code'], 0)

    def test_command_missing(self):
        r = self.check('`python scripts/run.py`')
        self.assertEqual(r['totals']['kind']['script-in-command'], 1)
        self.assertEqual(len(r['findings']), 1)

    def test_command_exists(self):
        self.write('scripts/run.sh')
        self.assertEqual(self.check('`./scripts/run.sh`')['exit_code'], 0)

    def test_make_present(self):
        self.write('Makefile', '# fake:\nNAME := x\ncheck:\n\ttrue\n')
        self.assertEqual(self.check('`make check`')['exit_code'], 0)

    def test_make_absent(self):
        self.write('Makefile', '# fake:\nNAME := x\ncheck:\n')
        self.assertEqual(self.check('`make fake` `make NAME`')['totals']['severity']['HIGH'], 2)

    def test_make_without_makefile(self):
        self.assertEqual(self.check('`make check`')['exit_code'], 0)

    def test_python_import(self):
        self.write('src/a.py', 'import legacy\n')
        self.assertEqual(self.check('Never use legacy')['exit_code'], 1)

    def test_python_from(self):
        self.write('src/a.py', 'from legacy import client\n')
        self.assertEqual(self.check('Never use legacy')['exit_code'], 1)

    def test_multiple_python_imports(self):
        self.write('src/a.py', 'import os, legacy as old\n')
        self.assertEqual(self.check('Never use legacy')['exit_code'], 1)

    def test_js_ts(self):
        for suffix, code in [('js', "const x = require('legacy');"), ('ts', "import x from 'legacy';")]:
            with self.subTest(suffix=suffix):
                self.write('src/a.' + suffix, code)
                self.assertEqual(self.check('Never use legacy')['exit_code'], 1)

    def test_fail_medium(self):
        self.write('src/a.py', 'import legacy')
        self.assertEqual(self.check('Never use legacy', fail_on='medium')['exit_code'], 2)

    def test_no_self_match(self):
        self.assertEqual(self.check('Never use legacy\nimport legacy')['exit_code'], 0)

    def test_custom_instruction_excluded(self):
        self.write('rules.py', 'Never use legacy\nimport legacy')
        self.assertEqual(audit(self.root, files=['rules.py'])['exit_code'], 0)

    def test_skipped_directories(self):
        for directory in ('.git', 'node_modules', 'dist', '__pycache__', '.venv', 'venv', '.hidden'):
            self.write(directory + '/x.py', 'import legacy')
        self.assertEqual(self.check('Never use legacy')['exit_code'], 0)

    def test_ignore(self):
        r = self.check('scripts/old.py', ignore=['scripts/*'])
        self.assertEqual((r['ignored'], r['exit_code']), (1, 0))

    def test_dedup(self):
        self.assertEqual(len(self.check('src/a.py src/a.py')['findings']), 1)

    def test_distinct_lines(self):
        self.assertEqual(len(self.check('src/a.py\nsrc/a.py')['findings']), 2)

    def test_default_order(self):
        for name in ('MUSE.md', 'CLAUDE.md', 'AGENTS.md', 'CONTRIBUTING.md'):
            self.write(name, 'src/a.py')
        self.assertEqual(audit(self.root)['files_read'], ['AGENTS.md', 'CLAUDE.md', 'MUSE.md', 'CONTRIBUTING.md'])

    def test_explicit_missing(self):
        self.assertEqual(audit(self.root, files=['absent.md'])['parse_error_count'], 1)

    def test_invalid_utf8(self):
        (self.root / 'AGENTS.md').write_bytes(b'\xff')
        self.assertEqual(audit(self.root)['exit_code'], 2)

    def test_unreadable(self):
        self.write('AGENTS.md')
        with patch.object(Path, 'read_text', side_effect=PermissionError('denied')):
            r = audit(self.root)
        self.assertEqual((r['parse_error_count'], r['exit_code']), (1, 2))

    def test_cap_order(self):
        r = self.check('\n'.join('src/missing%d.py' % n for n in range(502)))
        self.assertEqual(len(r['findings']), 500)
        self.assertTrue(r['truncated'])
        self.assertEqual(r['findings'][-1]['line'], 500)

    def test_exact_cap(self):
        r = self.check('\n'.join('src/missing%d.py' % n for n in range(500)))
        self.assertFalse(r['truncated'])

    def test_realistic(self):
        self.write('scripts/new.py')
        self.write('checks/test_app.py')
        self.write('src/app.py', 'import legacy')
        r = self.check('Run `python scripts/old.py`\nTests: tests/old/\nNever use legacy')
        self.assertEqual(r['totals']['severity'], {'HIGH': 2, 'MEDIUM': 1})
        self.assertEqual(r['exit_code'], 2)
        self.assertIn('verify manually', r['findings'][-1]['detail'])

    def test_invalid_repo(self):
        self.assertEqual(audit(self.root / 'missing')['exit_code'], 2)

    def test_high_after_cap_still_fails(self):
        self.write('src/a.py', 'import legacy')
        r = self.check('Never use legacy\n' * 500 + 'src/missing.py')
        self.assertTrue(r['truncated'])
        self.assertEqual(r['totals']['severity']['HIGH'], 0)
        self.assertEqual(r['exit_code'], 2)
