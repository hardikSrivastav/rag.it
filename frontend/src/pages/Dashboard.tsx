import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { connectorsApi } from '@/lib/api';
import { ConnectorCard } from '@/components/connectors/ConnectorCard';
import { Button } from '@/components/ui/button';
import { RefreshCw } from 'lucide-react';
import { useEffect } from 'react';

export function Dashboard() {
  const queryClient = useQueryClient();

  const { data: connectors = [], isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: connectorsApi.list,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const syncMutation = useMutation({
    mutationFn: connectorsApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });

  const syncAllMutation = useMutation({
    mutationFn: connectorsApi.syncAll,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    },
  });

  const testMutation = useMutation({
    mutationFn: connectorsApi.test,
    onSuccess: (result, connectorId) => {
      console.log(`Test result for ${connectorId}:`, result);
      // Could show toast notification here
    },
  });

  // Listen for refresh hotkey
  useEffect(() => {
    const handleRefresh = () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] });
    };

    window.addEventListener('refresh-data', handleRefresh);
    return () => window.removeEventListener('refresh-data', handleRefresh);
  }, [queryClient]);

  const onlineConnectors = connectors.filter(c => c.status === 'online').length;
  const totalItems = connectors.reduce((sum, c) => sum + (c.items_count || 0), 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-100px)]">
        <div className="text-terminal-muted">loading connectors...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-terminal-fg text-xl mb-2">
            #dashboard <span className="text-terminal-muted text-sm">v1.0</span>
          </h1>
          <div className="text-terminal-muted text-sm space-x-4">
            <span>{onlineConnectors}/{connectors.length} online</span>
            <span>{totalItems.toLocaleString()} items indexed</span>
          </div>
        </div>
        
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => syncAllMutation.mutate()}
            disabled={syncAllMutation.isPending}
            className="flex items-center gap-2"
          >
            {syncAllMutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              'sync all'
            )}
            <span className="text-terminal-muted text-xs border border-terminal-muted px-1 py-0.5 rounded">
              r
            </span>
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'connectors', value: connectors.length, color: 'text-terminal-green' },
          { label: 'online', value: onlineConnectors, color: 'text-terminal-amber' },
          { label: 'syncing', value: connectors.filter(c => c.status === 'syncing').length, color: 'text-blue-400' },
          { label: 'errors', value: connectors.filter(c => c.status === 'error').length, color: 'text-red-400' },
        ].map((stat) => (
          <div key={stat.label} className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
            <div className="text-terminal-muted uppercase tracking-wide text-xs mb-1">
              {stat.label}
            </div>
            <div className={`text-2xl font-medium ${stat.color}`}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Connectors Grid */}
      <div className="space-y-4">
        <h2 className="text-terminal-fg text-lg">#connectors</h2>
        
        {connectors.length === 0 ? (
          <div className="text-center py-12 text-terminal-muted">
            <div className="text-4xl mb-4">📡</div>
            <div>no connectors configured</div>
            <div className="text-sm mt-2">add connectors in settings</div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {connectors.map((connector) => (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                onSync={(id) => syncMutation.mutate(id)}
                onTest={(id) => testMutation.mutate(id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Command Hints */}
      <div className="mt-12 border-t border-terminal-gray pt-6">
        <div className="text-terminal-muted text-sm">
          <div className="mb-2">#quick actions</div>
          <div className="flex flex-wrap gap-4 text-xs">
            <span><span className="text-terminal-green">1</span> → chat</span>
            <span><span className="text-terminal-green">2</span> → browse</span>
            <span><span className="text-terminal-green">r</span> → refresh</span>
            <span><span className="text-terminal-green">/</span> → search</span>
          </div>
        </div>
      </div>
    </div>
  );
}