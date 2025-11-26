#!/bin/bash
set -e

# 1.2 Harden Entrypoint Against TOCTOU
# Verify /workspace is mounted read-only
if ! grep -qE "[[:space:]]/workspace[[:space:]].*ro[[:space:],]" /proc/mounts; then
    echo "ERR: /workspace not mounted read-only"
    exit 125
fi

# Purge output symlinks before execution
# This prevents path-escape via output symlinks
find /output -type l -delete 2>/dev/null || exit 126

# Execute the passed command
exec "$@"
