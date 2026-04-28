import { escHtml, modelShort } from '/js/utils.js';
import { setProjectScores } from '/js/state.js';

export function initBoardTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.board-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(btn.dataset.tab).classList.add('active');
    });
  });
}

export function renderBoard(data) {
  const byRole = {};
  for (const row of data) {
    const k = (row.role || '').toLowerCase();
    if (!byRole[k]) byRole[k] = { role: row.role, pts: 0, verdicts: 0 };
    byRole[k].pts += row.total_points;
    byRole[k].verdicts += row.verdict_count;
  }
  const roleRows = Object.values(byRole).sort((a, b) => b.pts - a.pts);

  const scores = {};
  for (const row of data) {
    const p = row.project || '';
    scores[p] = (scores[p] || 0) + row.total_points;
  }
  setProjectScores(scores);

  const roleTbody = document.getElementById('board-role-body');
  roleTbody.innerHTML = roleRows.length ? roleRows.map((r, i) => `
    <tr>
      <td class="rank">${i + 1}</td>
      <td>${escHtml((r.role || '').charAt(0).toUpperCase() + (r.role || '').slice(1))}</td>
      <td style="color:var(--muted)">${r.verdicts}</td>
      <td class="pts">${r.pts}</td>
    </tr>
  `).join('') : '<tr><td colspan="4" class="empty-state">No data yet</td></tr>';

  const byModel = {};
  for (const row of data) {
    const k = row.model || '(unknown)';
    if (!byModel[k]) byModel[k] = { model: k, pts: 0, verdicts: 0 };
    byModel[k].pts += row.total_points;
    byModel[k].verdicts += row.verdict_count;
  }
  const modelRows = Object.values(byModel).sort((a, b) => b.pts - a.pts);
  const modelTbody = document.getElementById('board-model-body');
  modelTbody.innerHTML = modelRows.length ? modelRows.map((r, i) => `
    <tr>
      <td class="rank">${i + 1}</td>
      <td style="font-size:0.72rem">${escHtml(modelShort(r.model))}</td>
      <td style="color:var(--muted)">${r.verdicts}</td>
      <td class="pts">${r.pts}</td>
    </tr>
  `).join('') : '<tr><td colspan="4" class="empty-state">No data yet</td></tr>';
}
