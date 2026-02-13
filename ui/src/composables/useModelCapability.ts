/**
 * Composable for model capability awareness.
 *
 * Wraps the resolved default provider query and exposes
 * whether the active model is considered "small" (< 14B parameters).
 * Used to show contextual nudges in the UI.
 */

import { computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { providersApi } from '@/services/api';

export function useModelCapability() {
  const { data: resolvedProvider } = useQuery({
    queryKey: ['providers', 'default'],
    queryFn: () => providersApi.getDefault(),
    staleTime: 5000,
  });

  const capabilityTier = computed(() => resolvedProvider.value?.capability_tier ?? null);
  const isSmallModel = computed(() => capabilityTier.value === 'basic');

  return { resolvedProvider, capabilityTier, isSmallModel };
}
