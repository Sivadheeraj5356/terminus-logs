# API Reference

This document describes the public API.

## Endpoints

### GET /api/v1/status

Returns the service health status as JSON.

```json
{
  "status": "healthy",
  "version": "0.4.2"
}
```

### POST /api/v1/convert

Accepts a Markdown body and returns HTML.

**Request headers:**

- `Content-Type: text/markdown`
- `Accept: text/html`

**Example using curl:**

```bash
curl -X POST https://example.com/api/v1/convert \
  -H "Content-Type: text/markdown" \
  -d "# Hello World"
```

## [Authentication](https://example.com/auth-info)

All endpoints require an API key. Pass it via the `Authorization` header:

~~~
Authorization: Bearer YOUR_API_KEY
~~~

See [authentication docs](https://example.com/auth) for key management.

## Rate Limiting

The API enforces a rate limit of *100 requests per minute* per API key.
Exceeding this limit returns a `429 Too Many Requests` response.

### Retry Strategy

Use exponential backoff with a base delay of 1 second:

- First retry: 1s
- Second retry: 2s
- Third retry: 4s

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad request |
| 401 | Unauthorized |
| 429 | Rate limited |
| 500 | Server error |

## SDK

Download the SDK from [our GitHub](https://github.com/example/sdk).
