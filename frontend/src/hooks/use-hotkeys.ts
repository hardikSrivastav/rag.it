import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export const useHotkeys = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // Only trigger if no input elements are focused
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (event.key) {
        case '0':
          navigate('/');
          break;
        case '1':
          navigate('/chat');
          break;
        case '2':
          navigate('/browse');
          break;
        case '3':
          navigate('/settings');
          break;
        case '/':
          event.preventDefault();
          // Focus search input
          const searchInput = document.querySelector('[data-search-input]') as HTMLInputElement;
          if (searchInput) {
            searchInput.focus();
          }
          break;
        case 'c':
          if (window.location.pathname === '/chat') {
            // Clear chat or start new conversation
            window.dispatchEvent(new CustomEvent('new-chat'));
          }
          break;
        case 'r':
          // Refresh/sync
          window.dispatchEvent(new CustomEvent('refresh-data'));
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [navigate]);
};