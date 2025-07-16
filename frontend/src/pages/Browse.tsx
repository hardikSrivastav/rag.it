import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { documentsApi, Document } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Search, FileText, Calendar, Mail, Github, Book } from 'lucide-react';

const connectorIcons = {
  gmail: Mail,
  calendar: Calendar,
  github: Github,
  notion: Book,
};

export function Browse() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedConnector, setSelectedConnector] = useState<string>('');

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents', selectedConnector],
    queryFn: () => documentsApi.list(selectedConnector || undefined),
  });

  const { data: searchResults = [], isLoading: isSearching } = useQuery({
    queryKey: ['search', searchQuery],
    queryFn: () => documentsApi.search(searchQuery),
    enabled: searchQuery.length > 2,
  });

  const displayDocuments = searchQuery.length > 2 ? searchResults : documents;

  const connectorCounts = documents.reduce((acc, doc) => {
    acc[doc.connector] = (acc[doc.connector] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const connectors = Object.keys(connectorCounts);

  return (
    <div className="flex h-[calc(100vh-100px)]">
      {/* Sidebar */}
      <div className="w-80 border-r border-terminal-gray p-6 space-y-6">
        {/* Search */}
        <div>
          <div className="text-terminal-muted text-sm mb-2">#search</div>
          <div className="border border-terminal-gray rounded bg-terminal-bg/20 focus-within:border-terminal-green transition-colors">
            <div className="flex items-center px-3 py-2">
              <Search className="w-4 h-4 text-terminal-muted mr-2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="search documents..."
                className="bg-transparent border-none outline-none text-terminal-fg flex-1 font-mono text-sm placeholder:text-terminal-muted/60"
                data-search-input
              />
            </div>
          </div>
        </div>

        {/* Connectors Filter */}
        <div>
          <div className="text-terminal-muted text-sm mb-2">#connectors</div>
          <div className="space-y-1">
            <Button
              variant={selectedConnector === '' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setSelectedConnector('')}
              className="w-full justify-start text-xs"
            >
              all ({documents.length})
            </Button>
            {connectors.map((connector) => {
              const Icon = connectorIcons[connector as keyof typeof connectorIcons] || FileText;
              return (
                <Button
                  key={connector}
                  variant={selectedConnector === connector ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setSelectedConnector(connector)}
                  className="w-full justify-start text-xs"
                >
                  <Icon className="w-3 h-3 mr-2" />
                  &{connector} ({connectorCounts[connector]})
                </Button>
              );
            })}
          </div>
        </div>

        {/* Stats */}
        <div>
          <div className="text-terminal-muted text-sm mb-2">#stats</div>
          <div className="space-y-1 text-xs text-terminal-muted">
            <div>total: {documents.length} documents</div>
            {searchQuery && (
              <div>found: {searchResults.length} results</div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-terminal-fg text-xl">
            #browse {searchQuery && `"${searchQuery}"`}
          </h1>
          <div className="text-terminal-muted text-sm">
            {isLoading || isSearching ? 'loading...' : `${displayDocuments.length} items`}
          </div>
        </div>

        {/* Documents List */}
        <div className="space-y-4">
          {displayDocuments.length === 0 ? (
            <div className="text-center py-12 text-terminal-muted">
              <div className="text-4xl mb-4">📄</div>
              <div>
                {searchQuery ? 'no results found' : 'no documents available'}
              </div>
              {searchQuery && (
                <div className="text-sm mt-2">try a different search term</div>
              )}
            </div>
          ) : (
            displayDocuments.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function DocumentCard({ document }: { document: Document }) {
  const Icon = connectorIcons[document.connector as keyof typeof connectorIcons] || FileText;
  
  return (
    <div className="border border-terminal-gray rounded bg-terminal-bg/20 hover:bg-terminal-bg/40 transition-all duration-200 p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-terminal-green" />
          <span className="text-terminal-fg font-medium">{document.title}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-terminal-muted">&{document.connector}</span>
          <span className="text-terminal-muted">
            {new Date(document.indexed_at).toLocaleDateString()}
          </span>
        </div>
      </div>
      
      <div className="text-terminal-muted text-sm mb-3 line-clamp-3">
        {document.content.substring(0, 200)}...
      </div>
      
      {document.metadata && Object.keys(document.metadata).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(document.metadata).slice(0, 3).map(([key, value]) => (
            <span key={key} className="text-xs bg-terminal-gray px-2 py-1 rounded text-terminal-muted">
              {key}: {String(value).substring(0, 20)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}