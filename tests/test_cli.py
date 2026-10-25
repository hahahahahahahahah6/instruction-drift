from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from instruction_drift.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(['audit', str(self.root), *args])
        return code, out.getvalue()

    def test_empty_note(self):
        code, out = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn('no instruction files', out)
        self.assertIn('PASS', out)

    def test_json(self):
        code, out = self.run_cli('--json')
        r = json.loads(out)
        self.assertEqual(r['exit_code'], code)
        self.assertEqual(r['parse_error_count'], 0)

    def test_high(self):
        (self.root / 'AGENTS.md').write_text('src/missing.py')
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('AGENTS.md:1: HIGH', out)

    def test_warn_and_threshold(self):
        (self.root / 'AGENTS.md').write_text('Never use legacy')
        (self.root / 'app.py').write_text('import legacy')
        self.assertEqual(self.run_cli()[0], 1)
        self.assertEqual(self.run_cli('--fail-on', 'medium')[0], 2)

    def test_parse_error(self):
        (self.root / 'AGENTS.md').write_bytes(b'\xff')
        code, out = self.run_cli('--json')
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['parse_error_count'], 1)

    def test_repeat_files_ignore(self):
        (self.root / 'one.md').write_text('src/a.py')
        (self.root / 'two.md').write_text('docs/b.md scripts/a.sh')
        code, out = self.run_cli('--files', 'one.md', '--files', 'two.md', '--ignore', 'src/*', 'docs/*', '--ignore', 'scripts/*', '--json')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)['ignored'], 3)

    def test_help(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as context:
            main(['--help'])
        self.assertEqual(context.exception.code, 0)
        self.assertIn('audit', out.getvalue())

    def test_version(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as context:
            main(['--version'])
        self.assertEqual(context.exception.code, 0)
        self.assertIn('0.1.0', out.getvalue())

    def test_realistic_json(self):
        (self.root / 'AGENTS.md').write_text('`python scripts/old.py`\ntests/old/\nNever use legacy')
        (self.root / 'app.py').write_text('import legacy')
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/new.py').write_text('')
        (self.root / 'checks').mkdir()
        code, out = self.run_cli('--json')
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['totals']['severity'], {'HIGH': 2, 'MEDIUM': 1})

    def test_human_json_totals(self):
        (self.root / 'AGENTS.md').write_text('src/a.py')
        _, human = self.run_cli()
        _, encoded = self.run_cli('--json')
        self.assertIn(json.dumps(json.loads(encoded)['totals'], sort_keys=True), human)
