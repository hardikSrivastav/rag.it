import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { connectorsApi, Connector } from '@/lib/api';
import { useToast } from './use-toast';

export function useConnectors() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsApi.list,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const syncMutation = useMutation({
    mutationFn: connectorsApi.sync,
    onSuccess: (_, connectorId) => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
      toast({
        title: 'Sync started',
        description: `Syncing connector ${connectorId}`,
      });
    },
    onError: (error) => {
      toast({
        title: 'Sync failed',
        description: String(error),
        variant: 'destructive',
      });
    }
  });

  const syncAllMutation = useMutation({
    mutationFn: connectorsApi.syncAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
      toast({
        title: 'Sync started',
        description: 'Syncing all connectors',
      });
    },
    onError: (error) => {
      toast({
        title: 'Sync failed',
        description: String(error),
        variant: 'destructive',
      });
    }
  });

  const testMutation = useMutation({
    mutationFn: connectorsApi.test,
    onSuccess: (result, connectorId) => {
      toast({
        title: result.success ? 'Connection successful' : 'Connection failed',
        description: result.message,
        variant: result.success ? 'default' : 'destructive',
      });
    },
  });

  const getConnectorByType = (type: string): Connector | undefined => {
    return connectors.find(c => c.type === type);
  };

  const getConnectorById = (id: string): Connector | undefined => {
    return connectors.find(c => c.id === id);
  };

  return {
    connectors,
    isLoading,
    syncConnector: syncMutation.mutate,
    syncAll: syncAllMutation.mutate,
    testConnector: testMutation.mutate,
    getConnectorByType,
    getConnectorById,
    isSyncing: syncMutation.isPending || syncAllMutation.isPending,
  };
}