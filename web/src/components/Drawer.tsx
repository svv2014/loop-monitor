import { useEffect, useId, useRef } from 'react';
import type { ReactNode } from 'react';

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function Drawer({ open, onClose, title, children }: DrawerProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const lastFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    lastFocusedRef.current = document.activeElement as HTMLElement;

    const panel = panelRef.current;
    if (!panel) return;

    const focusables = () =>
      Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        el => !el.hasAttribute('disabled')
      );

    const first = focusables()[0];
    if (first) first.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'Tab') {
        const targets = focusables();
        if (targets.length === 0) { e.preventDefault(); return; }
        const firstEl = targets[0];
        const lastEl = targets[targets.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === firstEl) {
            e.preventDefault();
            lastEl.focus();
          }
        } else {
          if (document.activeElement === lastEl) {
            e.preventDefault();
            firstEl.focus();
          }
        }
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open && lastFocusedRef.current) {
      lastFocusedRef.current.focus();
      lastFocusedRef.current = null;
    }
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="drawer-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'var(--scrim)',
        zIndex: 200,
      }}
      onClick={onClose}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        className="drawer-panel"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 360,
          background: 'var(--bg-2)',
          borderLeft: '1px solid var(--border)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div
          className="drawer-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--pad-3) var(--pad-4)',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {title && (
            <span
              id={titleId}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                color: 'var(--fg-3)',
              }}
            >
              {title}
            </span>
          )}
          <button
            className="btn drawer-close"
            onClick={onClose}
            aria-label="Close"
            style={{ marginLeft: 'auto' }}
          >
            ×
          </button>
        </div>
        <div style={{ flex: 1, padding: 'var(--pad-4)' }}>{children}</div>
      </div>
    </div>
  );
}
