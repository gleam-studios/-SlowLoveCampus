"""No model calls, real credentials or remote video submissions."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='slowlove portable ')
        self.workspace = Path(self.temp.name) / '中文 工作目录'

    def tearDown(self):
        self.temp.cleanup()

    def run_helper(self, *args):
        return subprocess.run([sys.executable, str(ROOT / 'scripts/workspace.py'),
                               '--workspace', str(self.workspace), *args],
                              cwd=self.temp.name, capture_output=True, text=True, timeout=20)

    def test_isolated_instances_and_label_only_history(self):
        first = self.run_helper('prepare', '--count', '3', '--agent', 'test-agent', '--model', 'test-model')
        self.assertEqual(first.returncode, 0, first.stderr)
        data = json.loads(first.stdout)
        self.assertEqual(data['agents_started'], 0)
        self.assertEqual(len({r['id'] for r in data['runs']}), 3)
        one, two, _ = data['runs']
        (Path(one['work_dir']) / 'story.txt').write_text('PRIVATE_STORY_NEVER_READ')
        self.assertEqual(self.run_helper('activity', '--run-id', one['id'], '--name', '做早餐').returncode, 0)
        ctx = self.run_helper('context', '--run-id', two['id'])
        self.assertIn('做早餐', ctx.stdout)
        self.assertNotIn('PRIVATE_STORY', ctx.stdout)
        self.assertIn('做早餐', self.run_helper('prepare').stdout)
        self.assertEqual(self.run_helper('context', '--run-id', '../outside').returncode, 1)
        self.assertNotEqual(self.run_helper('prepare', '--count', '4').returncode, 0)

    def test_parallel_activity_reservation(self):
        data = json.loads(self.run_helper('prepare', '--count', '2').stdout)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda run: self.run_helper('activity', '--run-id', run['id'], '--name', '洗碗'), data['runs']))
        self.assertEqual(sorted(p.returncode for p in results), [0, 1])
        self.assertTrue(any('E_ACTIVITY_ALREADY_USED' in p.stderr for p in results))
        self.assertFalse((self.workspace / '.activity.lock').exists())

    def test_prompt_validation_from_relocated_package(self):
        run = json.loads(self.run_helper('prepare').stdout)['runs'][0]
        out = Path(run['output_dir'])
        ms = ROOT / 'skills/multi-shot-prompt'
        fixture = (ms / 'examples/product_ad_10s.md').read_text()
        prompt = out / 'prompt.txt'
        prompt.write_text(fixture[fixture.index('# 视频梗概'):])
        command = [sys.executable, str(ms / 'scripts/validate_skill_contract.py'),
                   '--prompt', str(prompt), '--prompt-only']
        checked = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        prompt.write_text('invalid incomplete prompt')
        rejected = subprocess.run(command, capture_output=True, text=True, timeout=20)
        self.assertNotEqual(rejected.returncode, 0)
        assets = json.loads((ROOT / 'ASSETS.json').read_text())
        self.assertEqual(len(assets), 11)
        self.assertTrue(all((ROOT / a['path']).is_file() for a in assets))


if __name__ == '__main__':
    unittest.main()
