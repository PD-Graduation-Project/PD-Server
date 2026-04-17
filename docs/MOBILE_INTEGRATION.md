# Mobile App Integration Guide

This document describes how the mobile app should integrate with the PD-Server real-time notification system.

## Overview

The system provides two notification mechanisms:

1. **Server-Sent Events (SSE)** - For real-time updates while the app is in foreground
2. **Expo Push Notifications** - For notifications when the app is backgrounded or closed

---

## 1. Push Token Registration

### When to Register
- On app startup (after user logs in)
- When user enables notifications in settings

### Endpoint

```
POST /api/user/push-token
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "push_token": "ExponentPushToken[xxxxxxxxxxxxxx]"
}
```

### Response

```json
{
  "success": true
}
```

### Error Responses

| Status | Description |
|--------|-------------|
| 400 | `push_token` is missing or not a string |
| 401 | Invalid or expired access token |
| 404 | User not found |

### Notes
- A user can have multiple push tokens (e.g., multiple devices)
- Duplicate tokens are ignored (won't cause errors)
- Store the token locally after successful registration

---

## 2. Push Token Removal

### When to Remove
- When user logs out
- When user disables notifications in settings
- When the token is no longer valid (Expo returns an error)

### Endpoint

```
DELETE /api/user/push-token
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "push_token": "ExponentPushToken[xxxxxxxxxxxxxx]"
}
```

### Response

```json
{
  "success": true
}
```

### Notes
- If the token doesn't exist, the request still returns success
- If all tokens are removed, `push_token` field becomes `null`

---

## 3. SSE Connection

### When to Connect
- When user starts a tremor test (or any test that uses ESP32)
- Keep connection open while test is in progress

### Endpoint

```
GET /api/stream
Authorization: Bearer <access_token>
Accept: text/event-stream
```

### Response Headers

```
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache, no-transform
Connection: keep-alive
```

### Event Format

```
event: <event_name>
data: <json_data>

```

(Note the double newline after each event)

---

## 4. SSE Events

### 4.1 `connected`

Sent immediately when the SSE connection is established.

```
event: connected
data: {"user_id": 123}

```

**Usage:** Confirm connection is ready.

---

### 4.2 `device_connected`

Sent when the ESP32 device connects to the server.

```
event: device_connected
data: {"device_id": "ESP32-001234"}

```

**Usage:** Show "Sensor connected" or "Ready to start" message.

**Trigger:** ESP32 calls the heartbeat endpoint after pairing.

---

### 4.3 `device_disconnected`

Sent when the ESP32 device disconnects (timeout or explicit disconnect).

```
event: device_disconnected
data: {"device_id": "ESP32-001234"}

```

**Usage:** Show "Sensor disconnected" warning. May indicate battery issue or WiFi problem.

---

### 4.4 `next_subtest`

Sent after each tremor subtest data is uploaded.

```
event: next_subtest
data: {
  "test_id": 1,
  "uploaded_subtest": "0",
  "next_enabled_subtests": ["1", "2", "3"],
  "completed_subtests": ["0"]
}

```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `test_id` | int | The test session ID |
| `uploaded_subtest` | string | The subtest that was just uploaded (e.g., "0") |
| `next_enabled_subtests` | string[] | Next pending subtests (up to 5) |
| `completed_subtests` | string[] | All completed subtests so far |

**Usage:** 
- Update progress indicator
- Prompt user for next subtest
- Show "X of Y subtests completed"

**Trigger:** ESP32 uploads gyro data via `POST /api/tests/{test_id}/tremor`

---

### 4.5 `heartbeat`

Sent every 15 seconds to keep the connection alive.

```
event: heartbeat
data: {"timestamp": "2026-04-15T10:30:00.123456"}

```

**Usage:** Can be ignored, or used to verify connection health.

---

## 5. Heartbeat Endpoint

### When to Call
- Every 30 seconds while SSE is connected (optional but recommended)
- This refreshes the connection TTL in Redis (default TTL is 60 seconds)

### Endpoint

```
POST /api/stream/heartbeat
Authorization: Bearer <access_token>
```

### Response

```json
{
  "success": true
}
```

---

## 6. Push Notification (ML Score Ready)

### When Sent
When ML inference completes for a test. The app can be in any state (foreground, background, or terminated).

### Payload Structure

```json
{
  "to": "ExponentPushToken[xxxxxxxxxxxxxx]",
  "title": "Tremor Test Complete",
  "body": "Your tremor test results are ready",
  "data": {
    "type": "ml_score_ready",
    "test_id": 123,
    "test_type": "tremor",
    "ml_score": 0.75
  },
  "sound": "default"
}
```

### Handling in App

```javascript
// Example using expo-notifications
Notifications.addNotificationReceivedListener(notification => {
  const data = notification.request.content.data;
  
  if (data.type === 'ml_score_ready') {
    // Navigate to results screen
    navigation.navigate('TestResults', {
      testId: data.test_id,
      mlScore: data.ml_score
    });
  }
});

// For background/quit state
Notifications.addNotificationResponseReceivedListener(response => {
  const data = response.notification.request.content.data;
  
  if (data.type === 'ml_score_ready') {
    // User tapped the notification
    navigation.navigate('TestResults', {
      testId: data.test_id,
      mlScore: data.ml_score
    });
  }
});
```

---

## 7. Complete Test Flow Example

### Step-by-Step

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE APP                          SERVER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ 1. User logs in                                                              │
│    ───────────────────────────────► POST /api/auth/login                    │
│    ◄───────────────────────────────  {access_token, refresh_token}          │
│                                                                              │
│ 2. Register push token                                                       │
│    ───────────────────────────────► POST /api/user/push-token               │
│    ◄───────────────────────────────  {success: true}                        │
│                                                                              │
│ 3. User starts tremor test                                                   │
│    ───────────────────────────────► POST /api/tests                         │
│    ◄───────────────────────────────  {test_id: 1, status: "pending"}        │
│                                                                              │
│ 4. Open SSE connection                                                       │
│    ───────────────────────────────► GET /api/stream                         │
│    ◄───────────────────────────────  event: connected                       │
│                                                                              │
│ 5. ESP32 connects                                                            │
│                                    ◄── ESP32 heartbeat ──                    │
│    ◄───────────────────────────────  event: device_connected                │
│    [Show: "Sensor connected"]                                                │
│                                                                              │
│ 6. User performs subtest 0                                                   │
│                                    ─── ESP32 uploads data ──►               │
│    ◄───────────────────────────────  event: next_subtest                    │
│    [Update UI: "1 of 11 completed, next: subtest 1"]                        │
│                                                                              │
│ 7. ... repeat for all subtests ...                                          │
│                                                                              │
│ 8. User completes test                                                        │
│    ───────────────────────────────► POST /api/tests/1/complete              │
│    ◄───────────────────────────────  {status: "completed", ml_status:       │
│                                      "processing"}                          │
│                                                                              │
│ 9. Close SSE connection (optional, can stay open)                           │
│    ───────────────────────────────X  [disconnect]                           │
│                                                                              │
│ 10. ML processing completes (async)                                          │
│    ◄───────────────────────────────  PUSH NOTIFICATION                      │
│    [User taps notification]                                                  │
│    ───────────────────────────────► GET /api/tests/1                        │
│    ◄───────────────────────────────  {ml_score: 0.75, ...}                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Error Handling

### SSE Connection Errors

| Scenario | Action |
|----------|--------|
| Connection fails | Retry with exponential backoff (max 3 retries) |
| Connection drops | Reconnect automatically |
| Auth error (401) | Prompt user to log in again |
| Server error (5xx) | Fall back to polling |

### Push Token Errors

| Scenario | Action |
|----------|--------|
| Registration fails (4xx) | Check error message, fix payload |
| Registration fails (5xx) | Retry on next app launch |
| Push not received | Ensure token is valid, check Expo dashboard |

---

## 9. Fallback: Polling

If SSE is unavailable, the app can poll the test endpoint:

```
GET /api/tests/{test_id}
Authorization: Bearer <access_token>
```

Response includes:
```json
{
  "id": 1,
  "status": "completed",
  "ml_status": "completed",
  "ml_score": 0.75,
  "config": {"0": true, "1": true, ...}
}
```

Poll every 5-10 seconds while test is in progress.

---

## 10. Implementation Checklist

### Required

- [ ] Register push token on login
- [ ] Remove push token on logout
- [ ] Open SSE connection when test starts
- [ ] Handle `next_subtest` event (update progress UI)
- [ ] Handle push notification (navigate to results)

### Recommended

- [ ] Handle `device_connected` event (show sensor status)
- [ ] Handle `device_disconnected` event (show warning)
- [ ] Send heartbeat every 30 seconds
- [ ] Implement reconnection logic for dropped SSE
- [ ] Implement polling fallback

### Optional

- [ ] Handle `connected` event (log for debugging)
- [ ] Ignore `heartbeat` events
- [ ] Cache push token locally for re-registration

---

## 11. Testing

### Manual Testing Steps

1. **Push Token Registration**
   ```bash
   curl -X POST https://your-server.com/api/user/push-token \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"push_token": "ExponentPushToken[test]"}'
   ```

2. **SSE Connection**
   ```bash
   curl -N https://your-server.com/api/stream \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Accept: text/event-stream"
   ```

3. **Verify Events**
   - Connect ESP32 device → should see `device_connected`
   - Upload tremor data → should see `next_subtest`
   - Disconnect ESP32 → should see `device_disconnected`

---

## 12. Server Configuration

The server requires these environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `EXPO_ACCESS_TOKEN` | Yes | Expo push notification access token |
| `REDIS_URL` | Yes | Redis connection URL for pub/sub |
| `DATABASE_URL` | Yes | PostgreSQL connection URL |

Get `EXPO_ACCESS_TOKEN` from: https://expo.dev/accounts/[account]/settings/access-tokens

---

## 13. Troubleshooting

### SSE not receiving events

1. Check Authorization header is valid
2. Verify `Accept: text/event-stream` header
3. Check server logs for connection errors
4. Verify Redis is running and accessible

### Push notifications not received

1. Verify `EXPO_ACCESS_TOKEN` is configured on server
2. Check push token is registered (GET /api/user)
3. Verify token format: `ExponentPushToken[xxxxxxx]`
4. Check Expo push receipt for errors

### Events delayed or missing

1. Check network connectivity
2. Verify heartbeat is being sent
3. Check Redis connection is stable
4. Review server logs for publish errors
