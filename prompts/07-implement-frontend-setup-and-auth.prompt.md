---
mode: agent
description: "Phase 1B: React + Vite + Router setup, SSO login, i18n, layout shell"
---

# Task: Frontend Setup & Auth

## Context

Set up the `frontend/` directory with React + TypeScript + Vite + React Router. Implement SSO login flow and app shell with i18n support.

### Tech Stack

- React 18+ with TypeScript
- Vite for bundling
- React Router for routing
- **yarn** for package management
- i18n library (react-i18next)

### Project Structure

```
frontend/
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx
    routes/
    components/
      layout/
        AppShell.tsx
        Sidebar.tsx
        Header.tsx
    hooks/
    api/
      client.ts       # axios/fetch wrapper with auth headers
    i18n/
      en.json
      ja.json
      zh.json
      ko.json
    stores/            # state management (zustand or context)
    types/
```

### Auth Flow (Frontend)

1. Unauthenticated user → redirect to `/login`.
2. `/login` page has "Sign in with Microsoft" button → calls `GET /api/v1/auth/login`.
3. After OIDC redirect, backend issues session token → frontend stores it.
4. API client attaches token to all requests.
5. If `/me` returns `lobby: true` → show onboarding page ("Request to join a team").

### Routing

- `/login` — public, SSO login
- `/onboarding` — lobby state, team join request
- `/` — member dashboard (redirect to login if unauthenticated)
- `/daily/:date?` — daily form
- `/team` — leader dashboard (only for leaders)
- `/admin` — admin panel (only for admins)
- `/settings` — user preferences

### i18n

- 4 locales: en (default), ja, zh, ko
- UI language based on user preference (`preferred_locale`)
- Skeleton translation files — full translations later

### Layout Shell

- Responsive sidebar (collapsible on mobile)
- Header with user info, notification bell placeholder, locale switcher
- Protected route wrapper: checks auth + lobby state

## Acceptance Criteria

- [ ] `yarn create vite` project with TypeScript template
- [ ] React Router with all routes listed above
- [ ] Auth context/store: login, logout, token storage, `/me` fetch on app load
- [ ] Protected route component: redirects to login if unauthenticated, to onboarding if lobby
- [ ] SSO login button triggers OIDC flow
- [ ] API client with auth header injection and 401 redirect
- [ ] i18n setup with 4 locale files (skeleton keys)
- [ ] Responsive app shell (sidebar + header + main content area)
- [ ] Onboarding page with team list and "Request to Join" button
- [ ] Vite proxy config for backend API during development

## Constraints

- Use yarn (not npm, pnpm).
- UI default language: English. User can switch locale.
- Mobile-first responsive design.

## Out of Scope

- Daily form components (next task)
- Dashboard components (tasks 09, 10)
- Actual translations beyond skeleton keys
