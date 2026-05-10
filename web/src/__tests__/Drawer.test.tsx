import { describe, it, expect, afterEach } from 'vitest';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import Drawer from '../components/Drawer';

let container: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

function setup() {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
}

function teardown() {
  act(() => root.unmount());
  container.remove();
}

function render(ui: React.ReactElement) {
  act(() => root.render(ui));
}

afterEach(teardown);

describe('Drawer', () => {
  it('renders nothing when open=false', () => {
    setup();
    render(<Drawer open={false} onClose={() => {}}><p>content</p></Drawer>);
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it('renders panel when open=true', () => {
    setup();
    render(<Drawer open={true} onClose={() => {}}><p>content</p></Drawer>);
    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
  });

  it('shows title and wires aria-labelledby', () => {
    setup();
    render(<Drawer open={true} onClose={() => {}} title="Test Title"><p>body</p></Drawer>);
    const dialog = container.querySelector('[role="dialog"]')!;
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();
    const titleEl = container.querySelector(`#${CSS.escape(labelId!)}`) as HTMLElement;
    expect(titleEl?.textContent).toBe('Test Title');
  });

  it('calls onClose when Escape is pressed', () => {
    setup();
    let closed = false;
    render(<Drawer open={true} onClose={() => { closed = true; }}><p>content</p></Drawer>);
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(closed).toBe(true);
  });

  it('calls onClose when overlay is clicked', () => {
    setup();
    let closed = false;
    render(<Drawer open={true} onClose={() => { closed = true; }}><p>content</p></Drawer>);
    const overlay = container.querySelector('.drawer-overlay') as HTMLElement;
    act(() => overlay.click());
    expect(closed).toBe(true);
  });

  it('does not close when panel itself is clicked', () => {
    setup();
    let closed = false;
    render(<Drawer open={true} onClose={() => { closed = true; }}><p>content</p></Drawer>);
    const panel = container.querySelector('.drawer-panel') as HTMLElement;
    act(() => panel.click());
    expect(closed).toBe(false);
  });

  it('places initial focus inside the panel', () => {
    setup();
    render(
      <Drawer open={true} onClose={() => {}}>
        <button id="first-btn">First</button>
      </Drawer>
    );
    const firstFocusable = container.querySelector('button') as HTMLElement;
    expect(document.activeElement === firstFocusable).toBe(true);
  });

  it('restores focus to previously focused element on close', () => {
    setup();
    const trigger = document.createElement('button');
    trigger.textContent = 'Trigger';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    render(<Drawer open={true} onClose={() => {}}><p>content</p></Drawer>);
    render(<Drawer open={false} onClose={() => {}}><p>content</p></Drawer>);

    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
