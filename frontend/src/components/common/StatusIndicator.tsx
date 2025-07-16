import { RefreshCw, AlertCircle, CheckCircle, Clock } from 'lucide-react';

type StatusType = 'online' | 'syncing' | 'error' | 'offline';

interface StatusIndicatorProps {
  status: StatusType;
  showLabel?: boolean;
  className?: string;
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

export function StatusIndicator({ status, showLabel = true, className = '' }: StatusIndicatorProps) {
  const config = statusConfig[status];
  const Icon = config.icon;
  
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`w-2 h-2 rounded-full ${config.dot}`}></div>
      {showLabel && <span className={`text-xs ${config.color}`}>{config.label}</span>}
    </div>
  );
}