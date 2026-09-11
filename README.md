# Activity API for Teams Notifier

A microservice component that manages messages (activities) in Microsoft Teams:
- Send new messages
- Update existing messages
- Delete messages

Shares it's database with `bf-directline-endpoint`.

## Authentication

Uses one of two methods:
1. Password-based: `MICROSOFT_APP_PASSWORD`
2. Certificate-based: Both `MICROSOFT_APP_CERTIFICATE` + `MICROSOFT_APP_PRIVATEKEY`

## Configuration

Environment variables (can be set via `.env` file):

### Server Settings
- `PORT`: Server port (default: 3980)

### Microsoft App Settings
- `MICROSOFT_APP_ID`: Application ID from app registration
- `MICROSOFT_APP_TENANT_ID`: Azure AD Tenant ID
- `MICROSOFT_APP_PASSWORD`: App secret/password
- `MICROSOFT_APP_CERTIFICATE`: PEM certificate (Base64 encoded)
- `MICROSOFT_APP_PRIVATEKEY`: PEM private key (Base64 encoded)

### Database Settings
- `DATABASE_URL`: PostgreSQL connection string
  Format: `postgresql://{USER}:{PASSWORD}@{HOST}/{DATABASE}`

## API Documentation

Interactive documentation available at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc UI

### Post a message

### Send Messages

All POST routes require a `conversation_token` (obtained from MS Teams bot interaction) and returns a `message_id`:
```json
{
  "message_id": "uuid"
}
```

The server generates a v7 UUID unless the caller supplied its own id (see below), in which case the
answer echoes that one back.

#### Message options

1. **Text Message** `POST /api/v1/message/text`
```json
{
    "conversation_token": "conversation_token (uuid)",
    "text": "Your message content"
}
```

2. Simple Message `POST /api/v1/message/simple`
```json
{
    "conversation_token": "conversation_token (uuid)",
    "text": "Your message content",
    "title": "Message title",
    "title_color": "default" // Options: dark, light, accent, good, warning, attention
}
```

3. Simple Message `POST /api/v1/message/card`
```json
{
    "conversation_token": "conversation_token (uuid)",
    "card": {}, // Teams Adaptive Card object
    "summary": "Notification summary"
}
```

4. A generic one that can take any of the previous payload `POST /api/v1/message`
```json
{
    "conversation_token": "conversation_token (uuid)",
    [... one of the previous payload...]
}
```

#### Caller-chosen `message_id`

`POST /api/v1/message` also accepts an optional `message_id`, which **must be a random UUID**:

```json
{
    "conversation_token": "conversation_token (uuid)",
    "message_id": "random uuid",
    [... one of the previous payload...]
}
```

A caller that writes the id down before sending keeps a usable handle even when it never sees the
answer, so a timed out call no longer strands a message it can neither update nor delete.

Replaying the same `message_id` returns `200` with that id and sends nothing. Replaying one that
belongs to another conversation returns `409`: an id may only be reused inside the conversation
that owns it, otherwise a caller could squat an id and have it handed to someone else. Replaying
the id of a deleted message returns `410`, since the handle it would give back is already spent.

Concurrent replays of one id are serialised, so only one of them reaches Teams.

### Update a message

To update a message, send a `PATCH /api/v1/message` with one of the previous payload (not necessarily of the same kind), without the `conversation_token` but the provided `message_id`.

### Delete a message

Just send a `DELETE /api/v1/message` without the `conversation_token` but the provided `message_id`.
