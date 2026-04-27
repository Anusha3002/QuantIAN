# QuantIAN Deployment Notes

This deployment path uses AWS and GCP VMs plus an Azure Container Apps deployment for the anomaly peer.

Role split:

- AWS VM: registry, ingestion, dashboard
- Azure Container Apps: anomaly peer
- Azure Blob Storage: durable anomaly alerts and history
- GCP VM: risk peer

Expected public ports:

- AWS: `8000`, `8001`, `8501`
- Azure: HTTPS Container Apps endpoint
- GCP: `8003`

Bootstrap entrypoint:

- `infra/vm/bootstrap_quantian_host.sh`

Packaging entrypoint:

- `scripts/package_deployment_bundle.sh`

Primary orchestration entrypoint:

- `scripts/cloud_deploy.py`

Expected live manifest outputs:

- `dist/live/aws.json`
- `dist/live/azure.json`
- `dist/live/gcp.json`
- `dist/live/status.json`

Recommended command sequence:

1. `python3 scripts/cloud_deploy.py go-live`
2. `python3 scripts/cloud_deploy.py status`

What `go-live` does:

- reuses any existing AWS/GCP/Azure host manifests unless `--replace` is passed
- provisions the AWS VM, Azure Container Apps infrastructure, and GCP VM through the provider CLIs
- rebuilds the deployment tarball with macOS metadata and local installer artifacts excluded
- rebuilds the Azure Container Apps source bundle and remote-builds the anomaly image in ACR
- uploads the bundle to each VM
- runs `infra/vm/bootstrap_quantian_host.sh` for AWS and GCP
- deploys the Azure anomaly app to Container Apps with Blob-backed state
- verifies the public health endpoints and seeds the demo portfolio on GCP

Azure note:

- The pivot removes the Azure VM quota blocker by using Container Apps for the anomaly peer.
