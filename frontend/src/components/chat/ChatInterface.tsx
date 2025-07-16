import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { chatApi, ChatMessage } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Send, User, Bot, FileText, ExternalLink } from 'lucide-react';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: history } = useQuery({
    queryKey: ['chat-history'],
    queryFn: chatApi.history,
  });

  const sendMutation = useMutation({
    mutationFn: chatApi.send,
    onSuccess: (response) => {
      setMessages(prev => [...prev, response]);
      setInput('');
    },
  });

  useEffect(() => {
    if (history && Array.isArray(history)) {
      setMessages(history);
    }
  }, [history]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen for new chat event
  useEffect(() => {
    const handleNewChat = () => {
      setMessages([]);
      setInput('');
      inputRef.current?.focus();
    };

    window.addEventListener('new-chat', handleNewChat);
    return () => window.removeEventListener('new-chat', handleNewChat);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sendMutation.isPending) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: input,
      role: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    sendMutation.mutate(input);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-100px)]">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {!messages || messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-center">
            <div className="space-y-4">
              <div className="text-4xl">💬</div>
              <div className="text-terminal-muted">
                <div>start a conversation</div>
                <div className="text-sm mt-2">try: "what's in my calendar today?" or "&gmail recent emails"</div>
              </div>
            </div>
          </div>
        ) : (
          Array.isArray(messages) && messages.map((message) => (
            <div key={message.id} className="space-y-2">
              {/* Message header */}
              <div className="flex items-center gap-2 text-sm">
                {message.role === 'user' ? (
                  <>
                    <User className="w-4 h-4 text-terminal-green" />
                    <span className="text-terminal-green">user</span>
                  </>
                ) : (
                  <>
                    <Bot className="w-4 h-4 text-terminal-amber" />
                    <span className="text-terminal-amber">assistant</span>
                  </>
                )}
                <span className="text-terminal-muted text-xs">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </span>
              </div>

              {/* Message content */}
              <div className={`pl-6 ${
                message.role === 'user' ? 'text-terminal-fg' : 'text-terminal-muted'
              }`}>
                <div className="whitespace-pre-wrap">{message.content}</div>
                
                {/* Sources */}
                {message.sources && message.sources.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <div className="text-terminal-muted text-sm">#sources</div>
                    {message.sources.map((source, idx) => (
                      <div key={idx} className="border border-terminal-gray rounded p-3 bg-terminal-bg/20">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-4 h-4 text-terminal-green" />
                          <span className="text-terminal-fg text-sm">{source.title}</span>
                          <span className="text-terminal-muted text-xs">&{source.connector}</span>
                          <ExternalLink className="w-3 h-3 text-terminal-muted ml-auto" />
                        </div>
                        <div className="text-terminal-muted text-sm">{source.snippet}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        
        {sendMutation.isPending && (
          <div className="flex items-center gap-2 text-terminal-muted">
            <Bot className="w-4 h-4 animate-pulse" />
            <span>thinking...</span>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-terminal-gray p-6">
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="flex-1 border border-terminal-gray rounded bg-terminal-bg/20 focus-within:border-terminal-green transition-colors">
            <div className="flex items-center px-3 py-2">
              <span className="text-terminal-green text-lg mr-3">$</span>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="ask about your data..."
                className="bg-transparent border-none outline-none text-terminal-fg flex-1 font-mono placeholder:text-terminal-muted/60"
                disabled={sendMutation.isPending}
                data-search-input
              />
            </div>
          </div>
          
          <Button
            type="submit"
            disabled={!input.trim() || sendMutation.isPending}
            className="px-4"
          >
            <Send className="w-4 h-4" />
          </Button>
        </form>
        
        <div className="mt-3 text-terminal-muted text-xs">
          <span>try: </span>
          <span className="text-blue-400">&gmail</span>, 
          <span className="text-purple-400"> &cal</span>, 
          <span className="text-green-400"> &gh</span>
          <span className="ml-4">
            <span className="text-terminal-muted border border-terminal-muted px-1 py-0.5 rounded mr-1">c</span>
            new chat
          </span>
        </div>
      </div>
    </div>
  );
}