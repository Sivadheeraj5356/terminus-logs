#!/bin/bash
set -euo pipefail

# Oracle solution: static HTML/CSS/JS departure page satisfying
# /app/LINKOUT_POLICY.md. No backend, no build step, no external requests.

mkdir -p /app

cat > /app/index.html << 'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'">
<title>Continue</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<main id="main">
  <h1 id="destination-label"></h1>
</main>
<script src="app.js"></script>
</body>
</html>
HTML

cat > /app/style.css << 'CSS'
body { font-family: sans-serif; max-width: 32rem; margin: 3rem auto; text-align: center; }
#continue-link { display: inline-block; margin-top: 1rem; padding: 0.6rem 1.2rem; border: 1px solid #333; border-radius: 0.3rem; text-decoration: none; }
#blocked-notice { color: #a33; }
CSS

cat > /app/app.js << 'JS'
(function () {
  "use strict";

  const ALLOWED_ORIGINS = [
    "https://apply.riverton-partners.example",
    "https://docs.riverton-partners.example",
  ];

  function safeDestination(raw) {
    if (!raw) {
      return null;
    }
    let url;
    try {
      url = new URL(raw);
    } catch (err) {
      return null;
    }
    if (url.protocol !== "https:" && url.protocol !== "http:") {
      return null;
    }
    return ALLOWED_ORIGINS.includes(url.origin) ? url.href : null;
  }

  function init() {
    const params = new URLSearchParams(window.location.search);
    const rawTo = params.get("to") || "";
    const rawLabel = params.get("label") || "";

    const labelEl = document.getElementById("destination-label");
    labelEl.textContent = rawLabel.trim() === "" ? "Continue" : "Continue to " + rawLabel;

    const main = document.getElementById("main");
    const safeUrl = safeDestination(rawTo);

    if (safeUrl) {
      const link = document.createElement("a");
      link.id = "continue-link";
      link.href = safeUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "Continue";
      main.appendChild(link);
    } else {
      const notice = document.createElement("p");
      notice.id = "blocked-notice";
      notice.textContent = "This destination could not be verified as a known partner.";
      main.appendChild(notice);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
JS
