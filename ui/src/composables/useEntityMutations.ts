/**
 * Composable factory for entity CRUD mutations.
 * Provides delete, toggle, and batch delete mutations with
 * automatic query invalidation and toast notifications.
 */
import { useMutation, useQueryClient, type QueryKey } from '@tanstack/vue-query';
import { useToast } from './useToast';
import { useConfirm } from './useConfirm';
import type { BatchDeleteResponse } from '@/types/entities';

export interface EntityMutationConfig<T> {
  /** Entity type name for messages (e.g., 'digest', 'source') */
  entityName: string;
  /** Plural form for batch messages (e.g., 'digests', 'sources') */
  entityNamePlural?: string;
  /** Query keys to invalidate on mutation success */
  queryKeys: QueryKey[];
  /** API function to delete a single entity */
  deleteApi?: (id: number) => Promise<void>;
  /** API function to toggle entity status */
  toggleApi?: (id: number, enabled?: boolean) => Promise<T>;
  /** API function to batch delete entities */
  batchDeleteApi?: (ids: number[]) => Promise<BatchDeleteResponse>;
}

export function useEntityMutations<T>(config: EntityMutationConfig<T>) {
  const {
    entityName,
    entityNamePlural = `${entityName}s`,
    queryKeys,
    deleteApi,
    toggleApi,
    batchDeleteApi,
  } = config;

  const queryClient = useQueryClient();
  const toast = useToast();
  const { confirmDelete } = useConfirm();

  // Invalidate all related queries
  const invalidateQueries = () => {
    queryKeys.forEach(key => {
      queryClient.invalidateQueries({ queryKey: key });
    });
  };

  // Single delete mutation
  const deleteMutation = deleteApi
    ? useMutation({
        mutationFn: deleteApi,
        onSuccess: () => {
          toast.success(`${capitalize(entityName)} deleted successfully`);
          invalidateQueries();
        },
        onError: (error: Error) => {
          toast.error(`Failed to delete ${entityName}: ${error.message}`);
        },
      })
    : null;

  // Toggle mutation (for enabled/disabled status)
  const toggleMutation = toggleApi
    ? useMutation({
        mutationFn: toggleApi,
        onSuccess: () => {
          toast.success(`${capitalize(entityName)} updated`);
          invalidateQueries();
        },
        onError: (error: Error) => {
          toast.error(`Failed to update ${entityName}: ${error.message}`);
        },
      })
    : null;

  // Batch delete mutation
  const batchDeleteMutation = batchDeleteApi
    ? useMutation({
        mutationFn: batchDeleteApi,
        onSuccess: (result) => {
          if (result.deleted_count > 0) {
            toast.success(`Deleted ${result.deleted_count} ${result.deleted_count === 1 ? entityName : entityNamePlural}`);
          }
          if (result.failed_ids.length > 0) {
            toast.warning(`${result.failed_ids.length} ${entityNamePlural} could not be deleted`);
          }
          invalidateQueries();
        },
        onError: (error: Error) => {
          toast.error(`Failed to delete ${entityNamePlural}: ${error.message}`);
        },
      })
    : null;

  // Helper to delete with confirmation
  const deleteWithConfirm = async (id: number, itemName: string) => {
    if (!deleteMutation) {
      console.warn('Delete API not configured');
      return false;
    }
    if (confirmDelete(itemName, entityName)) {
      await deleteMutation.mutateAsync(id);
      return true;
    }
    return false;
  };

  // Helper to batch delete with confirmation
  const batchDeleteWithConfirm = async (ids: number[]) => {
    if (!batchDeleteMutation) {
      console.warn('Batch delete API not configured');
      return false;
    }
    const count = ids.length;
    const message = `Are you sure you want to delete ${count} ${count === 1 ? entityName : entityNamePlural}? This action cannot be undone.`;
    if (window.confirm(message)) {
      await batchDeleteMutation.mutateAsync(ids);
      return true;
    }
    return false;
  };

  return {
    // Mutations
    deleteMutation,
    toggleMutation,
    batchDeleteMutation,
    // Helper methods
    deleteWithConfirm,
    batchDeleteWithConfirm,
    invalidateQueries,
  };
}

// Helper function to capitalize first letter
function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}
