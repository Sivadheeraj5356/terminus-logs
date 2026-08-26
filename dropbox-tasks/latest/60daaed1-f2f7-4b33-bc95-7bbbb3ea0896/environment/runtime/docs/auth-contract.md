# Auth Contract

Authorization header format:
- Authorization: Bearer <token>

Invalid or missing token for protected routes:
- Status: 401
- Body: {"error":{"code":"unauthorized","message":"missing or invalid bearer token"}}
