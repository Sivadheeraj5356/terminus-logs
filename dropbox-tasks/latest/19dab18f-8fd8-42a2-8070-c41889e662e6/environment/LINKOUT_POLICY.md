# Departure-page security policy

Applies to the static page served at `/app` (root URL `/`). The page reads
two values from its own query string: `to` (the destination URL) and `label`
(the partner's display name), then offers a link out to `to`. It has no
backend; everything happens client-side in the browser, and both query
values are attacker-controlled - anyone can link a visitor to this page with
whatever `to`/`label` they want.

## Allowed destinations

Exactly two origins are real partners:

- `https://apply.riverton-partners.example`
- `https://docs.riverton-partners.example`

A destination counts as allowed only when it is one of these two origins
*exactly*. Checking whether the string of `to` merely starts with, contains,
or ends with an allowed origin is not the same thing and gets this wrong in
both directions - parse `to` as a URL and compare the parsed origin, not the
raw text.

## Page contract

- `#destination-label`: shows `Continue to {label}` when `label` is a
  non-blank value, or `Continue` when it's blank or missing.
- `#continue-link`: an anchor pointing at `to`, present in the document only
  when `to` is an allowed destination as defined above. It must never be
  present with an empty, `#`, or otherwise non-functional `href` - either
  it's a real link to `to`, or it doesn't exist in the page at all.
- `#blocked-notice`: present and visible whenever `#continue-link` is not -
  whether `to` is missing, malformed, or simply not one of the two allowed
  origins.

## Untrusted `label`

Whatever a visitor puts in `label` must render back as the exact text they
supplied inside `#destination-label`, and must never be able to execute as
script when the page renders it, no matter what markup, attributes, or event
handlers it contains.

## Opening a partner site safely

When `#continue-link` is rendered, it must open the destination in a new
browsing context (`target="_blank"`) that has no way back into this page -
the new tab's `window.opener` must be `null` (or otherwise unusable), and
this page's own document is not disclosed to the destination as the
referrer.

## Content-Security-Policy

The page must ship an HTML `Content-Security-Policy` (via a
`<meta http-equiv>` tag, since there is no application server to set
response headers) that restricts `default-src` to the page's own origin,
disallows inline and `eval`-based script execution, and sets
`frame-ancestors 'none'` so the page refuses to render inside a frame on
another site. The page must remain fully functional under this policy for a
visitor heading to a real partner destination.
