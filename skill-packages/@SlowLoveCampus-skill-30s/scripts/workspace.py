#!/usr/bin/env python3
"""Offline workspace and activity-label helpers; no model or video submission."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

BUNDLE = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def instance(workspace, run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', run_id):
        raise ValueError('无效 run-id')
    directory = workspace / run_id
    if not (directory / 'run.json').is_file():
        raise ValueError('运行实例不存在')
    return directory


def labels(workspace, current=None):
    result = set()
    for path in sorted(workspace.glob('*/run.json')):
        if path.parent.name == current:
            continue
        activity = read_json(path).get('activity', '')
        if activity:
            result.add(activity)
    return sorted(result)


def context(workspace, run_id):
    directory = instance(workspace, run_id)
    return {'id': run_id, 'run_dir': str(directory), 'work_dir': str(directory / 'work'),
            'output_dir': str(directory / 'output'),
            'excluded_activities': labels(workspace, run_id)}


@contextmanager
def activity_lock(workspace):
    path = workspace / '.activity.lock'
    for attempt in range(100):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError:
            if attempt == 99:
                raise ValueError('活动登记正被占用；若进程已退出，先核对并清理 .activity.lock')
            time.sleep(.05)
    try:
        yield
    finally:
        path.unlink()


def normalize(value):
    return re.sub(r'\s+', '', value).casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=BUNDLE / 'runs')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--count', type=int, choices=(1, 2, 3), default=1)
    prepare.add_argument('--agent', default='unknown')
    prepare.add_argument('--model', default='unknown')
    ctx = commands.add_parser('context')
    ctx.add_argument('--run-id', required=True)
    activity = commands.add_parser('activity')
    activity.add_argument('--run-id', required=True)
    activity.add_argument('--name', required=True)
    args = parser.parse_args()
    workspace = args.workspace.expanduser().resolve()

    try:
        if args.command == 'check':
            assets = read_json(BUNDLE / 'ASSETS.json')
            absent = [item['path'] for item in assets if not (BUNDLE / item['path']).is_file()]
            required = ['references/创作总纲.md', 'skills/multi-shot-prompt/SKILL.md',
                        'skills/multi-shot-prompt/scripts/validate_skill_contract.py']
            absent.extend(p for p in required if not (BUNDLE / p).is_file())
            ready = sys.version_info >= (3, 10) and not absent
            result = {'bundle': str(BUNDLE), 'python': sys.version.split()[0],
                      'third_party_dependencies': [], 'missing_files': absent,
                      'asset_count': len(assets),
                      'offline_dependencies_ready': ready, 'network_tested': False,
                      'output_type': 'video_prompt'}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if ready else 1
        if args.command == 'prepare':
            workspace.mkdir(parents=True, exist_ok=True)
            batch = uuid.uuid4().hex
            runs = []
            for index in range(args.count):
                run_id = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:12]
                directory = workspace / run_id
                directory.mkdir()
                (directory / 'work').mkdir()
                (directory / 'output').mkdir()
                write_json(directory / 'run.json', {'id': run_id, 'batch_id': batch,
                           'batch_index': index + 1, 'agent': args.agent, 'model': args.model,
                           'created_at': datetime.now().astimezone().isoformat(), 'activity': None})
                runs.append(context(workspace, run_id))
            result = {'batch_id': batch, 'runs': runs, 'agents_started': 0}
        elif args.command == 'context':
            result = context(workspace, args.run_id)
        else:
            name = args.name.strip()
            if not name or len(name) > 60 or '\n' in name or '\r' in name:
                raise ValueError('活动标签须为 1–60 字的单行简短活动名称')
            directory = instance(workspace, args.run_id)
            with activity_lock(workspace):
                existing = labels(workspace, args.run_id)
                if any(normalize(value) == normalize(name) for value in existing):
                    raise ValueError('E_ACTIVITY_ALREADY_USED：活动已使用，请重新构思')
                data = read_json(directory / 'run.json')
                if data.get('activity') and data['activity'] != name:
                    raise ValueError('活动已登记，不得以改名绕过占用；需要新创意时创建新实例')
                data['activity'] = name
                write_json(directory / 'run.json', data)
            result = context(workspace, args.run_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
