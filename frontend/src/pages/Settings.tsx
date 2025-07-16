import { Button } from '@/components/ui/button';
import { Settings as SettingsIcon, Database, Zap, Shield, Info } from 'lucide-react';

export function Settings() {
  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-terminal-fg text-xl mb-2">
          #settings <span className="text-terminal-muted text-sm">v1.0</span>
        </h1>
        <div className="text-terminal-muted text-sm">
          configure connectors and system preferences
        </div>
      </div>

      {/* Settings Sections */}
      <div className="space-y-8">
        {/* Connectors */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Database className="w-5 h-5 text-terminal-green" />
            <h2 className="text-terminal-fg text-lg">#connectors</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { name: 'gmail', status: 'configured', description: 'sync emails and attachments' },
              { name: 'calendar', status: 'configured', description: 'sync events and meetings' },
              { name: 'github', status: 'configured', description: 'sync repositories and code' },
              { name: 'notion', status: 'not configured', description: 'sync pages and databases' },
            ].map((connector) => (
              <div key={connector.name} className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-terminal-fg">&{connector.name}</span>
                  <span className={`text-xs px-2 py-1 rounded ${
                    connector.status === 'configured' 
                      ? 'bg-terminal-green/20 text-terminal-green' 
                      : 'bg-terminal-muted/20 text-terminal-muted'
                  }`}>
                    {connector.status}
                  </span>
                </div>
                <div className="text-terminal-muted text-sm mb-3">
                  {connector.description}
                </div>
                <Button variant="outline" size="sm" className="text-xs">
                  {connector.status === 'configured' ? 'reconfigure' : 'setup'}
                </Button>
              </div>
            ))}
          </div>
        </section>

        {/* System */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-terminal-amber" />
            <h2 className="text-terminal-fg text-lg">#system</h2>
          </div>
          
          <div className="space-y-4">
            <div className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-terminal-fg">sync interval</span>
                <span className="text-terminal-muted text-sm">30 minutes</span>
              </div>
              <div className="text-terminal-muted text-sm mb-3">
                how often to automatically sync connectors
              </div>
              <Button variant="outline" size="sm" className="text-xs">
                configure
              </Button>
            </div>

            <div className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-terminal-fg">embedding model</span>
                <span className="text-terminal-muted text-sm">sentence-transformers</span>
              </div>
              <div className="text-terminal-muted text-sm mb-3">
                model used for document embeddings
              </div>
              <Button variant="outline" size="sm" className="text-xs">
                change
              </Button>
            </div>
          </div>
        </section>

        {/* Security */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-blue-400" />
            <h2 className="text-terminal-fg text-lg">#security</h2>
          </div>
          
          <div className="space-y-4">
            <div className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-terminal-fg">oauth tokens</span>
                <span className="text-terminal-green text-sm">✓ encrypted</span>
              </div>
              <div className="text-terminal-muted text-sm mb-3">
                all oauth tokens are encrypted at rest
              </div>
              <Button variant="outline" size="sm" className="text-xs">
                manage
              </Button>
            </div>

            <div className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-terminal-fg">data retention</span>
                <span className="text-terminal-muted text-sm">90 days</span>
              </div>
              <div className="text-terminal-muted text-sm mb-3">
                how long to keep indexed documents
              </div>
              <Button variant="outline" size="sm" className="text-xs">
                configure
              </Button>
            </div>
          </div>
        </section>

        {/* About */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Info className="w-5 h-5 text-purple-400" />
            <h2 className="text-terminal-fg text-lg">#about</h2>
          </div>
          
          <div className="border border-terminal-gray rounded bg-terminal-bg/20 p-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-terminal-muted">version</span>
                <span className="text-terminal-fg">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">backend</span>
                <span className="text-terminal-fg">fastapi + python</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">frontend</span>
                <span className="text-terminal-fg">react + typescript</span>
              </div>
              <div className="flex justify-between">
                <span className="text-terminal-muted">database</span>
                <span className="text-terminal-fg">postgresql + qdrant</span>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Hotkey Hints */}
      <div className="mt-12 border-t border-terminal-gray pt-6">
        <div className="text-terminal-muted text-sm">
          <div className="mb-2">#navigation</div>
          <div className="flex flex-wrap gap-4 text-xs">
            <span><span className="text-terminal-green">0</span> → dashboard</span>
            <span><span className="text-terminal-green">1</span> → chat</span>
            <span><span className="text-terminal-green">2</span> → browse</span>
          </div>
        </div>
      </div>
    </div>
  );
}