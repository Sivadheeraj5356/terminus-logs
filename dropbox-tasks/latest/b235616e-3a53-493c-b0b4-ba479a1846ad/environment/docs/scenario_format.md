# Lockout attack scenario format

Scenario files configure PAM faillock authentication attacks for
`bayctl setup --scenario <path>`.

Required fields:

| Field | Type | Meaning |
|-------|------|---------|
| `principal` | string | Account name under lockout attack |
| `password` | string | Correct password for successful authentication |
| `bad_rounds` | integer | Optional seeded failed-login count hint |

Example:

```json
{
  "principal": "operator-a",
  "password": "s3cret!",
  "bad_rounds": 3
}
```

Additional principals and passwords may appear in dynamic scenario files at
runtime.
