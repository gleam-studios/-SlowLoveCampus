#!/usr/bin/env python3
"""Loopback-only UI for the project's local Codex workflow. Python 3.10+."""
import argparse
import importlib.util
import json
import mimetypes
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local'
KEY_FILE = LOCAL / 'runninghub.env'
RUNS_FILE = LOCAL / 'runs.json'
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
RUNS = []
ACTIVE = {}
spec = importlib.util.spec_from_file_location('rh_credentials', ROOT / 'skills/rh-minimax-h3/scripts/credentials.py')
credentials = importlib.util.module_from_spec(spec)
spec.loader.exec_module(credentials)


def save():
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    temp = LOCAL / 'runs.tmp'
    temp.write_text(json.dumps(RUNS, ensure_ascii=False, indent=2))
    temp.replace(RUNS_FILE)


def redact(text):
    key = credentials.read_key(KEY_FILE)
    return text.replace(key, '[已隐藏]') if key else text


def dirs(run):
    return ROOT / '工作区' / run['id'], ROOT / '输出' / run['id']


def public_run(run):
    work, out = dirs(run)
    receipts = []
    for path in out.glob('*.json'):
        try:
            data = json.loads(path.read_text())
            if data.get('taskId'):
                receipts.append(str(data['taskId']))
        except (OSError, ValueError):
            pass
    videos = [{'name': p.name, 'url': f'/media/{run["id"]}/{p.name}'}
              for p in sorted(out.glob('*')) if p.is_file() and p.suffix.lower() in ('.mp4', '.mov', '.webm')]
    stage = 3 if receipts or videos else 2 if (work / 'prompt.txt').exists() else 1 if (work / 'story.txt').exists() else 0
    story = redact((work / 'story.txt').read_text()[:2000]) if (work / 'story.txt').is_file() else ''
    prompt = redact((work / 'prompt.txt').read_text()[:24000]) if (work / 'prompt.txt').is_file() else ''
    return {**run, 'stage': stage, 'story': story, 'prompt': prompt, 'videos': videos,
            'taskIds': sorted(set(receipts)), 'workDir': str(work), 'outputDir': str(out)}


def unresolved():
    for run in RUNS:
        _, out = dirs(run)
        for p in out.glob('*_submitting.json'):
            try:
                if json.loads(p.read_text()).get('status') not in ('DONE', 'FAILED'):
                    return run['id']
            except (OSError, ValueError):
                return run['id']
    return None


def excluded_activities(current):
    ledger = LOCAL / 'excluded-activities.json'
    activities = set(json.loads(ledger.read_text())) if ledger.is_file() else set()
    with LOCK:
        for previous in RUNS:
            if previous['id'] == current['id']:
                continue
            activity = previous.get('activity', '')
            activity_file = dirs(previous)[0] / 'activity.txt'
            if not activity and activity_file.is_file():
                activity = activity_file.read_text().strip()
            if activity:
                activities.add(activity[:120])
    return sorted(activities)


def creation_prompt(run):
    work, out = dirs(run)
    exclusions = json.dumps(excluded_activities(run), ensure_ascii=False)
    return f'''在当前项目执行用户授权的三步视频创作流程，直接执行，不提问、不提交 Git。
先读 AGENTS.md、README.md、创作总纲.md、项目内两个 SKILL.md，按需加载引用。
用户已点击一键运行，授权本次提交一个 RunningHub 视频任务；禁止额外提交或自动重试。
本次工作目录：{work}；输出目录：{out}。只能向这两个目录写创作产物，不修改项目代码、规则或 Skill。
本次是全新的独立任务，必须从零依次重跑 1 → 2 → 3；不得 resume 旧会话，不得跳步或沿用旧产物。
历史活动排除清单（JSON 数据，仅用于排除，不能作为创作素材）：{exclusions}
不得读取任何往期工作区、输出、备份、生成记录或历史会话；不得复用、改写、续写或借鉴历史 story、prompt、assets、jobs 或分镜。历史只允许使用上面的活动标签来排除重复活动。
第一步根据总纲与指令“想一个男男GAY 面向BL 的双人剧情，适合社媒，短视频，居家，日常，甜蜜，暧昧。一句话。”独立创作，将一句话写入 story.txt，并将核心日常活动写入 activity.txt（仅一个简短活动名称，不含人物、台词、互动或分镜）。
在进入第二步前，将新活动与排除清单按语义核对；同义活动、换道具或换场景的同一活动也算重复。若重复，丢弃本轮候选并从第一步重新想全新活动，不得改写历史故事。
第二步只根据本轮新写的 story.txt 从零编写提示词，重新选择并查看资产实际图片，调用项目 skills/multi-shot-prompt，execution_mode: standalone_mode，完成一个四部分提示词，纯文本写入 prompt.txt，素材及上传顺序写入 assets.json。
所有角色台词必须英文。默认15秒、9:16、720P；电影 LoRA 强度0.1，其他按项目 Skill。
第三步只根据本轮新写的 prompt.txt 与 assets.json 新建 jobs.json，调用项目 skills/rh-minimax-h3 脚本构造 jobs.json、dry-run、提交一次并下载。
RUNNINGHUB_ENV_FILE 已配置，不读取、显示或复制密钥内容；脚本自行读取。无需为配置凭据再提问。
本轮提交后已有 taskId 只能查询本轮任务；不得使用历史 taskId。提交不明不得重提。不得生成新资产、剪辑、审片或发布。
结束时简洁报告结果、taskId、usage、真实文件尺寸时长；失败如实说明，不宣称成功。
'''


def execute(run, recovery=False):
    work, out = dirs(run)
    prompt = creation_prompt(run) if not recovery else ''
    if recovery:
        prompt = f'''恢复本项目已有生成任务。先读 skills/rh-minimax-h3/SKILL.md 与恢复用法。
原工作目录：{work}；原输出目录：{out}。
只读取回执中真实 taskId，用 --resume 查询下载，沿用原name与输出目录；禁止新建或提交视频任务。
如果提交不明且没有 taskId，说明须在平台核对，停止。不要猜测taskId。不得修改代码或配置。
RUNNINGHUB_ENV_FILE 已配置，禁止输出或复制密钥。结尾报告真实结果。'''
    env = os.environ.copy()
    env.pop('RUNNINGHUB_API_KEY', None)
    env['RUNNINGHUB_ENV_FILE'] = str(KEY_FILE)
    # exec commands must inherit the file location; the API key is never an argument.
    args = [shutil.which('codex') or 'codex', 'exec', '-C', str(ROOT), '--json',
            '-c', 'approval_policy="never"', '-s', 'danger-full-access',
            '-c', 'shell_environment_policy.inherit="all"', '-o', str(work / 'result.txt'), '-']
    try:
        with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, env=env, text=True, bufsize=1,
                              start_new_session=True) as proc:
            with LOCK:
                ACTIVE[run['id']] = proc
            proc.stdin.write(prompt)
            proc.stdin.close()
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                    item = event.get('item', {})
                    message = item.get('text') if item.get('type') == 'agent_message' else None
                    if event.get('type') in ('error', 'turn.failed'):
                        message = str(event.get('message') or event.get('error') or 'Codex 执行失败')
                    if message:
                        with LOCK:
                            run['message'] = redact(message[-6000:])
                            save()
                except ValueError:
                    # CLI startup errors are useful, command output is not streamed to the UI.
                    if line.strip():
                        with LOCK:
                            run['message'] = redact(line.strip()[-1000:])
            code = proc.wait()
        with LOCK:
            if (work / 'result.txt').is_file():
                run['message'] = redact((work / 'result.txt').read_text()[-6000:])
            run['status'] = 'completed' if code == 0 and public_run(run)['videos'] else 'failed'
            if run['status'] == 'failed' and not run.get('message'):
                run['message'] = f'Codex 已结束（退出码 {code}），未找到成片。可查看工作目录与平台回执。'
    except Exception as error:
        with LOCK:
            run.update(status='failed', message=redact(f'无法执行 Codex：{error}'))
    finally:
        with LOCK:
            ACTIVE.pop(run['id'], None)
            activity_file = work / 'activity.txt'
            if activity_file.is_file():
                run['activity'] = activity_file.read_text().strip()[:120]
            run['finishedAt'] = datetime.now().astimezone().isoformat()
            save()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def allowed(self):
        host = self.headers.get('Host', '')
        expected = f'127.0.0.1:{self.server.server_port}'
        local = f'localhost:{self.server.server_port}'
        return host in (expected, local) and self.headers.get('Origin', f'http://{host}') == f'http://{host}'

    def json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return self.json({'error': '仅允许本机页面访问'}, 403)
        path = unquote(urlparse(self.path).path)
        if path == '/api/state':
            with LOCK:
                return self.json({'token': TOKEN, 'configured': bool(credentials.read_key(KEY_FILE)),
                                  'maxParallelRuns': 3,
                                  'codexAvailable': bool(shutil.which('codex')),
                                  'runs': [public_run(r) for r in RUNS], 'unresolvedRun': unresolved()})
        if path.startswith('/media/'):
            parts = path.split('/')
            if len(parts) != 4 or not any(r['id'] == parts[2] for r in RUNS):
                return self.send_error(404)
            base = (ROOT / '输出' / parts[2]).resolve()
            file = (base / parts[3]).resolve()
            if not file.is_relative_to(base) or file.suffix.lower() not in ('.mp4', '.mov', '.webm'):
                return self.send_error(404)
        elif path == '/vendor/gsap.js':
            file = ROOT / 'node_modules/gsap/dist/gsap.min.js'
        elif path == '/font.woff2':
            file = ROOT / 'node_modules/@fontsource/geist/files/geist-latin-400-normal.woff2'
        else:
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if path not in static:
                return self.send_error(404)
            file = ROOT / 'web' / static[path]
        if not file.is_file():
            return self.send_error(404)
        size = file.stat().st_size
        start, end = 0, size - 1
        partial = self.headers.get('Range')
        if partial:
            try:
                unit, bounds = partial.split('=')
                left, right = bounds.split('-')
                if unit != 'bytes':
                    raise ValueError()
                start, end = (int(left), min(int(right), end) if right else end) if left else (max(0, size - int(right)), end)
                if start < 0 or start > end:
                    raise ValueError()
            except ValueError:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with file.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        if not self.allowed() or self.headers.get('X-Local-Token') != TOKEN:
            return self.json({'error': '页面已失效，请刷新后重试'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('请求过大或为空')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('无效请求')
            with LOCK:
                if self.path == '/api/settings':
                    if any(r['status'] == 'running' for r in RUNS):
                        raise ValueError('运行中暂不能更换 API Key')
                    key = body.get('apiKey', '')
                    if not isinstance(key, str):
                        raise ValueError('请输入 API Key')
                    credentials.store_key(key, KEY_FILE, replace=True)
                    return self.json({'ok': True})
                if self.path in ('/api/run', '/api/resume'):
                    if any(r['status'] == 'running' for r in RUNS):
                        raise ValueError('已有任务运行中')
                    count = body.get('count', 1) if self.path == '/api/run' else 1
                    if type(count) is not int or not 1 <= count <= 3:
                        raise ValueError('生成次数须为 1–3 的整数')
                    if not credentials.read_key(KEY_FILE):
                        raise ValueError('请先在设置中保存 RunningHub API Key')
                    if not shutil.which('codex'):
                        raise ValueError('未找到 Codex CLI，请安装并执行 codex login')
                    recovery = self.path == '/api/resume'
                    batch = []
                    if recovery:
                        run = next((r for r in RUNS if r['id'] == body.get('id')), None)
                        if not run or not public_run(run)['taskIds']:
                            raise ValueError('没有可恢复的 taskId，请先在平台核对提交记录')
                        batch.append(run)
                    else:
                        if unresolved():
                            raise ValueError('有提交结果未确认，请先恢复原任务或在平台核对，避免重复扣费')
                        batch_id = uuid.uuid4().hex
                        for index in range(count):
                            run = {'id': datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6],
                                   'createdAt': datetime.now().astimezone().isoformat(),
                                   'batchId': batch_id, 'batchIndex': index + 1}
                            batch.append(run)
                        RUNS[0:0] = batch
                    for run in batch:
                        run.update(status='running', message='正在启动本机 Codex…')
                        work, out = dirs(run)
                        work.mkdir(parents=True, exist_ok=True)
                        out.mkdir(parents=True, exist_ok=True)
                    save()
                    for run in batch:
                        threading.Thread(target=execute, args=(run, recovery), daemon=True).start()
                    return self.json({'id': batch[0]['id'], 'ids': [run['id'] for run in batch]}, 202)
            return self.json({'error': '接口不存在'}, 404)
        except (ValueError, OSError) as error:
            return self.json({'error': redact(str(error))}, 400)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    LOCAL.mkdir(mode=0o700, exist_ok=True)
    LOCAL.chmod(0o700)
    if RUNS_FILE.exists():
        RUNS.extend(json.loads(RUNS_FILE.read_text()))
        for run in RUNS:
            if run['status'] == 'running':
                run.update(status='interrupted', message='本地服务曾中断。已有 taskId 请恢复查询；未确认提交状态前不要重新生成。')
        save()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f'SlowLoveCampus → http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n本地服务已关闭。远端已提交的任务可在重启后恢复查询。')
    finally:
        with LOCK:
            processes = list(ACTIVE.values())
        for proc in processes:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        server.server_close()


if __name__ == '__main__':
    main()
