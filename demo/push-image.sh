#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

repository="$(terraform -chdir=infra/terraform/cluster output -raw mcp_image_repository)"
tag="${1:-demo}"
registry="${repository%%/*}"

aws ecr get-login-password \
  --region "$(terraform -chdir=infra/terraform/cluster output -raw aws_region)" \
  | docker login --username AWS --password-stdin "$registry"

docker buildx build \
  --platform linux/amd64 \
  --push \
  --tag "${repository}:${tag}" \
  src/mcp_server

echo "Pushed ${repository}:${tag}"
