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
                         patch.object(server, 'RUNS', []), patch.dict(server.ACTIVE, process=None)]
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

    def test_fake_codex_end_to_end_and_video_range(self):
        self.request('/api/settings', {'apiKey': 'fake-key'})
        fake = self.root / 'codex'
        fake.write_text('''#!/usr/bin/env python3
import json,sys,re,time
from pathlib import Path
prompt=sys.stdin.read()
match=re.search(r"本次工作目录：(.*?)；输出目录：(.*?)。",prompt)
work,out=map(Path,match.groups())
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


if __name__ == '__main__':
    unittest.main()
