import { escHtml } from '/js/utils.js';
import { setCurrentLoopId } from '/js/state.js';

export async function initVersionBadge() {
  try {
    const resp = await fetch('/api/health');
    if (!resp.ok) return;
    const data = await resp.json();
    const ver = data.monitor_version || 'unknown';
    document.getElementById('version-badge').textContent = `loop-monitor v${ver}`;
  } catch (_) {}
}

export async function initLoopSelector(onLoopChange) {
  try {
    const resp = await fetch('/api/loops');
    if (!resp.ok) return;
    const loops = await resp.json();
    const realLoops = loops.filter(l => l.loop_id !== '(unknown)');
    if (realLoops.length <= 1) return;
    const loopSelector = document.getElementById('loop-selector');
    const loopSelectorWrap = document.getElementById('loop-selector-wrap');
    loopSelector.innerHTML = '<option value="">All loops</option>' +
      realLoops.map(l => `<option value="${escHtml(l.loop_id)}">${escHtml(l.loop_id)}</option>`).join('');
    loopSelectorWrap.classList.add('visible');
    loopSelector.addEventListener('change', () => {
      setCurrentLoopId(loopSelector.value);
      onLoopChange();
    });
  } catch (_) {}
}
