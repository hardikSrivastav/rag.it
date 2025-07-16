import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { useHotkeys } from '@/hooks/use-hotkeys';

interface TerminalLayoutProps {
  children: ReactNode;
}

export function TerminalLayout({ children }: TerminalLayoutProps) {
  useHotkeys();
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'dashboard', key: '0' },
    { path: '/chat', label: 'chat', key: '1' },
    { path: '/browse', label: 'browse', key: '2' },
    { path: '/settings', label: 'settings', key: '3' },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground font-mono">
      {/* Header */}
      <nav className="flex justify-between items-center p-6 md:p-8 border-b border-border">
        <div className="font-mono text-terminal-green flex items-center gap-2">
          ~/rag-system
          <span className="text-terminal-muted text-xs border border-terminal-muted px-1 py-0.5 rounded">
            0
          </span>
        </div>
        
        <div className="flex items-center gap-6">
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-terminal-green rounded-full animate-pulse"></div>
            <span className="text-terminal-muted text-xs border border-terminal-muted px-2 py-1 rounded">
              hotkeys enabled
            </span>
          </div>
          
          {/* Navigation */}
          <div className="flex gap-6">
            {navItems.map((item) => (
              <Button key={item.path} variant="terminal" asChild>
                <Link 
                  to={item.path} 
                  className={`flex items-center gap-2 ${
                    location.pathname === item.path ? 'text-terminal-fg' : ''
                  }`}
                >
                  {item.label}
                  <span className="text-terminal-muted text-xs border border-terminal-muted px-1 py-0.5 rounded">
                    {item.key}
                  </span>
                </Link>
              </Button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
}