// @vitest-environment happy-dom
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import React from 'react';

// Silence React's act() environment check warning
// (happy-dom doesn't set IS_REACT_ACT_ENVIRONMENT automatically)
// @ts-expect-error - global not in typedefs
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import Drawer from '../components/Drawer';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let container: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => {
    root.unmount();
  });
  container.remove();
});

function render(ui: React.ReactElement) {
  act(() => {
    root.render(ui);
  });
}

function fireKeydown(key: string) {
  const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true });
  document.dispatchEvent(event);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Drawer', () => {
  it('renders nothing when open=false', () => {
    render(
      <Drawer open={false} onClose={() => {}}>
        <p id="content">hello</p>
      </Drawer>,
    );
    expect(document.getElementById('content')).toBeNull();
  });

  it('renders children when open=true', () => {
    render(
      <Drawer open={true} onClose={() => {}}>
        <p id="content">hello</p>
      </Drawer>,
    );
    expect(document.getElementById('content')).not.toBeNull();
  });

  it('renders title when provided', () => {
    render(
      <Drawer open={true} onClose={() => {}} title="My Drawer">
        <p>content</p>
      </Drawer>,
    );
    const h2 = document.querySelector('h2');
    expect(h2).not.toBeNull();
    expect(h2!.textContent).toContain('My Drawer');
  });

  it('panel has role=dialog and aria-modal=true', () => {
    render(
      <Drawer open={true} onClose={() => {}}>
        <p>content</p>
      </Drawer>,
    );
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog!.getAttribute('aria-modal')).toBe('true');
  });

  it('closes when Escape key is pressed', () => {
    let closed = false;
    render(
      <Drawer open={true} onClose={() => { closed = true; }}>
        <p>content</p>
      </Drawer>,
    );
    act(() => {
      fireKeydown('Escape');
    });
    expect(closed).toBe(true);
  });

  it('closes when overlay (backdrop) is clicked', () => {
    let closed = false;
    render(
      <Drawer open={true} onClose={() => { closed = true; }}>
        <p id="inner">content</p>
      </Drawer>,
    );
    // The overlay is the outermost fixed div (the scrim), not the panel.
    // Find it by looking for the fixed-position div that wraps the panel.
    const portal = document.body.lastElementChild as HTMLElement;
    act(() => {
      portal.click();
    });
    expect(closed).toBe(true);
  });

  it('does not close when the panel itself is clicked', () => {
    let closed = false;
    render(
      <Drawer open={true} onClose={() => { closed = true; }}>
        <p id="inner">content</p>
      </Drawer>,
    );
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    act(() => {
      dialog.click();
    });
    expect(closed).toBe(false);
  });

  it('focuses inside panel when opened', () => {
    render(
      <Drawer open={true} onClose={() => {}}>
        <button id="first-btn">First</button>
      </Drawer>,
    );
    // Focus should have moved to the first focusable element
    const btn = document.getElementById('first-btn');
    expect(document.activeElement).toBe(btn);
  });

  it('restores focus to previously focused element on close', () => {
    // Create a button outside the drawer and focus it
    const trigger = document.createElement('button');
    trigger.id = 'trigger';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    // Open drawer
    render(
      <Drawer open={true} onClose={() => {}}>
        <button id="inside">Inside</button>
      </Drawer>,
    );

    // Focus should be inside panel now
    expect(document.activeElement?.id).toBe('inside');

    // Close drawer (re-render with open=false)
    act(() => {
      root.render(
        <Drawer open={false} onClose={() => {}}>
          <button id="inside">Inside</button>
        </Drawer>,
      );
    });

    // Focus should return to trigger
    expect(document.activeElement).toBe(trigger);

    trigger.remove();
  });
});
