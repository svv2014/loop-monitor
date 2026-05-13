import { useEffect, useId, useRef } from 'react';
import ReactDOM from 'react-dom';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

export default function Drawer({ open, onClose, title, children }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<Element | null>(null);
  const titleId = useId();

  // Save and restore focus
  useEffect(() => {
    if (open) {
      previousFocusRef.current = document.activeElement;
      // Move focus into panel on next tick so the panel is rendered
      const panel = panelRef.current;
      if (panel) {
        const first = panel.querySelector<HTMLElement>(FOCUSABLE);
        if (first) {
          first.focus();
        } else {
          panel.focus();
        }
      }
    } else {
      const prev = previousFocusRef.current;
      if (prev && prev instanceof HTMLElement) {
        prev.focus();
      }
      previousFocusRef.current = null;
    }
  }, [open]);

  // Esc to close
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    }
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [open, onClose]);

  // Focus trap
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  if (!open) return null;

  return ReactDOM.createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'var(--scrim)',
        zIndex: 200,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        onClick={e => e.stopPropagation()}
        style={{
          width: 360,
          height: '100%',
          background: 'var(--bg-2)',
          borderLeft: '1px solid var(--border)',
          padding: 'var(--pad-4)',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--pad-3)',
        }}
      >
        {title && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2
              id={titleId}
              style={{
                margin: 0,
                fontSize: 13,
                fontFamily: 'var(--font-mono)',
                fontWeight: 500,
                color: 'var(--fg)',
              }}
            >
              {title}
            </h2>
            <button className="btn" onClick={onClose} aria-label="Close drawer">
              ×
            </button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
