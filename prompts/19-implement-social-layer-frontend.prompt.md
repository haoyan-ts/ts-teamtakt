---
mode: agent
description: "Phase 3B: Activity feed, comments, reactions, real-time WebSocket UI"
---

# Task: Social Layer Frontend

## Context

Frontend for the social layer: activity feed, comments, emoji reactions, and real-time WebSocket updates.

### Activity Feed (`/feed`)

- Default view: own team's records. Toggle button: "My Team" / "All Teams".
- Each feed card:
  - Header: author name, avatar placeholder, date, team name
  - Body: task list (public fields: task, project, category, effort, status, tags)
  - day_note (public)
  - Blocker type badges (public, no blocker_text)
  - Footer: reaction summary (emoji × count), comment count
  - Click → expand to full record detail with comments
- Infinite scroll or paginated "Load more".
- Real-time: new records appear at top with subtle animation.

### Comments (expanded record view)

- Threaded display (like GitHub PR comments):
  - Top-level comments sorted by date.
  - Replies indented under parent.
- Comment input: textarea + submit button.
  - Reply button on each comment → reply textarea appears.
- Edit: inline edit mode (pencil icon, author only).
- Delete: trash icon:
  - Visible to: author (own comment), leader (comments on own team's records), admin (any).
  - Confirmation dialog before delete.
- Real-time: new comments appear without refresh.

### Emoji Reactions (on each record card)

- Quick-reaction bar: preset emojis (👍 🎉 💪 🤔 ❤️) always visible under each record.
- Click preset → toggle reaction (add if not reacted, remove if already reacted).
- "+" button → opens full emoji picker (searchable).
- Display: emoji badges with count. Hover → show who reacted.
- Own reactions highlighted.
- Real-time: reaction counts update live.

### WebSocket Integration

- Connect on app mount (after auth): `WS /api/v1/ws` with auth token.
- Subscribe to team channel by default. If feed scope=all, subscribe to all channel.
- Handle events:
  - `record.created` / `record.updated` → update feed
  - `comment.created` / `comment.updated` / `comment.deleted` → update comment threads
  - `reaction.added` / `reaction.removed` → update reaction counts
- Reconnection: on disconnect, auto-retry with exponential backoff.
- Show connection status indicator (optional).

### Notification Badge Update

- WebSocket events also update the notification unread count in the header bell.

## Acceptance Criteria

- [ ] Activity feed with team/all toggle
- [ ] Feed cards with public fields, reaction summary, comment count
- [ ] Infinite scroll / load more pagination
- [ ] Expanded record view with threaded comments
- [ ] Comment CRUD: post, reply, edit (author), delete (author/leader/admin)
- [ ] Quick-reaction bar with preset emojis
- [ ] Full emoji picker behind "+" button
- [ ] Reaction toggle (add/remove) with optimistic UI update
- [ ] Reaction badges with count and hover user list
- [ ] WebSocket connection with auth
- [ ] Real-time: new records, comments, reactions update live
- [ ] Reconnection with exponential backoff
- [ ] Responsive layout (mobile: full-width cards, stacked)

## Constraints

- Feed shows public fields ONLY. No day_load, no blocker_text.
- Reaction rate limit handled by backend (429). Frontend: disable button briefly on 429.
- Leader can only delete comments on own team's records — check on render (or rely on API 403).
- WebSocket reuses REST visibility — no extra client-side filtering needed.

## Out of Scope

- Notification preferences UI (already in task 16)
- MS Teams integration
- Moderation log / audit trail UI
