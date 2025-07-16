import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { chatApi, ChatMessage } from '@/lib/api';
import { useToast } from './use-toast';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: history } = useQuery({
    queryKey: ['chat-history'],
    queryFn: chatApi.history,
  });

  useEffect(() => {
    if (history) {
      setMessages(history);
    }
  }, [history]);

  const sendMutation = useMutation({
    mutationFn: chatApi.send,
    onSuccess: (response) => {
      setMessages(prev => [...prev, response]);
      queryClient.invalidateQueries({ queryKey: ['chat-history'] });
    },
    onError: (error) => {
      toast({
        title: 'Message failed',
        description: String(error),
        variant: 'destructive',
      });
    }
  });

  const sendMessage = (content: string) => {
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    sendMutation.mutate(content);
  };

  const clearChat = () => {
    setMessages([]);
  };

  return {
    messages,
    sendMessage,
    clearChat,
    isLoading: sendMutation.isPending,
  };
}