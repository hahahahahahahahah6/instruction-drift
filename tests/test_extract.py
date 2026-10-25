import unittest
from instruction_drift.extract import extract, path_token


class ExtractTests(unittest.TestCase):
    def test_bare_path(self):
        self.assertEqual(extract('See src/app.py')[0].claim, 'src/app.py')

    def test_backtick_path(self):
        self.assertEqual(extract('See `docs/help.md`.')[0].kind, 'referenced-file')

    def test_directory(self):
        self.assertEqual(path_token('tests/old/'), 'tests/old/')

    def test_url(self):
        self.assertIsNone(path_token('https://example.org/src/a.py'))

    def test_http_url(self):
        self.assertIsNone(path_token('http://example.org/a.py'))

    def test_glob(self):
        self.assertIsNone(path_token('src/*.py'))

    def test_unknown_extension(self):
        self.assertIsNone(path_token('other/a.xyz'))

    def test_all_extensions(self):
        for ext in ('py', 'js', 'ts', 'md', 'json', 'yaml', 'yml', 'toml', 'sh', 'go', 'rs', 'txt'):
            self.assertEqual(path_token('other/a.' + ext), 'other/a.' + ext)

    def test_directory_roots(self):
        for root in ('src', 'tests', 'docs', 'examples', 'scripts', 'bin'):
            self.assertEqual(path_token(root + '/sub/'), root + '/sub/')

    def test_command(self):
        self.assertEqual(extract('Run `python scripts/run.py`')[0].kind, 'script-in-command')

    def test_dot_script(self):
        item = extract('Run `./scripts/run.sh`')[0]
        self.assertEqual(item.claim, './scripts/run.sh')
        self.assertEqual(item.kind, 'script-in-command')

    def test_make(self):
        self.assertEqual(extract('Run `make check`')[0].claim, 'make check')

    def test_prohibition_forms(self):
        for prefix in ('Do not use', 'never use', 'must not use', 'avoid using'):
            self.assertEqual(extract(prefix + ' `legacy`.')[0].claim, 'legacy')

    def test_line_number(self):
        self.assertEqual(extract('\n\nsrc/a.py')[0].line, 3)

    def test_dedup(self):
        self.assertEqual(len(extract('src/a.py src/a.py')), 1)

    def test_no_plain_filename(self):
        self.assertEqual(extract('Read README.md'), [])
