# Frontend Implementation Plan

## Core Principles
- **Minimal Text**: Use symbols, icons, and abbreviations
- **Intuitive UI**: Visual hierarchy with clear affordances
- **Ampersand Notation**: `&gmail`, `&calendar`, `&github` for quick reference
- **Terminal Aesthetic**: Match portfolio's jet black design

## Branch Strategy
- Create new branch `frontend` from current `claude-code`
- Keep all backend code untouched
- Build React frontend in `/frontend` directory

## Directory Structure
```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/           # shadcn/ui components
│   │   ├── layout/       # TerminalLayout, Sidebar, Header
│   │   ├── chat/         # ChatInterface, MessageList
│   │   ├── connectors/   # ConnectorCard, StatusIndicator
│   │   └── common/       # CommandPalette, HotkeyIndicator
│   ├── hooks/
│   │   ├── use-hotkeys.ts
│   │   ├── use-connectors.ts
│   │   └── use-chat.ts
│   ├── lib/
│   │   ├── api.ts        # Backend API calls
│   │   └── utils.ts
│   └── pages/
│       ├── Dashboard.tsx
│       ├── Chat.tsx
│       ├── Browse.tsx
│       └── Settings.tsx
```

## Key Features

### Ampersand System
- `&gmail` → Gmail connector
- `&cal` → Calendar connector  
- `&gh` → GitHub connector
- `&sync` → Sync all
- `&search` → Global search

### Minimal UI Elements
- Status dots (🟢🟡🔴) for connector health
- Unicode symbols for file types
- Single-letter hotkeys with visual indicators
- Compact cards with essential info only

### Terminal Interface
- Command input with `$` prompt
- Autocomplete for `&` commands
- Real-time status in header
- Monospace font throughout

### Intuitive Navigation
- Visual connector grid on dashboard
- Breadcrumb navigation
- Context-aware hotkeys
- Progressive disclosure of details

## API Integration
- Connect to existing FastAPI backend
- Use React Query for caching
- WebSocket for real-time sync status
- No backend modifications needed

## Hotkey System
```
Global:
0 → Dashboard
1 → Chat  
2 → Browse
3 → Settings
/ → Search
c → New chat
r → Refresh

Context:
s → Sync current
d → Details
e → Edit config
```

## Technology Stack
- **Framework**: React + TypeScript + Vite
- **Styling**: Tailwind CSS with custom terminal theme
- **UI Components**: Radix UI primitives (shadcn/ui)
- **State Management**: React Query for server state
- **Routing**: React Router

## Design System
**Color Palette:**
- Background: Pure black (`hsl(0 0% 0%)`)
- Foreground: Light gray (`hsl(210 40% 98%)`)
- Terminal green: `hsl(142 76% 36%)`
- Muted text: `hsl(215 20.2% 65.1%)`
- Borders: Dark gray (`hsl(0 0% 15%)`)

**Typography:**
- Font: JetBrains Mono (monospace)
- Lowercase styling throughout
- Terminal-style prompts and indicators