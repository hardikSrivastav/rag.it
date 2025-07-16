import { Connector } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { RefreshCw, AlertCircle, CheckCircle, Clock } from 'lucide-react';

interface ConnectorCardProps {
  connector: Connector;
  onSync: (id: string) => void;
  onTest: (id: string) => void;
}

const statusConfig = {
  online: { 
    icon: CheckCircle, 
    color: 'text-terminal-green', 
    dot: 'bg-terminal-green',
    label: 'online'
  },
  syncing: { 
    icon: RefreshCw, 
    color: 'text-terminal-amber', 
    dot: 'bg-terminal-amber animate-pulse',
    label: 'syncing'
  },
  error: { 
    icon: AlertCircle, 
    color: 'text-red-400', 
    dot: 'bg-red-400',
    label: 'error'
  },
  offline: { 
    icon: Clock, 
    color: 'text-terminal-muted', 
    dot: 'bg-terminal-muted',
    label: 'offline'
  }
};

const connectorSymbols = {
  gmail: '✉',
  calendar: '📅',
  github: '⚡',
  notion: '📝'
};

export function ConnectorCard({ connector, onSync, onTest }: ConnectorCardProps) {
  const status = statusConfig[connector.status];
  const StatusIcon = status.icon;
  const symbol = connectorSymbols[connector.type] || '📄';

  return (
    <div className="border border-terminal-gray rounded bg-terminal-bg/20 hover:bg-terminal-bg/40 transition-all duration-200 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{symbol}</span>
          <span className="text-terminal-fg font-medium">&{connector.type}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${status.dot}`}></div>
          <span className={`text-xs ${status.color}`}>{status.label}</span>
        </div>
      </div>

      {/* Stats */}
      <div className="space-y-1 mb-4">
        {connector.items_count !== undefined && (
          <div className="text-terminal-muted text-sm">
            {connector.items_count.toLocaleString()} items
          </div>
        )}
        {connector.last_sync && (
          <div className="text-terminal-muted text-xs">
            last: {new Date(connector.last_sync).toLocaleDateString()}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onSync(connector.id)}
          disabled={connector.status === 'syncing'}
          className="flex-1 text-xs"
        >
          {connector.status === 'syncing' ? (
            <RefreshCw className="w-3 h-3 animate-spin" />
          ) : (
            'sync'
          )}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onTest(connector.id)}
          className="text-xs"
        >
          test
        </Button>
      </div>
    </div>
  );
}