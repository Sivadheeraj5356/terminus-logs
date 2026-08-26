# Non-interactive bash sources BASH_ENV before the script body.
# Recover /app when a runner starts at the filesystem root.
if [ "${PWD:-/}" = "/" ] && [ -d /app ]; then
  cd /app || true
fi
