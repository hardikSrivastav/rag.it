import { ReactNode } from 'react';

interface HotkeyIndicatorProps {
  hotkey: string;
  className?: string;
}

export function HotkeyIndicator({ hotkey, className = '' }: HotkeyIndicatorProps) {
  return (
    <span className={`text-terminal-muted text-xs border border-terminal-muted px-1 py-0.5 rounded ${className}`}>
      {hotkey}
    </span>
  );
}

interface HotkeyLabelProps {
  hotkey: string;
  children: ReactNode;
  className?: string;
}

export function HotkeyLabel({ hotkey, children, className = '' }: HotkeyLabelProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {children}
      <HotkeyIndicator hotkey={hotkey} />
    </div>
  );
}