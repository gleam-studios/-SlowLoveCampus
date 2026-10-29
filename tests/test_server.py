"""Local integration tests; fake Codex never contacts RunningHub or OpenAI."""
import http.client
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import server


class LocalAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.local = self.root / '.local'
        self.local.mkdir()
        self.patchers = [patch.object(server, 'ROOT', self.root), patch.object(server, 'LOCAL', self.local),
                         patch.object(server, 'KEY_FILE', self.local / 'runninghub.env'),
                         patch.object(server, 'RUNS_FILE', self.local / 'runs.json'),
                         patch.object(server, 'RUNS', []), patch.object(server, 'ACTIVE', {})]
        for p in self.patchers:
            p.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.http.server_port

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        for p in reversed(self.patchers):
            p.stop()
        self.temp.cleanup()

    def request(self, path, data=None, headers=None):
        client = http.client.HTTPConnection('127.0.0.1', self.port)
        all_headers = {'X-Local-Token': server.TOKEN, 'Content-Type': 'application/json'}
        all_headers.update(headers or {})
        client.request('GET' if data is None else 'POST', path,
                       None if data is None else json.dumps(data), all_headers)
        response = client.getresponse()
        status, body = response.status, response.read()
        client.close()
        return status, body

    def test_key_storage_and_access_boundaries(self):
        key = 'fake-runninghub-secret-for-tests'
        self.assertEqual(self.request('/api/settings', {'apiKey': key})[0], 200)
        self.assertEqual(stat.S_IMODE(server.KEY_FILE.stat().st_mode), 0o600)
        state = self.request('/api/state')[1]
        self.assertNotIn(key.encode(), state)
        self.assertTrue(json.loads(state)['configured'])
        self.assertEqual(json.loads(state)['maxParallelRuns'], 3)
        self.assertEqual(self.request('/.local/runninghub.env')[0], 404)
        self.assertEqual(self.request('/.env')[0], 404)
        self.assertEqual(self.request('/api/state', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/settings', {'apiKey': 'bad'}, {'Origin': 'https://evil.example'})[0], 403)
        self.assertEqual(self.request('/api/settings', {'apiKey': 'bad'}, {'X-Local-Token': 'wrong'})[0], 403)

    def test_missing_key_duplicate_and_uncertain_submission(self):
        self.assertEqual(self.request('/api/run', {})[0], 400)
        self.request('/api/settings', {'apiKey': 'fake-key'})
        run = {'id': 'existing', 'status': 'running'}
        server.RUNS.append(run)
        self.assertEqual(self.request('/api/run', {})[0], 400)
        self.assertEqual(self.request('/api/settings', {'apiKey': 'new-key'})[0], 400)
        run['status'] = 'interrupted'
        _, out = server.dirs(run)
        out.mkdir(parents=True)
        (out / 'video_submitting.json').write_text(json.dumps({'status': 'SUBMIT_UNKNOWN'}))
        self.assertEqual(server.unresolved(), 'existing')
        with patch.object(server.shutil, 'which', return_value='/fake/codex'):
            self.assertEqual(self.request('/api/run', {})[0], 400)
            self.assertEqual(self.request('/api/resume', {'id': 'existing'})[0], 400)

    def test_batch_count_validation(self):
        self.request('/api/settings', {'apiKey': 'fake-key'})
        for count in (0, 4, -1, True, 1.5, '3', None):
            with self.subTest(count=count):
                self.assertEqual(self.request('/api/run', {'count': count})[0], 400)
        self.assertEqual(server.RUNS, [])

    def test_three_tasks_start_concurrently_and_fail_independently(self):
        self.request('/api/settings', {'apiKey': 'fake-key'})
        entered = []
        release = threading.Event()
        all_started = threading.Event()
        all_finished = threading.Event()
        finished = []

        def fake_execute(run, recovery=False):
            with server.LOCK:
                entered.append(run['id'])
                if len(entered) == 3:
                    all_started.set()
            release.wait(5)
            with server.LOCK:
                run['status'] = 'failed' if run['batchIndex'] == 2 else 'completed'
                finished.append(run['id'])
                server.save()
                if len(finished) == 3:
                    all_finished.set()

        with patch.object(server, 'execute', side_effect=fake_execute), patch.object(server.shutil, 'which', return_value='/fake/codex'):
            try:
                status, data = self.request('/api/run', {'count': 3})
                self.assertEqual(status, 202)
                ids = json.loads(data)['ids']
                self.assertEqual(len(set(ids)), 3)
                self.assertTrue(all_started.wait(2), 'Three workers must enter before any finishes')
                self.assertEqual(len(server.RUNS), 3)
                self.assertEqual(len({r['batchId'] for r in server.RUNS}), 1)
                for run in server.RUNS:
                    self.assertTrue(server.dirs(run)[0].is_dir())
                    self.assertTrue(server.dirs(run)[1].is_dir())
                self.assertEqual(self.request('/api/run', {'count': 1})[0], 400)
            finally:
                release.set()
                self.assertTrue(all_finished.wait(3))
        self.assertEqual([r['status'] for r in server.RUNS], ['completed', 'failed', 'completed'])

    def test_fresh_prompt_uses_only_activity_exclusions(self):
        old = {'id': 'old', 'status': 'completed'}
        current = {'id': 'new', 'status': 'running'}
        server.RUNS.extend([current, old])
        old_work, _ = server.dirs(old)
        old_work.mkdir(parents=True)
        (old_work / 'activity.txt').write_text('叠衣服')
        (old_work / 'story.txt').write_text('SECRET_OLD_STORY')
        (old_work / 'prompt.txt').write_text('SECRET_OLD_PROMPT')
        prompt = server.creation_prompt(current)
        self.assertIn('叠衣服', prompt)
        self.assertNotIn('SECRET_OLD', prompt)
        self.assertIn('不得读取', prompt)
        self.assertIn('1 → 2 → 3', prompt)
        self.assertIn('activity.txt', prompt)
        self.assertNotIn(str(old_work), prompt)

    def test_recorded_activity_survives_missing_work_files(self):
        (self.local / 'excluded-activities.json').write_text('["叠衣服"]')
        server.RUNS.append({'id': 'legacy', 'status': 'failed', 'activity': '做早餐'})
        self.assertIn('叠衣服', server.creation_prompt({'id': 'new'}))
        self.assertIn('做早餐', server.creation_prompt({'id': 'new'}))

    def test_fake_codex_end_to_end_and_video_range(self):
        self.request('/api/settings', {'apiKey': 'fake-key'})
        fake = self.root / 'codex'
        fake.write_text('''#!/usr/bin/env python3
import json,sys,re,time
from pathlib import Path
prompt=sys.stdin.read()
match=re.search(r"本次工作目录：(.*?)；输出目录：(.*?)。",prompt)
work,out=map(Path,match.groups())
(work/'activity.txt').write_text('做早餐')
(work/'request.txt').write_text(prompt)
(work/'args.json').write_text(json.dumps(sys.argv))
(work/'story.txt').write_text('厨房里，两人争抢最后一口早餐。')
(work/'prompt.txt').write_text('视频梗概\\n影片质感\\n素材锁定\\n分镜：Hello, love.')
(out/'video_123.json').write_text(json.dumps({'taskId':'123','status':'SUCCESS'}))
(out/'video.mp4').write_bytes(b'0123456789')
Path(sys.argv[sys.argv.index('-o')+1]).write_text('模拟结果，未提交真实视频。')
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'模拟任务已完成'}}),flush=True)
time.sleep(.1)
''')
        fake.chmod(0o700)
        with patch.object(server.shutil, 'which', return_value=str(fake)):
            status, data = self.request('/api/run', {})
            self.assertEqual(status, 202)
            run_id = json.loads(data)['id']
            deadline = time.monotonic() + 5
            while server.RUNS[0]['status'] == 'running' and time.monotonic() < deadline:
                time.sleep(.05)
        run = json.loads(self.request('/api/state')[1])['runs'][0]
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(run['stage'], 3)
        self.assertEqual(run['taskIds'], ['123'])
        self.assertIn('Hello, love.', run['prompt'])
        status, content = self.request(f'/media/{run_id}/video.mp4', headers={'Range': 'bytes=2-5'})
        self.assertEqual((status, content), (206, b'2345'))
        self.assertEqual(self.request(f'/media/{run_id}/%2e%2e%2fsecret.mp4')[0], 404)
        self.assertEqual(self.request(f'/media/{run_id}/video.mp4', headers={'Range': 'bytes=100-'})[0], 416)
        self.assertTrue(server.RUNS_FILE.is_file())
        self.assertEqual(run['activity'], '做早餐')
        with patch.object(server.shutil, 'which', return_value=str(fake)):
            status, data = self.request('/api/run', {})
            self.assertEqual(status, 202)
            second_id = json.loads(data)['id']
            self.assertNotEqual(second_id, run_id)
            deadline = time.monotonic() + 5
            while server.RUNS[0]['status'] == 'running' and time.monotonic() < deadline:
                time.sleep(.05)
        work, _ = server.dirs(server.RUNS[0])
        second_prompt = (work / 'request.txt').read_text()
        self.assertIn('做早餐', second_prompt)
        self.assertNotIn('厨房里，两人争抢最后一口早餐', second_prompt)
        self.assertNotIn('Hello, love.', second_prompt)
        self.assertNotIn('resume', json.loads((work / 'args.json').read_text()))
        self.assertEqual(server.RUNS[0]['status'], 'completed')



if __name__ == '__main__':
    unittest.main()
