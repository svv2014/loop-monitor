// useRoles — fetch the operator-configured role vocabulary from the server.
// Server reads config/roles.yaml; falls back to built-in Loop defaults if
// no config exists. The hook always returns a non-empty list so consumers
// never need to special-case loading state.
import { useQuery } from '@tanstack/react-query';
import { DEFAULT_ROLES, fetchRoles, RoleConfig } from './api';

export function useRoles(): RoleConfig[] {
  const { data } = useQuery({
    queryKey: ['config', 'roles'],
    queryFn: fetchRoles,
    staleTime: 5 * 60_000, // 5 min — roles change rarely (operator yaml edit + restart)
  });
  return data ?? DEFAULT_ROLES;
}

export function useRoleIds(): string[] {
  return useRoles().map((r) => r.id);
}
