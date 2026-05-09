import { useQuery } from '@tanstack/react-query';
import { apiClient, type ActiveWorker, type FeedEvent, type PipelineRun, type PrMonitorRow, type ProjectStatusEntry } from '../api/client';

export function useProjectRuns(project: string | null) {
  return useQuery<PipelineRun[]>({
    queryKey: ['runs', project],
    queryFn: () => apiClient.getProjectRuns(project!),
    enabled: !!project,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}

export function useProjectPrs(project: string | null, includeFinished = false) {
  return useQuery<PrMonitorRow[]>({
    queryKey: ['prs', project, includeFinished],
    queryFn: () => apiClient.getProjectPrs(project!, includeFinished),
    enabled: !!project,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useProjectFeed(project: string | null) {
  return useQuery<FeedEvent[]>({
    queryKey: ['feed', project],
    queryFn: () => apiClient.getFeed(),
    enabled: !!project,
    refetchInterval: 10_000,
    staleTime: 5_000,
    select: (data) => (project ? data.filter((e) => e.project === project) : data),
  });
}

export function useActiveWorkers() {
  return useQuery<ActiveWorker[]>({
    queryKey: ['active'],
    queryFn: () => apiClient.getActive(),
    refetchInterval: 5_000,
    staleTime: 3_000,
  });
}

export function useProjectStatus() {
  return useQuery<ProjectStatusEntry[]>({
    queryKey: ['status'],
    queryFn: () => apiClient.getStatus(),
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}
