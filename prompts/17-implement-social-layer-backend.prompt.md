---
mode: agent
description: "Phase 3A: Comments, emoji reactions, moderation, WebSocket, cross-team feed"
---

# Task: Social Layer Backend

## Context

Comments and reactions on daily records. Real-time updates via WebSocket. Cross-team activity feed. Rate limiting and moderation.

### New Tables

```
comments:
  id UUID PK
  daily_record_id FK
  parent_comment_id FK (nullable, for threads)
  author_id FK
  body TEXT
  created_at
  updated_at

reactions:
  id UUID PK
  daily_record_id FK
  user_id FK
  emoji VARCHAR(32)  -- Unicode emoji
  created_at
  UNIQUE(daily_record_id, user_id, emoji)  -- same user, same emoji, same record = toggle
```

### Comment Endpoints

- `POST /api/v1/daily-records/{id}/comments` — add comment (or reply if parent_comment_id set)
- `GET /api/v1/daily-records/{id}/comments` — list threaded comments
- `PUT /api/v1/comments/{id}` — edit own comment only (author check)
- `DELETE /api/v1/comments/{id}` — delete:
  - Author: can delete own
  - Admin: can delete any
  - Leader: can delete comments on own team's records only (check record.user_id is in leader's team)
  - Anyone else: 403

### Reaction Endpoints

- `POST /api/v1/daily-records/{id}/reactions` — add reaction (emoji)
  - If `(record_id, user_id, emoji)` already exists → remove it (toggle)
  - Rate limit: 30 reactions/min per user. Return 429 if exceeded.
- `GET /api/v1/daily-records/{id}/reactions` — list reactions grouped by emoji with counts and user list
- `DELETE /api/v1/daily-records/{id}/reactions/{emoji}` — explicit remove

### Activity Feed

`GET /api/v1/feed?scope=team|all&page=&page_size=`
- `scope=team` (default): records from user's current team.
- `scope=all`: records from all teams.
- Returns daily records with public fields only (visibility filter applied).
- Sorted by `record_date DESC, created_at DESC`.
- Includes: comment count, reaction summary per record.
- Paginated.

### WebSocket

`WS /api/v1/ws`
- After connection: client sends auth token. Server validates, subscribes to relevant channels.
- Channels:
  - `team:{team_id}` — records, comments, reactions for team's records
  - `all` — all public events (for activity feed with scope=all)
- Events broadcast:
  - `record.created`, `record.updated`
  - `comment.created`, `comment.updated`, `comment.deleted`
  - `reaction.added`, `reaction.removed`
- **Visibility**: all WS payloads pass through the same visibility filter as REST. Private fields stripped for non-privileged subscribers.
- Connection management: heartbeat, reconnection guidance, auth expiry handling.

### Notification Integration

- On comment created → trigger `social_reaction` notification for record owner (batched).
- On reaction added → trigger `social_reaction` notification for record owner (batched).
- Use NotificationService from task 13.

### Moderation

- Leader delete scoped to own team's records. Check: is `daily_record.user_id` in leader's active team?
- Admin delete: no scope restriction.
- Deleted comments: soft-delete (set body to "[deleted]", keep record for thread integrity) or hard-delete with cascade.

## Acceptance Criteria

- [ ] Comment CRUD with threading (parent_comment_id)
- [ ] Comment edit: author only. Delete: author, admin, or leader (scoped)
- [ ] Reaction toggle: add/remove on repeat
- [ ] Rate limit: 30 reactions/min per user
- [ ] Activity feed with team/all scope, paginated
- [ ] Feed applies visibility filter (public fields only for non-privileged)
- [ ] WebSocket: auth, subscribe, broadcast events
- [ ] WS payloads use same visibility filter as REST
- [ ] Notification triggers for comments and reactions (batched)
- [ ] Moderation: leader delete scoped to own team
- [ ] Alembic migration for new tables
- [ ] Tests: CRUD, threading, moderation scope, rate limit, visibility, feed pagination

## Constraints

- WebSocket MUST reuse REST visibility filter — do not implement separate logic.
- Emoji rate limit: 30/min. Duplicate = toggle off (not error).
- Leader moderation: own team's records only.
- Author can edit own comments. No one else can edit another's comment.

## Out of Scope

- Frontend for social features (Phase 3B)
- MS Teams notifications (stub channel exists from task 13)
