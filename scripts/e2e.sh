#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost:8080/api}

REGISTER=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"email":"qa@viewdezider.local","password":"password","role":"ADMIN"}')

TOKEN=$(echo "$REGISTER" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "Failed to get token"
  exit 1
fi

curl -s -X POST "$BASE_URL/projects/1/compute" \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null

curl -s "$BASE_URL/projects/1/export" \
  -H "Authorization: Bearer $TOKEN" \
  -o /dev/null

echo "E2E happy path completed."
