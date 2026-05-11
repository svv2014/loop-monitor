const GLYPH_MAP: Record<string, { sym: string; cls: string; color?: string }> = {
  po_start:    { sym: '▸', cls: 'role-po' },
  po_done:     { sym: '◆', cls: 'role-po' },
  dev_start:   { sym: '▸', cls: 'role-dev' },
  dev_done:    { sym: '◆', cls: 'role-dev' },
  qa_pass:     { sym: '✓', cls: 'role-qa' },
  qa_fail:     { sym: '✗', cls: 'role-qa', color: 'var(--fail)' },
  review_done: { sym: '◆', cls: 'role-reviewer' },
  merge_done:  { sym: '⬢', cls: 'role-merge' },
  judge_done:  { sym: '★', cls: 'role-judge' },
};

interface EventGlyphProps {
  event: string;
}

export default function EventGlyph({ event }: EventGlyphProps) {
  const m = GLYPH_MAP[event] ?? { sym: '·', cls: 'muted' };
  return (
    <span
      className={m.cls}
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 13,
        lineHeight: 1,
        ...(m.color ? { color: m.color } : {}),
      }}
    >
      {m.sym}
    </span>
  );
}
