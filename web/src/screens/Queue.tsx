import { useMemo, useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchActionQueue } from '../lib/api';
import type { QueueItem } from '../lib/types';
import FailureInspector from '../components/FailureInspector';
import Drawer from '../components/Drawer';
import { useHashRoute } from '../router';

export const PAGE_SIZE = 20;

/** Parse `page` from a hash string (e.g. `#queue?page=2`). Exported for testing. */
export function parsePageFromHash(hash: string): number {
  const qIdx = hash.indexOf('?');
  if (qIdx === -1) return 1;
  const params = new URLSearchParams(hash.slice(qIdx + 1));
  const p = parseInt(params.get('page') ?? '1', 10);
  return Number.isFinite(p) && p >= 1 ? p : 1;
}

/** Build an updated hash string with `page` set. Exported for testing. */
export function buildHashWithPage(hash: string, page: number): string {
  const qIdx = hash.indexOf('?');
  const route = qIdx === -1 ? hash : hash.slice(0, qIdx);
  const params = new URLSearchParams(qIdx === -1 ? '' : hash.slice(qIdx + 1));
  if (page <= 1) {
    params.delete('page');
  } else {
    params.set('page', String(page));
  }
  const qs = params.toString();
  return qs ? `${route}?${qs}` : route;
}

/** Read `page` from the URL hash. Hash format: `#queue?page=2` or `#queue`. */
export function readPageFromHash(): number {
  return parsePageFromHash(window.location.hash);
}

/** Write `page` into the URL hash, preserving the route segment. */
export function writePageToHash(page: number): void {
  window.location.hash = buildHashWithPage(window.location.hash, page);
}

/** Slice `items` to the requested page. Returns `{ pageItems, totalPages }`. */
export function paginateItems<T>(items: T[], page: number, pageSize: number = PAGE_SIZE) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const clampedPage = Math.min(Math.max(1, page), totalPages);
  const start = (clampedPage - 1) * pageSize;
  return { pageItems: items.slice(start, start + pageSize), totalPages, clampedPage };
}

function isFailureItem(item: QueueItem): boolean {
  return item.stage === 'needs-clarification' || item.reason === 'qa_fail_repeated';
}

export type SortCol = 'project' | 'item' | 'stage' | 'age_seconds' | 'reason';
export type SortDir = 'asc' | 'desc';

export function applyFilters(
  items: QueueItem[],
  f: { project?: string; reason?: string; loop?: string },
): QueueItem[] {
  return items.filter(item => {
    if (f.project && item.project !== f.project) return false;
    if (f.reason && item.reason !== f.reason) return false;
    if (f.loop && item.loop_id !== f.loop) return false;
    return true;
  });
}

export function applySort(items: QueueItem[], col: SortCol, dir: SortDir): QueueItem[] {
  return [...items].sort((a, b) => {
    let cmp = 0;
    if (col === 'item') {
      cmp = a.kind !== b.kind ? a.kind.localeCompare(b.kind) : a.number - b.number;
    } else if (col === 'age_seconds') {
      cmp = a.age_seconds - b.age_seconds;
    } else {
      cmp = String(a[col]).localeCompare(String(b[col]));
    }
    return dir === 'asc' ? cmp : -cmp;
  });
}

function formatAge(seconds: number): string {
  if (seconds >= 3600) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m}m`;
  }
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

interface QueueItemDrawerContentProps {
  item: QueueItem;
  onClose: () => void;
}

function QueueItemDrawerContent({ item, onClose }: QueueItemDrawerContentProps) {
  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 500, color: 'var(--fg)' }}>
          {item.title || `${item.kind} #${item.number}`}
        </h2>
        <button className="btn" onClick={onClose}>×</button>
      </div>
      <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px var(--pad-3)', fontSize: 12 }}>
        <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Project</dt>
        <dd style={{ margin: 0 }}>{item.project}</dd>
        <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Stage</dt>
        <dd style={{ margin: 0 }}>{item.stage}</dd>
        <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Age</dt>
        <dd style={{ margin: 0 }} className="num">{formatAge(item.age_seconds)}</dd>
        <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Reason</dt>
        <dd style={{ margin: 0 }}>{item.reason}</dd>
        {item.threshold_seconds !== null && (
          <>
            <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Threshold</dt>
            <dd style={{ margin: 0 }} className="num">{formatAge(item.threshold_seconds)}</dd>
          </>
        )}
        {item.loop_id !== null && (
          <>
            <dt style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em', alignSelf: 'center' }}>Loop</dt>
            <dd style={{ margin: 0 }} className="mono">{item.loop_id}</dd>
          </>
        )}
      </dl>
      {item.github_url && (
        <a
          href={item.github_url}
          target="_blank"
          rel="noreferrer"
          className="btn primary"
          style={{ display: 'inline-block', textAlign: 'center', textDecoration: 'none' }}
        >
          View on GitHub
        </a>
      )}
    </>
  );
}

interface QueueTableProps {
  items: QueueItem[];
  onRowClick: (item: QueueItem) => void;
  sortCol?: SortCol;
  sortDir?: SortDir;
  onSort?: (col: SortCol) => void;
}

function QueueTable({ items, onRowClick, sortCol, sortDir, onSort }: QueueTableProps) {
  function Th({ col, label }: { col: SortCol; label: string }) {
    const active = col === sortCol;
    const glyph = active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';
    return (
      <th
        onClick={() => onSort?.(col)}
        style={{
          cursor: onSort ? 'pointer' : 'default',
          userSelect: 'none',
          color: active ? 'var(--fg-2)' : undefined,
        }}
      >
        {label}{glyph}
      </th>
    );
  }

  return (
    <table className="t" style={{ width: '100%' }}>
      <thead>
        <tr>
          <Th col="project" label="Project" />
          <Th col="item" label="Item" />
          <Th col="stage" label="Stage" />
          <Th col="age_seconds" label="Age" />
          <Th col="reason" label="Reason" />
        </tr>
      </thead>
      <tbody>
        {items.map(item => (
          <tr
            key={`${item.project}-${item.kind}-${item.number}`}
            onClick={() => onRowClick(item)}
            style={{ cursor: 'pointer' }}
          >
            <td>{item.project}</td>
            <td className="mono">{item.kind} #{item.number}</td>
            <td>{item.stage}</td>
            <td className="num">{formatAge(item.age_seconds)}</td>
            <td>{item.reason}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

interface QueueProps {
  globalProjectFilter?: string | null;
}

export default function Queue({ globalProjectFilter }: QueueProps) {
  const { data: items = [], isLoading } = useQuery({
    queryKey: ['actionQueue'],
    queryFn: fetchActionQueue,
    refetchInterval: 5000,
  });

  const { setDrawer } = useHashRoute();
  const [selected, setSelected] = useState<QueueItem | null>(null);
  const [filterProject, setFilterProject] = useState(globalProjectFilter ?? '');
  const [filterReason, setFilterReason] = useState('');
  const [filterLoop, setFilterLoop] = useState('');
  const [sortCol, setSortCol] = useState<SortCol>('age_seconds');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [page, setPage] = useState<number>(() => readPageFromHash());

  /** Sync page to URL hash and component state together. */
  const goToPage = useCallback((next: number) => {
    setPage(next);
    writePageToHash(next);
  }, []);

  /** Reset to page 1 when any filter changes. */
  const setFilterProjectAndReset = useCallback((v: string) => { setFilterProject(v); goToPage(1); }, [goToPage]);
  const setFilterReasonAndReset  = useCallback((v: string) => { setFilterReason(v);  goToPage(1); }, [goToPage]);
  const setFilterLoopAndReset    = useCallback((v: string) => { setFilterLoop(v);    goToPage(1); }, [goToPage]);

  useEffect(() => {
    setFilterProject(globalProjectFilter ?? '');
    goToPage(1);
  }, [globalProjectFilter, goToPage]);

  const projects = useMemo(
    () => [...new Set(items.map(i => i.project))].sort(),
    [items],
  );

  const loops = useMemo(
    () => [...new Set(items.map(i => i.loop_id).filter((id): id is string => id !== null))].sort(),
    [items],
  );

  const stuckItems = useMemo(
    () =>
      applySort(
        items.filter(i => i.reason === 'stuck_label' || i.reason === 'timeout'),
        'age_seconds',
        'desc',
      ),
    [items],
  );

  const allFiltered = useMemo(
    () =>
      applySort(
        applyFilters(items, {
          project: filterProject || undefined,
          reason: filterReason || undefined,
          loop: filterLoop || undefined,
        }),
        sortCol,
        sortDir,
      ),
    [items, filterProject, filterReason, filterLoop, sortCol, sortDir],
  );

  const { pageItems, totalPages, clampedPage } = useMemo(
    () => paginateItems(allFiltered, page),
    [allFiltered, page],
  );

  // If totalPages shrinks (e.g. filter narrowed results), clamp and sync hash.
  useEffect(() => {
    if (clampedPage !== page) {
      setPage(clampedPage);
      writePageToHash(clampedPage);
    }
  }, [clampedPage, page]);

  function handleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  }

  function handleRowClick(item: QueueItem) {
    setSelected(item);
    setDrawer(`item:${item.project}:${item.kind}:${item.number}`);
  }

  function handleClose() {
    setSelected(null);
    setDrawer(null);
  }

  if (isLoading) {
    return <div className="muted" style={{ padding: 'var(--pad-4)' }}>Loading…</div>;
  }

  const showLoopFilter = loops.length > 1;

  return (
    <div style={{ padding: 'var(--pad-4)' }}>
      {/* Stuck */}
      <section style={{ marginBottom: 'var(--pad-5)' }}>
        <div className="screen-h" style={{ paddingLeft: 0, paddingRight: 0 }}>
          <h1>Stuck</h1>
          <span className="meta">{stuckItems.length} item{stuckItems.length !== 1 ? 's' : ''}</span>
        </div>
        {stuckItems.length === 0 ? (
          <div className="muted" style={{ padding: 'var(--pad-3) 0' }}>No stuck items</div>
        ) : (
          <QueueTable items={stuckItems} onRowClick={handleRowClick} />
        )}
      </section>

      {/* All Items */}
      <section>
        <div className="screen-h" style={{ paddingLeft: 0, paddingRight: 0 }}>
          <h1>All Items</h1>
          <span className="meta">{allFiltered.length} / {items.length}</span>
        </div>

        <div style={{ display: 'flex', gap: 'var(--pad-2)', marginBottom: 'var(--pad-3)', flexWrap: 'wrap' }}>
          <select className="btn" value={filterProject} onChange={e => setFilterProjectAndReset(e.target.value)}>
            <option value="">All projects</option>
            {projects.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <select className="btn" value={filterReason} onChange={e => setFilterReasonAndReset(e.target.value)}>
            <option value="">All reasons</option>
            <option value="stuck_label">stuck_label</option>
            <option value="timeout">timeout</option>
            <option value="qa_fail_repeated">qa_fail_repeated</option>
          </select>
          {showLoopFilter && (
            <select className="btn" value={filterLoop} onChange={e => setFilterLoopAndReset(e.target.value)}>
              <option value="">All loops</option>
              {loops.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          )}
        </div>

        {allFiltered.length === 0 ? (
          <div className="muted" style={{ padding: 'var(--pad-3) 0' }}>No items</div>
        ) : (
          <>
            <QueueTable
              items={pageItems}
              onRowClick={handleRowClick}
              sortCol={sortCol}
              sortDir={sortDir}
              onSort={handleSort}
            />
            {totalPages > 1 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--pad-2)',
                  marginTop: 'var(--pad-3)',
                  fontSize: 12,
                }}
                aria-label="Pagination"
              >
                <button
                  className="btn"
                  onClick={() => goToPage(clampedPage - 1)}
                  disabled={clampedPage <= 1}
                  aria-label="Previous page"
                >
                  &lt; Prev
                </button>
                <span className="muted">Page {clampedPage} of {totalPages}</span>
                <button
                  className="btn"
                  onClick={() => goToPage(clampedPage + 1)}
                  disabled={clampedPage >= totalPages}
                  aria-label="Next page"
                >
                  Next &gt;
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {selected && isFailureItem(selected) ? (
        <FailureInspector
          project={selected.project}
          kind={selected.kind}
          number={selected.number}
          title={selected.title}
          githubUrl={selected.github_url}
          onClose={handleClose}
        />
      ) : selected ? (
        <Drawer open={true} onClose={handleClose}>
          <QueueItemDrawerContent item={selected} onClose={handleClose} />
        </Drawer>
      ) : null}
    </div>
  );
}
