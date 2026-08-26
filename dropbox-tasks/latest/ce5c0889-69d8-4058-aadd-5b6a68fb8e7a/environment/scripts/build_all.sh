#!/bin/bash
set -euo pipefail
cat > /usr/local/bin/deskctl <<'WRAP'
#!/bin/bash
exec php /app/booth/main.php "$@"
WRAP
chmod +x /usr/local/bin/deskctl
echo "deskctl installed"
