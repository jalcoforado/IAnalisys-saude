import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { homeService, type HomeLayoutItem } from '@/services/home.service'

const QUERY_KEY = ['home', 'layout'] as const

export function useHomeLayout() {
  const qc = useQueryClient()

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: () => homeService.getLayout(),
    staleTime: Infinity,
  })

  const mutation = useMutation({
    mutationFn: (layout: HomeLayoutItem[]) => homeService.saveLayout(layout),
    onSuccess: (data) => qc.setQueryData(QUERY_KEY, data),
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    save: mutation.mutate,
    saveAsync: mutation.mutateAsync,
    isSaving: mutation.isPending,
  }
}
