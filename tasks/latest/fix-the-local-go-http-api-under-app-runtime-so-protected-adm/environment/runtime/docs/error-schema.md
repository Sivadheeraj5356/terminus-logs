# Error Schema

All API errors are returned as:

{
  "error": {
    "code": "<machine_code>",
    "message": "<human_message>"
  }
}

Known error codes used by the service:
- unauthorized
- not_found
- method_not_allowed
