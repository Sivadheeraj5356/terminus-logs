# STH consistency

The signed tree head timestamp must be on or after the matching CT inclusion entry timestamp.

When sth.timestamp is strictly before entry.timestamp the row is stale_sth rejected.
