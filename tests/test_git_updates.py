import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_app as updater


class GitUpdates(unittest.TestCase):
    def test_clone_update_fallback_and_local_changes(self):
        # Retain the isolated test directory for inspection; no user files removed.
        base = Path(tempfile.mkdtemp(prefix='headliner-update-test-'))
        source = base / 'source'
        source.mkdir()
        updater.git(source, 'init', '-b', 'main')
        updater.git(source, 'config', 'user.email', 'test@example.invalid')
        updater.git(source, 'config', 'user.name', 'Update test')
        for name in ['app.py', 'worker.py', 'requirements.txt', 'update_app.py']:
            (source / name).write_text('original')
        (source / '.gitignore').write_text('models/\nlocal_settings.json\n')
        updater.git(source, 'add', '.')
        updater.git(source, 'commit', '-m', 'initial')
        installed = base / 'installed'
        installed.mkdir()
        (installed / 'models').mkdir()
        (installed / 'models' / 'keep').write_text('model')
        (installed / 'local_settings.json').write_text('private')
        mirrors = [('Unavailable', str(base / 'missing')), ('Fallback', str(source))]
        with patch.object(updater, 'MIRRORS', mirrors):
            updater.update(installed)
            self.assertIn('up to date', updater.check_update(installed))
            (source / 'app.py').write_text('new')
            updater.git(source, 'commit', '-am', 'new release')
            self.assertIn('available', updater.check_update(installed))
            updater.update(installed)
            self.assertEqual((installed / 'app.py').read_text(), 'new')
            self.assertEqual((installed / 'models' / 'keep').read_text(), 'model')
            self.assertEqual((installed / 'local_settings.json').read_text(), 'private')
            (installed / 'app.py').write_text('my edits')
            with self.assertRaisesRegex(RuntimeError, 'Local source changes'):
                updater.update(installed)
            self.assertEqual((installed / 'app.py').read_text(), 'my edits')

if __name__ == '__main__':
    unittest.main()
