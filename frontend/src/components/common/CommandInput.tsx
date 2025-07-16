import { useState, useRef, useEffect } from 'react';
import { Search } from 'lucide-react';

interface CommandInputProps {
  onSubmit: (command: string) => void;
  placeholder?: string;
  initialValue?: string;
  autoFocus?: boolean;
}

export function CommandInput({ 
  onSubmit, 
  placeholder = 'type command...', 
  initialValue = '',
  autoFocus = false
}: CommandInputProps) {
  const [input, setInput] = useState(initialValue);
  const inputRef = useRef<HTMLInputElement>(null);
  
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSubmit(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="border border-terminal-gray rounded bg-terminal-bg/20 focus-within:border-terminal-green transition-colors">
        <div className="flex items-center px-3 py-2">
          <span className="text-terminal-green text-lg mr-3">$</span>
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="bg-transparent border-none outline-none text-terminal-fg flex-1 font-mono placeholder:text-terminal-muted/60"
            data-search-input
          />
          {input.length === 0 && (
            <Search className="w-4 h-4 text-terminal-muted" />
          )}
        </div>
      </div>
    </form>
  );
}