interface IssueRefProps {
  number: number;
  url?: string | null;
}

export default function IssueRef({ number, url }: IssueRefProps) {
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="mono"
        style={{
          fontSize: 'inherit',
          color: 'var(--fg-3)',
          textDecoration: 'none',
          cursor: 'pointer',
        }}
        onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
        onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
      >
        #{number}
      </a>
    );
  }
  return <span className="mono">#{number}</span>;
}
