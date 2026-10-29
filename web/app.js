const $ = (id) => document.getElementById(id);
let state, selected, busy = false;
const names = {running: '运行中', completed: '已完成', failed: '未完成', interrupted: '服务曾中断'};
const emptyPreview = $('video-frame').innerHTML;
let shownVideo = '';
let waterfallSignature = '';
function renderWaterfall() {
  const videos = state.runs.flatMap(run => run.videos);
  $('records-empty').hidden = videos.length > 0;
  const signature = JSON.stringify(videos);
  if (signature === waterfallSignature) return;
  waterfallSignature = signature;
  const tiles = videos.map(video => {
    const tile = document.createElement('div'); tile.className = 'video-tile';
    const player = document.createElement('video'); player.src = video.url;
    player.muted = true; player.playsInline = true; player.preload = 'metadata';
    const open = document.createElement('button'); open.className = 'tile-open';
    open.setAttribute('aria-label', '播放视频');
    const play = document.createElement('span'); play.className = 'tile-play'; play.textContent = '▷';
    open.append(player, play);
    open.onclick = () => {
      $('media-player').src = video.url;
      $('media-download').href = video.url; $('media-download').download = video.name;
      $('media-viewer').showModal(); $('media-player').play().catch(() => {});
    };
    const download = document.createElement('a'); download.href = video.url; download.download = video.name;
    download.className = 'tile-download'; download.textContent = '↓';
    download.setAttribute('aria-label', '下载成片'); download.title = '下载成片';
    tile.append(open, download); return tile;
  });
  $('record-waterfall').replaceChildren(...tiles);
}
function route() {
  const records = location.hash === '#records' || location.hash.startsWith('#records/');
  $('studio-page').hidden = records;
  $('records-page').hidden = !records;
  for (const [id, active] of [['nav-studio', !records], ['nav-records', records]]) {
    if (active) $(id).setAttribute('aria-current', 'page');
    else $(id).removeAttribute('aria-current');
  }
  document.querySelectorAll('video').forEach(video => video.pause());
  if (location.hash.startsWith('#records/')) selected = decodeURIComponent(location.hash.slice(9));
  document.title = `SlowLoveCampus · ${records ? '生成记录' : '创作台'}`;
  if (state) render();
}
function downloadSelected() {
  const run = state?.runs.find(r => r.id === selected) || state?.runs[0];
  const video = run?.videos[0];
  if (!video) return;
  const link = document.createElement('a'); link.href = video.url; link.download = video.name;
  document.body.append(link); link.click(); link.remove();
}
function notify(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(notify.timer); notify.timer = setTimeout(() => $('toast').hidden = true, 6000); }
async function post(path, data = {}) {
  const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Local-Token': state.token}, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败');
  return result;
}
function render() {
  const activeCount = state.runs.filter(r => r.status === 'running').length;
  const running = activeCount > 0;
  const count = Number($('run-count').value);
  const compatible = state.maxParallelRuns === 3;
  $('run-count').disabled = busy || running;
  $('connection').textContent = state.codexAvailable ? '本地 Codex 已就绪' : '未找到 Codex CLI';
  $('run-button').disabled = busy || running || !compatible || !state.configured || !state.codexAvailable || !!state.unresolvedRun;
  $('run-button').firstElementChild.textContent = running ? `${activeCount} 个任务运行中…` : count > 1 ? `一键运行 · ${count} 次` : '一键运行';
  $('run-hint').textContent = !compatible ? '当前后端仍是旧版本，请在现有任务完成后重启服务，再开始生成。' : running ? `${activeCount} 个任务运行中，可点击下方任务切换进度和预览。` : !state.configured ? '先在设置中保存 RunningHub API Key。' : state.unresolvedRun ? '有提交状态未确认，请先恢复原任务。' : !state.codexAvailable ? '先在终端安装 Codex CLI 并登录。' : `点击后将${count > 1 ? '并行' : ''}提交 ${count} 次视频生成，费用由 RunningHub 账户扣除。`;
  $('key-hint').textContent = state.configured ? '已保存。输入新 Key 可替换；保存不代表已联网验证。' : '仅保存在本机，不会在页面中回显。';
  renderWaterfall();
  const run = state.runs.find(r => r.id === selected) || state.runs[0];
  if (!run) return;
  const batch = run.batchId ? state.runs.filter(r => r.batchId === run.batchId) : [run];
  $('batch-tasks').hidden = batch.length < 2;
  const signature = JSON.stringify(batch.map(r => [r.id, r.status, r.id === run.id]));
  if ($('batch-tasks').dataset.signature !== signature) {
    $('batch-tasks').dataset.signature = signature;
    $('batch-tasks').replaceChildren(...batch.map((task, index) => {
      const button = document.createElement('button');
      button.className = 'quiet'; button.textContent = `任务 ${index + 1} · ${names[task.status]}`;
      button.setAttribute('aria-pressed', String(task.id === run.id));
      button.onclick = () => { selected = task.id; render(); }; return button;
    }));
  }
  $('result-status').textContent = names[run.status];
  $('resume-button').hidden = !run.taskIds.length || run.status === 'completed' || running;
  $('resume-button').dataset.id = run.id;
  document.querySelectorAll('.steps li').forEach((li, i) => {
    const done = run.status === 'completed' || (i < 2 && run.stage > i);
    const active = run.status === 'running' && i === Math.min(run.stage, 2);
    li.className = done ? 'done' : active ? 'active' : '';
    li.querySelector('.step-status').textContent = done ? '完成' : active ? '进行中' : run.status === 'running' ? '等待' : '—';
  });
  const video = run.videos[0];
  const url = video ? video.url : '';
  $('preview-download').disabled = !video;
  if (url !== shownVideo) {
    shownVideo = url;
    if (video) { const el = document.createElement('video'); el.src = url; el.controls = true; el.playsInline = true; el.preload = 'metadata'; $('video-frame').replaceChildren(el); }
    else $('video-frame').innerHTML = emptyPreview;
  }
  $('result-links').replaceChildren();
  if (run.taskIds.length) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = 'taskId: ' + run.taskIds.join(', '); $('result-links').append(p); }
}
async function refresh() {
  const response = await fetch('/api/state');
  if (!response.ok) throw new Error('本地服务连接失败');
  state = await response.json();
  if (!selected) selected = state.runs[0]?.id;
  render();
}
$('settings-button').onclick = () => $('settings').showModal();
$('close-settings').onclick = () => $('settings').close();
$('settings-form').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { await post('/api/settings', {apiKey: $('api-key').value}); $('api-key').value = ''; $('settings-feedback').textContent = '已保存到本机'; await refresh(); $('settings').close(); notify('API Key 已保存'); }
  catch (e) { $('settings-feedback').textContent = e.message; }
  finally { button.disabled = false; }
};
$('run-button').onclick = async () => {
  if (busy) return; busy = true; render();
  try {
    if (state.maxParallelRuns !== 3) throw new Error('后端尚未加载并行版本，请先重启服务');
    const count = Number($('run-count').value);
    const result = await post('/api/run', {count}); selected = result.id; await refresh();
    if (!Array.isArray(result.ids) || result.ids.length !== count) notify('实际创建的任务数与请求不符，请勿重复点击，先检查服务版本。');
  }
  catch (e) { notify(e.message); }
  finally { busy = false; render(); }
};
$('resume-button').onclick = async () => {
  const button = $('resume-button'); button.disabled = true;
  try { await post('/api/resume', {id: button.dataset.id}); await refresh(); }
  catch (e) { notify(e.message); }
  finally { button.disabled = false; }
};
async function poll() { try { await refresh(); } catch (_) { $('connection').textContent = '本地服务已断开'; $('run-button').disabled = true; $('run-hint').textContent = '请启动本地服务，连接恢复后将自动更新。'; } finally { setTimeout(poll, 2500); } }
$('preview-download').onclick = downloadSelected;
$('run-count').onchange = () => { if (state) render(); };
$('close-media').onclick = () => $('media-viewer').close();
$('media-viewer').addEventListener('close', () => { $('media-player').pause(); $('media-player').removeAttribute('src'); $('media-player').load(); });
$('media-viewer').addEventListener('click', event => { if (event.target === $('media-viewer')) $('media-viewer').close(); });
window.addEventListener('hashchange', route);
route();
poll();
if (window.gsap) gsap.matchMedia().add('(prefers-reduced-motion: no-preference)', () => {
  gsap.from('.title-row, .workspace > .panel, .activity', {y: 10, opacity: 0, duration: .45, stagger: .07, ease: 'power2.out'});
});
