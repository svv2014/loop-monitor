interface RoleTagProps {
  role: string;
  solid?: boolean;
}

export default function RoleTag({ role, solid }: RoleTagProps) {
  return (
    <span
      className={`tag role-${role}`}
      style={solid ? {
        background: `var(--role-${role})`,
        color: 'var(--bg)',
        borderColor: `var(--role-${role})`,
      } : {}}
    >
      {role}
    </span>
  );
}
