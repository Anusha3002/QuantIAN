#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LIVE_DIR="$ROOT_DIR/dist/live"

KEEP_STORAGE=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --keep-storage) KEEP_STORAGE=1 ;;
    --yes|-y)       ASSUME_YES=1 ;;
    -h|--help)
      cat <<USAGE
Usage: scripts/teardown_cloud.sh [--keep-storage] [--yes]

  --keep-storage  skip deletion of ECR repos, AR repo, IAM role
                  (compute resources are still deleted)
  --yes           skip the interactive confirmation prompt

Reads endpoints/ARNs from dist/live/{aws,azure,gcp}.json and deletes:
  - AWS App Runner services for registry + ingestion
  - GCP Cloud Run service
  - Azure resource group (which transitively deletes Container Apps,
    ACR, storage account, environment)

By default also deletes:
  - AWS ECR repos
  - AWS IAM role for App Runner
  - GCP Artifact Registry repo
  (pass --keep-storage to skip these)
USAGE
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

confirm() {
  if [[ $ASSUME_YES -eq 1 ]]; then return 0; fi
  read -r -p "Continue? [y/N] " reply
  [[ "$reply" =~ ^[Yy] ]]
}

read_json() {
  local file="$1"
  local query="$2"
  if [[ ! -f "$file" ]]; then return 1; fi
  jq -r "$query // empty" "$file"
}

teardown_aws() {
  local manifest="$LIVE_DIR/aws.json"
  if [[ ! -f "$manifest" ]]; then
    echo "[aws] no manifest at $manifest, skipping"
    return 0
  fi

  local region registry_arn ingestion_arn
  region=$(read_json "$manifest" '.region') || true
  registry_arn=$(read_json "$manifest" '.registry.service_arn') || true
  ingestion_arn=$(read_json "$manifest" '.ingestion.service_arn') || true
  region=${region:-us-east-1}

  if [[ -n "$registry_arn" ]]; then
    echo "[aws] deleting App Runner service: registry"
    aws apprunner delete-service --region "$region" --service-arn "$registry_arn" >/dev/null \
      || echo "[aws] registry delete failed (may already be gone)"
  fi
  if [[ -n "$ingestion_arn" ]]; then
    echo "[aws] deleting App Runner service: ingestion"
    aws apprunner delete-service --region "$region" --service-arn "$ingestion_arn" >/dev/null \
      || echo "[aws] ingestion delete failed (may already be gone)"
  fi

  if [[ $KEEP_STORAGE -eq 1 ]]; then
    echo "[aws] keeping ECR repos + IAM role (per --keep-storage)"
    return 0
  fi

  local registry_repo ingestion_repo
  registry_repo=$(read_json "$manifest" '.registry.ecr_repository') || true
  ingestion_repo=$(read_json "$manifest" '.ingestion.ecr_repository') || true
  if [[ -n "$registry_repo" ]]; then
    echo "[aws] deleting ECR repo: $registry_repo"
    aws ecr delete-repository --region "$region" --repository-name "$registry_repo" --force >/dev/null \
      || echo "[aws] ECR $registry_repo delete failed"
  fi
  if [[ -n "$ingestion_repo" ]]; then
    echo "[aws] deleting ECR repo: $ingestion_repo"
    aws ecr delete-repository --region "$region" --repository-name "$ingestion_repo" --force >/dev/null \
      || echo "[aws] ECR $ingestion_repo delete failed"
  fi

  echo "[aws] detaching + deleting IAM role: QuantIANAppRunnerECRAccessRole"
  aws iam detach-role-policy \
    --role-name QuantIANAppRunnerECRAccessRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess \
    >/dev/null 2>&1 || true
  aws iam delete-role --role-name QuantIANAppRunnerECRAccessRole >/dev/null 2>&1 \
    || echo "[aws] IAM role delete failed (may already be gone)"
}

teardown_gcp() {
  local manifest="$LIVE_DIR/gcp.json"
  if [[ ! -f "$manifest" ]]; then
    echo "[gcp] no manifest at $manifest, skipping"
    return 0
  fi

  local project region service_name repository
  project=$(read_json "$manifest" '.project') || true
  region=$(read_json "$manifest" '.region') || true
  service_name=$(read_json "$manifest" '.service_name') || true
  repository=$(read_json "$manifest" '.repository') || true
  region=${region:-us-central1}

  if [[ -n "$project" && -n "$service_name" ]]; then
    echo "[gcp] deleting Cloud Run service: $service_name"
    gcloud run services delete "$service_name" \
      --project "$project" --region "$region" --quiet >/dev/null \
      || echo "[gcp] Cloud Run delete failed (may already be gone)"
  fi

  if [[ $KEEP_STORAGE -eq 1 ]]; then
    echo "[gcp] keeping Artifact Registry repo (per --keep-storage)"
    return 0
  fi

  if [[ -n "$project" && -n "$repository" ]]; then
    echo "[gcp] deleting Artifact Registry repo: $repository"
    gcloud artifacts repositories delete "$repository" \
      --project "$project" --location "$region" --quiet >/dev/null \
      || echo "[gcp] AR delete failed (may already be gone)"
  fi
}

teardown_azure() {
  local manifest="$LIVE_DIR/azure.json"
  if [[ ! -f "$manifest" ]]; then
    echo "[azure] no manifest at $manifest, skipping"
    return 0
  fi

  local resource_group
  resource_group=$(read_json "$manifest" '.resource_group') || true
  if [[ -z "$resource_group" ]]; then
    echo "[azure] no resource_group in manifest, skipping"
    return 0
  fi

  echo "[azure] deleting resource group: $resource_group (async, takes 5-15 min)"
  az group delete --name "$resource_group" --yes --no-wait \
    || echo "[azure] resource group delete failed (may already be gone)"
}

echo "About to delete:"
echo "  - AWS App Runner services + ECR repos + IAM role (region from aws.json)"
echo "  - GCP Cloud Run service + Artifact Registry repo (project from gcp.json)"
echo "  - Azure resource group (everything in it: container apps, ACR, blob storage)"
if [[ $KEEP_STORAGE -eq 1 ]]; then
  echo "  (--keep-storage: skipping ECR/AR/IAM)"
fi
echo
if ! confirm; then
  echo "aborted"
  exit 1
fi

teardown_aws
teardown_gcp
teardown_azure

echo
echo "Teardown requested. Verify with:"
echo "  aws apprunner list-services --region us-east-1 --output json | jq '.ServiceSummaryList | length'"
echo "  gcloud run services list --region us-central1 --format='value(SERVICE)' | wc -l"
echo "  az group exists --name <resource-group>"
