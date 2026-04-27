from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"
LIVE_DIR = DIST_DIR / "live"
BUNDLE_PATH = DIST_DIR / "quantian-deploy.tar.gz"
AZURE_CONTAINERAPP_CONTEXT_DIR = DIST_DIR / "azure-containerapp-src"
AZURE_CONTAINERAPP_DOCKERFILE = ROOT_DIR / "azure_anomaly" / "containerapp.Dockerfile"
PACKAGE_SCRIPT = ROOT_DIR / "scripts" / "package_deployment_bundle.sh"
SSH_KEY_PATH = Path("/tmp/quantian_demo_key")
SSH_PUBLIC_KEY_PATH = Path("/tmp/quantian_demo_key.pub")
AZURE_CONTAINERAPP_PORT = 8002
AZURE_CONTAINERAPP_SECRET_NAME = "storconn"
SKIP_DIR_NAMES = {
    ".azure-cli",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "data",
    "dist",
}
SKIP_FILE_NAMES = {".DS_Store"}
SKIP_FILE_SUFFIXES = {".docx", ".pkg", ".pyc", ".pyd", ".pyo"}

DEFAULT_PORTFOLIO = {
    "portfolio_id": "demo_portfolio",
    "positions": [
        {"symbol": "BTCUSD", "weight": 0.4},
        {"symbol": "ETHUSD", "weight": 0.3},
        {"symbol": "AAPL", "weight": 0.2},
        {"symbol": "MSFT", "weight": 0.1},
    ],
}


def run(command: list[str], *, check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"+ {shlex.join(command)}", file=sys.stderr)
    env = os.environ.copy()
    if command and command[0] == "az":
        azure_config_dir = ROOT_DIR / ".azure-cli"
        home_azure_dir = Path.home() / ".azure"
        if home_azure_dir.exists():
            shutil.copytree(home_azure_dir, azure_config_dir, dirs_exist_ok=True)
        else:
            azure_config_dir.mkdir(parents=True, exist_ok=True)
        env.setdefault("AZURE_CONFIG_DIR", str(azure_config_dir))
    completed = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=capture_output,
        check=False,
        env=env,
    )
    if check and completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        raise SystemExit(completed.returncode)
    return completed


def parse_json_output(payload: str) -> dict[str, Any]:
    payload = payload.strip()
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(payload):
            if char not in "[{":
                continue
            try:
                decoded, _ = decoder.raw_decode(payload[index:])
                return decoded
            except json.JSONDecodeError:
                continue
        raise


def run_json(command: list[str]) -> dict[str, Any]:
    completed = run(command)
    return parse_json_output(completed.stdout)


def soft_fail(command: list[str], *, ok_substrings: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    completed = run(command, check=False)
    combined = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode == 0 or any(fragment in combined for fragment in ok_substrings):
        return completed
    if completed.stdout:
        print(completed.stdout, file=sys.stderr, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    raise SystemExit(completed.returncode)


def load_manifest(name: str) -> dict[str, Any] | None:
    path = LIVE_DIR / f"{name}.json"
    if not path.exists():
        return None
    payload = path.read_text().strip()
    if not payload:
        return None
    return json.loads(payload)


def save_manifest(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = LIVE_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def ensure_ssh_key() -> None:
    if SSH_KEY_PATH.exists() and SSH_PUBLIC_KEY_PATH.exists():
        return
    run(
        [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-f",
            str(SSH_KEY_PATH),
            "-N",
            "",
            "-C",
            "quantian-demo",
        ],
        capture_output=False,
    )


def package_bundle() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    run(["bash", str(PACKAGE_SCRIPT), str(BUNDLE_PATH)])
    return BUNDLE_PATH


def should_skip_bundle_path(relative_path: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in relative_path.parts):
        return True
    name = relative_path.name
    if name in SKIP_FILE_NAMES or name.startswith("._"):
        return True
    return relative_path.suffix in SKIP_FILE_SUFFIXES


def copy_filtered_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyd", "*.pyo", ".DS_Store", "._*"),
    )


def package_azure_containerapp_context() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if AZURE_CONTAINERAPP_CONTEXT_DIR.exists():
        shutil.rmtree(AZURE_CONTAINERAPP_CONTEXT_DIR)
    AZURE_CONTAINERAPP_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(AZURE_CONTAINERAPP_DOCKERFILE, AZURE_CONTAINERAPP_CONTEXT_DIR / "Dockerfile")
    shutil.copy2(
        ROOT_DIR / "azure_anomaly" / "requirements-containerapp.txt",
        AZURE_CONTAINERAPP_CONTEXT_DIR / "requirements-containerapp.txt",
    )
    copy_filtered_tree(ROOT_DIR / "azure_anomaly", AZURE_CONTAINERAPP_CONTEXT_DIR / "azure_anomaly")
    copy_filtered_tree(ROOT_DIR / "shared", AZURE_CONTAINERAPP_CONTEXT_DIR / "shared")
    return AZURE_CONTAINERAPP_CONTEXT_DIR


def output_value(command: list[str]) -> str:
    return run(command).stdout.strip()


def utc_deploy_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def stable_name_suffix(seed: str, *, length: int = 10) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:length]


def azure_suffix(args: argparse.Namespace) -> str:
    subscription_id = output_value(["az", "account", "show", "--query", "id", "--output", "tsv"]) or "local"
    return stable_name_suffix(f"{subscription_id}:{args.azure_resource_group}:{args.azure_location}")


def ensure_azure_provider(namespace: str) -> None:
    state = output_value(
        [
            "az",
            "provider",
            "show",
            "--namespace",
            namespace,
            "--query",
            "registrationState",
            "--output",
            "tsv",
        ]
    )
    if state.lower() == "registered":
        return
    run(
        [
            "az",
            "provider",
            "register",
            "--namespace",
            namespace,
            "--wait",
        ],
        capture_output=False,
    )


def extract_containerapp_fqdn(payload: dict[str, Any]) -> str | None:
    properties = payload.get("properties", {})
    configuration = properties.get("configuration", {})
    ingress = configuration.get("ingress", {})
    return ingress.get("fqdn") or properties.get("latestRevisionFqdn")


def load_containerapp(resource_group: str, app_name: str) -> dict[str, Any] | None:
    result = run(
        [
            "az",
            "containerapp",
            "show",
            "--resource-group",
            resource_group,
            "--name",
            app_name,
            "--output",
            "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    return parse_json_output(result.stdout)


def azure_container_env_vars(azure: dict[str, Any], endpoints: dict[str, str], *, base_url: str) -> list[str]:
    secret_ref = f"secretref:{AZURE_CONTAINERAPP_SECRET_NAME}"
    return [
        "APP_ENV=cloud",
        "SERVICE_HOST=0.0.0.0",
        f"SERVICE_PORT={AZURE_CONTAINERAPP_PORT}",
        "ENABLE_SERVICE_RUNTIME=true",
        "REQUEST_TIMEOUT_SECONDS=8",
        "HEARTBEAT_INTERVAL_SECONDS=20",
        "QUANTIAN_DATA_DIR=/tmp/quantian-data",
        "STORAGE_BACKEND=azure_blob",
        f"BASE_URL={base_url}",
        f"AZURE_ANOMALY_BASE_URL={base_url}",
        f"AZURE_ANOMALY_URL={base_url}",
        f"REGISTRY_URL={endpoints['REGISTRY_URL']}",
        f"LEDGER_URL={endpoints['REGISTRY_URL']}",
        f"AWS_INGESTION_URL={endpoints['INGESTION_URL']}",
        f"GCP_RISK_URL={endpoints['RISK_URL']}",
        f"AZURE_ANOMALY_STORAGE_CONNECTION_STRING={secret_ref}",
        f"AZURE_ANOMALY_STORAGE_CONTAINER={azure['storage_container']}",
        "AZURE_ANOMALY_STATE_BLOB_NAME=azure-anomaly/state.json",
    ]


def provision_aws(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_manifest("aws")
    if existing and existing.get("public_ip") and not args.replace:
        return existing

    ensure_ssh_key()

    subnet_data = run_json(["aws", "ec2", "describe-subnets", "--region", args.aws_region, "--output", "json"])
    subnets = subnet_data.get("Subnets", [])
    default_subnets = [subnet for subnet in subnets if subnet.get("DefaultForAz")]
    if not default_subnets:
        raise SystemExit("No default AWS subnet found for provisioning.")
    subnet = sorted(default_subnets, key=lambda item: item["AvailabilityZone"])[0]
    vpc_id = subnet["VpcId"]
    subnet_id = subnet["SubnetId"]

    image_data = run_json(
        [
            "aws",
            "ec2",
            "describe-images",
            "--region",
            args.aws_region,
            "--owners",
            "099720109477",
            "--filters",
            "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-jammy-22.04-amd64-server-*",
            "Name=state,Values=available",
            "Name=architecture,Values=x86_64",
            "--output",
            "json",
        ]
    )
    images = image_data.get("Images", [])
    if not images:
        raise SystemExit("No Ubuntu 22.04 AWS image was returned.")
    image_id = sorted(images, key=lambda item: item["CreationDate"], reverse=True)[0]["ImageId"]

    deploy_id = args.deploy_id or utc_deploy_id()
    key_name = f"quantian-demo-key-{deploy_id}"
    security_group_name = f"quantian-aws-host-{deploy_id}"

    run(
        [
            "aws",
            "ec2",
            "import-key-pair",
            "--region",
            args.aws_region,
            "--key-name",
            key_name,
            "--public-key-material",
            f"fileb://{SSH_PUBLIC_KEY_PATH}",
            "--output",
            "json",
        ]
    )

    security_group = run_json(
        [
            "aws",
            "ec2",
            "create-security-group",
            "--region",
            args.aws_region,
            "--group-name",
            security_group_name,
            "--description",
            "QuantIAN AWS registry, ingestion, and dashboard host",
            "--vpc-id",
            vpc_id,
            "--output",
            "json",
        ]
    )
    security_group_id = security_group["GroupId"]

    for port in (22, 8000, 8001, 8501):
        soft_fail(
            [
                "aws",
                "ec2",
                "authorize-security-group-ingress",
                "--region",
                args.aws_region,
                "--group-id",
                security_group_id,
                "--protocol",
                "tcp",
                "--port",
                str(port),
                "--cidr",
                "0.0.0.0/0",
            ],
            ok_substrings=("InvalidPermission.Duplicate",),
        )

    instance_data = run_json(
        [
            "aws",
            "ec2",
            "run-instances",
            "--region",
            args.aws_region,
            "--image-id",
            image_id,
            "--instance-type",
            args.aws_instance_type,
            "--key-name",
            key_name,
            "--security-group-ids",
            security_group_id,
            "--subnet-id",
            subnet_id,
            "--tag-specifications",
            f"ResourceType=instance,Tags=[{{Key=Name,Value={args.aws_instance_name}}}]",
            "--output",
            "json",
        ]
    )
    instance_id = instance_data["Instances"][0]["InstanceId"]

    run(["aws", "ec2", "wait", "instance-running", "--region", args.aws_region, "--instance-ids", instance_id])

    allocation_data = run_json(
        [
            "aws",
            "ec2",
            "allocate-address",
            "--region",
            args.aws_region,
            "--domain",
            "vpc",
            "--output",
            "json",
        ]
    )
    allocation_id = allocation_data["AllocationId"]
    public_ip = allocation_data["PublicIp"]

    run(
        [
            "aws",
            "ec2",
            "associate-address",
            "--region",
            args.aws_region,
            "--instance-id",
            instance_id,
            "--allocation-id",
            allocation_id,
        ]
    )

    return save_manifest(
        "aws",
        {
            "allocation_id": allocation_id,
            "deploy_id": deploy_id,
            "instance_id": instance_id,
            "instance_name": args.aws_instance_name,
            "key_name": key_name,
            "public_ip": public_ip,
            "region": args.aws_region,
            "security_group_id": security_group_id,
            "ssh_user": "ubuntu",
            "subnet_id": subnet_id,
            "vpc_id": vpc_id,
        },
    )


def provision_azure(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_manifest("azure")
    suffix = azure_suffix(args)
    existing = existing if existing and existing.get("type") == "container_app" and not args.replace else {}
    app_name = args.azure_app_name or existing.get("app_name") or "quantian-azure-anomaly"
    environment_name = args.azure_environment_name or existing.get("environment_name") or "quantian-azure-env"
    image_repository = args.azure_image_repository or existing.get("image_repository") or "quantian/azure-anomaly"
    registry_name = args.azure_registry_name or existing.get("registry_name") or f"qtanacr{suffix}"[:50]
    storage_account = args.azure_storage_account or existing.get("storage_account") or f"qtanom{suffix}"[:24]

    group_exists = run(
        ["az", "group", "exists", "--name", args.azure_resource_group],
    ).stdout.strip()
    if group_exists.lower() != "true":
        run(
            [
                "az",
                "group",
                "create",
                "--name",
                args.azure_resource_group,
                "--location",
                args.azure_location,
                "--output",
                "json",
            ]
        )

    ensure_azure_provider("Microsoft.App")
    ensure_azure_provider("Microsoft.ContainerRegistry")
    ensure_azure_provider("Microsoft.Storage")

    env_result = run(
        [
            "az",
            "containerapp",
            "env",
            "show",
            "--resource-group",
            args.azure_resource_group,
            "--name",
            environment_name,
            "--output",
            "json",
        ],
        check=False,
    )
    if env_result.returncode != 0:
        run(
            [
                "az",
                "containerapp",
                "env",
                "create",
                "--resource-group",
                args.azure_resource_group,
                "--name",
                environment_name,
                "--location",
                args.azure_location,
                "--logs-destination",
                "none",
                "--output",
                "json",
            ]
        )
    registry_result = run(
        [
            "az",
            "acr",
            "show",
            "--resource-group",
            args.azure_resource_group,
            "--name",
            registry_name,
            "--output",
            "json",
        ],
        check=False,
    )
    if registry_result.returncode != 0:
        run(
            [
                "az",
                "acr",
                "create",
                "--resource-group",
                args.azure_resource_group,
                "--name",
                registry_name,
                "--location",
                args.azure_location,
                "--sku",
                "Basic",
                "--admin-enabled",
                "true",
                "--output",
                "json",
            ]
        )
    else:
        run(
            [
                "az",
                "acr",
                "update",
                "--resource-group",
                args.azure_resource_group,
                "--name",
                registry_name,
                "--admin-enabled",
                "true",
                "--output",
                "json",
            ]
        )

    storage_result = run(
        [
            "az",
            "storage",
            "account",
            "show",
            "--resource-group",
            args.azure_resource_group,
            "--name",
            storage_account,
            "--output",
            "json",
        ],
        check=False,
    )
    if storage_result.returncode != 0:
        run(
            [
                "az",
                "storage",
                "account",
                "create",
                "--resource-group",
                args.azure_resource_group,
                "--name",
                storage_account,
                "--location",
                args.azure_location,
                "--sku",
                "Standard_LRS",
                "--kind",
                "StorageV2",
                "--allow-blob-public-access",
                "false",
                "--output",
                "json",
            ]
        )

    connection_string = output_value(
        [
            "az",
            "storage",
            "account",
            "show-connection-string",
            "--resource-group",
            args.azure_resource_group,
            "--name",
            storage_account,
            "--query",
            "connectionString",
            "--output",
            "tsv",
        ]
    )

    soft_fail(
        [
            "az",
            "storage",
            "container",
            "create",
            "--connection-string",
            connection_string,
            "--name",
            args.azure_storage_container,
            "--output",
            "json",
        ],
            ok_substrings=("ContainerAlreadyExists",),
        )

    registry_server = output_value(
        [
            "az",
            "acr",
            "show",
            "--resource-group",
            args.azure_resource_group,
            "--name",
            registry_name,
            "--query",
            "loginServer",
            "--output",
            "tsv",
        ]
    )

    containerapp_data = load_containerapp(args.azure_resource_group, app_name) or {}
    default_hostname = extract_containerapp_fqdn(containerapp_data)
    base_url = f"https://{default_hostname}" if default_hostname else None

    return save_manifest(
        "azure",
        {
            "app_name": app_name,
            "base_url": base_url,
            "default_hostname": default_hostname,
            "environment_name": environment_name,
            "image_repository": image_repository,
            "location": args.azure_location,
            "max_replicas": existing.get("max_replicas", args.azure_max_replicas),
            "memory": existing.get("memory", args.azure_memory),
            "min_replicas": existing.get("min_replicas", args.azure_min_replicas),
            "registry_name": registry_name,
            "registry_server": registry_server,
            "resource_group": args.azure_resource_group,
            "storage_account": storage_account,
            "storage_container": args.azure_storage_container,
            "storage_type": "azure_blob",
            "target_port": AZURE_CONTAINERAPP_PORT,
            "type": "container_app",
            "cpu": existing.get("cpu", args.azure_cpu),
        },
    )


def provision_gcp(args: argparse.Namespace) -> dict[str, Any]:
    existing = load_manifest("gcp")
    if existing and existing.get("public_ip") and not args.replace:
        return existing

    firewall_check = run(
        ["gcloud", "compute", "firewall-rules", "describe", args.gcp_firewall_rule, "--format=json"],
        check=False,
    )
    if firewall_check.returncode != 0:
        run(
            [
                "gcloud",
                "compute",
                "firewall-rules",
                "create",
                args.gcp_firewall_rule,
                "--allow",
                "tcp:8003",
                "--source-ranges",
                "0.0.0.0/0",
                "--target-tags",
                args.gcp_network_tag,
                "--format=json",
            ]
        )

    instance_result = run(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            args.gcp_instance_name,
            "--zone",
            args.gcp_zone,
            "--format=json",
        ],
        check=False,
    )

    if instance_result.returncode != 0:
        run(
            [
                "gcloud",
                "compute",
                "instances",
                "create",
                args.gcp_instance_name,
                "--zone",
                args.gcp_zone,
                "--machine-type",
                args.gcp_machine_type,
                "--image-family",
                "ubuntu-2204-lts",
                "--image-project",
                "ubuntu-os-cloud",
                "--boot-disk-size",
                "20GB",
                "--tags",
                args.gcp_network_tag,
                "--format=json",
            ]
        )

    instance_data = run_json(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            args.gcp_instance_name,
            "--zone",
            args.gcp_zone,
            "--format=json",
        ]
    )
    access_configs = instance_data["networkInterfaces"][0]["accessConfigs"]
    public_ip = access_configs[0]["natIP"]

    project_name = run(["gcloud", "config", "get-value", "project"]).stdout.strip()
    return save_manifest(
        "gcp",
        {
            "instance": args.gcp_instance_name,
            "project": project_name,
            "public_ip": public_ip,
            "ssh_user": args.gcp_ssh_user,
            "zone": args.gcp_zone,
        },
    )


def upload_bundle(provider: str, manifest: dict[str, Any]) -> None:
    if provider == "gcp":
        run(
            [
                "gcloud",
                "compute",
                "scp",
                str(BUNDLE_PATH),
                f"{manifest['instance']}:/tmp/quantian-deploy.tar.gz",
                "--zone",
                manifest["zone"],
            ],
            capture_output=False,
        )
        return

    ssh_user = manifest.get("ssh_user", "ubuntu")
    run(
        [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            str(SSH_KEY_PATH),
            str(BUNDLE_PATH),
            f"{ssh_user}@{manifest['public_ip']}:/tmp/quantian-deploy.tar.gz",
        ],
        capture_output=False,
    )


def run_remote(provider: str, manifest: dict[str, Any], command: str) -> None:
    if provider == "gcp":
        run(
            [
                "gcloud",
                "compute",
                "ssh",
                manifest["instance"],
                "--zone",
                manifest["zone"],
                "--command",
                command,
            ],
            capture_output=False,
        )
        return

    ssh_user = manifest.get("ssh_user", "ubuntu")
    run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-i",
            str(SSH_KEY_PATH),
            f"{ssh_user}@{manifest['public_ip']}",
            command,
        ],
        capture_output=False,
    )


def remote_bootstrap_command(role: str, endpoints: dict[str, str]) -> str:
    env_exports = " ".join(f"{key}={shlex.quote(value)}" for key, value in endpoints.items())
    return (
        "set -euo pipefail; "
        "sudo mkdir -p /opt/quantian; "
        "sudo chown $(id -un):$(id -gn) /opt/quantian; "
        "tar -xzf /tmp/quantian-deploy.tar.gz -C /opt/quantian; "
        "cd /opt/quantian; "
        f"{env_exports} bash infra/vm/bootstrap_quantian_host.sh {shlex.quote(role)}"
    )


def build_azure_container_image(azure: dict[str, Any], *, deploy_id: str | None = None) -> tuple[str, str]:
    package_azure_containerapp_context()
    image_tag = deploy_id or utc_deploy_id()
    run(
        [
            "az",
            "acr",
            "build",
            "--resource-group",
            azure["resource_group"],
            "--registry",
            azure["registry_name"],
            "--image",
            f"{azure['image_repository']}:{image_tag}",
            "--file",
            str(AZURE_CONTAINERAPP_CONTEXT_DIR / "Dockerfile"),
            str(AZURE_CONTAINERAPP_CONTEXT_DIR),
        ],
        capture_output=False,
    )
    return f"{azure['registry_server']}/{azure['image_repository']}:{image_tag}", image_tag


def deploy_azure_container_app(azure: dict[str, Any], endpoints: dict[str, str]) -> dict[str, Any]:
    ensure_azure_provider("Microsoft.App")
    connection_string = output_value(
        [
            "az",
            "storage",
            "account",
            "show-connection-string",
            "--resource-group",
            azure["resource_group"],
            "--name",
            azure["storage_account"],
            "--query",
            "connectionString",
            "--output",
            "tsv",
        ]
    )
    registry_credentials = run_json(
        [
            "az",
            "acr",
            "credential",
            "show",
            "--resource-group",
            azure["resource_group"],
            "--name",
            azure["registry_name"],
            "--output",
            "json",
        ]
    )
    registry_username = registry_credentials["username"]
    registry_password = registry_credentials["passwords"][0]["value"]
    image_ref, image_tag = build_azure_container_image(azure)

    current_app = load_containerapp(azure["resource_group"], azure["app_name"])
    provisional_base_url = azure.get("base_url") or "https://bootstrap.invalid"
    env_vars = azure_container_env_vars(azure, endpoints, base_url=provisional_base_url)

    if current_app is None:
        run(
            [
                "az",
                "containerapp",
                "create",
                "--resource-group",
                azure["resource_group"],
                "--name",
                azure["app_name"],
                "--environment",
                azure["environment_name"],
                "--image",
                image_ref,
                "--registry-server",
                azure["registry_server"],
                "--registry-username",
                registry_username,
                "--registry-password",
                registry_password,
                "--ingress",
                "external",
                "--target-port",
                str(azure["target_port"]),
                "--cpu",
                str(azure["cpu"]),
                "--memory",
                azure["memory"],
                "--min-replicas",
                str(azure["min_replicas"]),
                "--max-replicas",
                str(azure["max_replicas"]),
                "--revisions-mode",
                "single",
                "--secrets",
                f"{AZURE_CONTAINERAPP_SECRET_NAME}={connection_string}",
                "--env-vars",
                *env_vars,
                "--output",
                "json",
            ]
        )
    else:
        run(
            [
                "az",
                "containerapp",
                "secret",
                "set",
                "--resource-group",
                azure["resource_group"],
                "--name",
                azure["app_name"],
                "--secrets",
                f"{AZURE_CONTAINERAPP_SECRET_NAME}={connection_string}",
                "--output",
                "json",
            ]
        )
        run(
            [
                "az",
                "containerapp",
                "update",
                "--resource-group",
                azure["resource_group"],
                "--name",
                azure["app_name"],
                "--image",
                image_ref,
                "--cpu",
                str(azure["cpu"]),
                "--memory",
                azure["memory"],
                "--min-replicas",
                str(azure["min_replicas"]),
                "--max-replicas",
                str(azure["max_replicas"]),
                "--replace-env-vars",
                *env_vars,
                "--output",
                "json",
            ]
        )

    current_app = load_containerapp(azure["resource_group"], azure["app_name"]) or {}
    fqdn = extract_containerapp_fqdn(current_app)
    if not fqdn:
        raise SystemExit("Azure Container App did not return an ingress FQDN.")
    base_url = f"https://{fqdn}"
    if base_url != provisional_base_url:
        run(
            [
                "az",
                "containerapp",
                "update",
                "--resource-group",
                azure["resource_group"],
                "--name",
                azure["app_name"],
                "--replace-env-vars",
                *azure_container_env_vars(azure, endpoints, base_url=base_url),
                "--output",
                "json",
            ]
        )
        current_app = load_containerapp(azure["resource_group"], azure["app_name"]) or current_app

    return save_manifest(
        "azure",
        {
            **azure,
            "base_url": base_url,
            "default_hostname": fqdn,
            "image_ref": image_ref,
            "image_tag": image_tag,
            "latest_revision_name": (
                current_app.get("properties", {}).get("latestRevisionName")
            ),
        },
    )


def wait_for_http(url: str, *, timeout_seconds: float = 300.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        completed = subprocess.run(
            ["curl", "-fsSL", "--max-time", "5", url],
            cwd=ROOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return True
        time.sleep(3)
    return False


def seed_portfolio(risk_url: str) -> None:
    payload = json.dumps(DEFAULT_PORTFOLIO).encode("utf-8")
    request = urllib.request.Request(
        f"{risk_url}/risk/portfolio",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        return


def bootstrap_hosts(_: argparse.Namespace) -> dict[str, Any]:
    aws = load_manifest("aws")
    azure = load_manifest("azure")
    gcp = load_manifest("gcp")

    missing = [
        provider
        for provider, manifest in (("aws", aws), ("azure", azure), ("gcp", gcp))
        if not manifest
        or (provider in {"aws", "gcp"} and not manifest.get("public_ip"))
        or (provider == "azure" and not manifest.get("app_name"))
    ]
    if missing:
        raise SystemExit(f"Missing live manifest(s): {', '.join(missing)}")

    package_bundle()
    provisional_endpoints = {
        "REGISTRY_URL": f"http://{aws['public_ip']}:8000",
        "INGESTION_URL": f"http://{aws['public_ip']}:8001",
        "RISK_URL": f"http://{gcp['public_ip']}:8003",
    }
    if not azure.get("base_url"):
        azure = deploy_azure_container_app(azure, provisional_endpoints)
    endpoints = {
        **provisional_endpoints,
        "ANOMALY_URL": azure["base_url"],
    }

    upload_bundle("aws", aws)
    run_remote("aws", aws, remote_bootstrap_command("aws", endpoints))

    upload_bundle("gcp", gcp)
    run_remote("gcp", gcp, remote_bootstrap_command("gcp", endpoints))

    health = {
        "registry": wait_for_http(f"{endpoints['REGISTRY_URL']}/health"),
        "ingestion": wait_for_http(f"{endpoints['INGESTION_URL']}/health"),
        "anomaly": wait_for_http(f"{endpoints['ANOMALY_URL']}/health"),
        "risk": wait_for_http(f"{endpoints['RISK_URL']}/health"),
        "dashboard": wait_for_http(f"http://{aws['public_ip']}:8501"),
    }

    if health["risk"]:
        try:
            seed_portfolio(endpoints["RISK_URL"])
        except urllib.error.URLError:
            health["portfolio_seeded"] = False
        else:
            health["portfolio_seeded"] = True
    else:
        health["portfolio_seeded"] = False

    status_payload = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "dashboard": f"http://{aws['public_ip']}:8501",
            "registry": endpoints["REGISTRY_URL"],
            "ingestion": endpoints["INGESTION_URL"],
            "anomaly": endpoints["ANOMALY_URL"],
            "risk": endpoints["RISK_URL"],
        },
        "health": health,
    }
    save_manifest("status", status_payload)
    return status_payload


def collect_status(_: argparse.Namespace) -> dict[str, Any]:
    aws = load_manifest("aws")
    azure = load_manifest("azure")
    gcp = load_manifest("gcp")
    status = {
        "aws": aws,
        "azure": azure,
        "gcp": gcp,
        "health": {},
    }

    if aws and aws.get("public_ip"):
        status["health"]["registry"] = wait_for_http(f"http://{aws['public_ip']}:8000/health", timeout_seconds=5)
        status["health"]["ingestion"] = wait_for_http(f"http://{aws['public_ip']}:8001/health", timeout_seconds=5)
        status["health"]["dashboard"] = wait_for_http(f"http://{aws['public_ip']}:8501", timeout_seconds=5)
    if azure and azure.get("base_url"):
        status["health"]["anomaly"] = wait_for_http(f"{azure['base_url']}/health", timeout_seconds=5)
    if gcp and gcp.get("public_ip"):
        status["health"]["risk"] = wait_for_http(f"http://{gcp['public_ip']}:8003/health", timeout_seconds=5)
    return status


def go_live(args: argparse.Namespace) -> dict[str, Any]:
    provision_aws(args)
    provision_azure(args)
    provision_gcp(args)
    return bootstrap_hosts(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision and deploy the QuantIAN live multi-cloud stack.")
    parser.add_argument("--replace", action="store_true", help="Recreate a provider resource instead of reusing dist/live manifests.")
    parser.add_argument("--deploy-id", help="Override the AWS key/security-group suffix.")
    parser.add_argument("--aws-region", default="us-east-1")
    parser.add_argument("--aws-instance-type", default="t3.small")
    parser.add_argument("--aws-instance-name", default="quantian-aws-core")
    parser.add_argument("--azure-resource-group", default="quantian-rg")
    parser.add_argument("--azure-location", default="eastus")
    parser.add_argument("--azure-app-name")
    parser.add_argument("--azure-environment-name")
    parser.add_argument("--azure-registry-name")
    parser.add_argument("--azure-image-repository", default="quantian/azure-anomaly")
    parser.add_argument("--azure-storage-account")
    parser.add_argument("--azure-storage-container", default="quantian-state")
    parser.add_argument("--azure-cpu", default="0.5")
    parser.add_argument("--azure-memory", default="1.0Gi")
    parser.add_argument("--azure-min-replicas", type=int, default=1)
    parser.add_argument("--azure-max-replicas", type=int, default=1)
    parser.add_argument("--gcp-zone", default="us-central1-a")
    parser.add_argument("--gcp-instance-name", default="quantian-gcp-risk")
    parser.add_argument("--gcp-machine-type", default="e2-small")
    parser.add_argument("--gcp-network-tag", default="quantian-risk")
    parser.add_argument("--gcp-firewall-rule", default="quantian-risk-allow")
    parser.add_argument("--gcp-ssh-user", default="bhaveshgupta01")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("package", help="Build the deployment tarball.")
    subparsers.add_parser(
        "package-azure",
        aliases=["package-webapp"],
        help="Build the Azure Container Apps source bundle.",
    )
    subparsers.add_parser("provision-aws", help="Create or reuse the AWS VM and persist dist/live/aws.json.")
    subparsers.add_parser(
        "provision-azure",
        help="Create or reuse the Azure Container Apps infrastructure and persist dist/live/azure.json.",
    )
    subparsers.add_parser("provision-gcp", help="Create or reuse the GCP VM and persist dist/live/gcp.json.")
    subparsers.add_parser(
        "deploy-azure",
        help="Deploy the Azure anomaly app to Azure Container Apps and refresh its runtime settings.",
    )
    subparsers.add_parser("bootstrap", help="Upload the bundle and bootstrap all three hosts.")
    subparsers.add_parser("status", help="Check the current public health endpoints.")
    subparsers.add_parser("go-live", help="Provision all hosts, upload the bundle, bootstrap them, and verify health.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "package":
        print(str(package_bundle()))
        return
    if args.command in {"package-azure", "package-webapp"}:
        print(str(package_azure_containerapp_context()))
        return
    if args.command == "provision-aws":
        print(json.dumps(provision_aws(args), indent=2))
        return
    if args.command == "provision-azure":
        print(json.dumps(provision_azure(args), indent=2))
        return
    if args.command == "provision-gcp":
        print(json.dumps(provision_gcp(args), indent=2))
        return
    if args.command == "deploy-azure":
        azure = load_manifest("azure")
        aws = load_manifest("aws")
        gcp = load_manifest("gcp")
        if not azure or not azure.get("app_name") or not aws or not gcp:
            raise SystemExit("Missing aws/gcp/azure manifests required for Azure deployment.")
        azure = deploy_azure_container_app(
            azure,
            {
                "REGISTRY_URL": f"http://{aws['public_ip']}:8000",
                "INGESTION_URL": f"http://{aws['public_ip']}:8001",
                "RISK_URL": f"http://{gcp['public_ip']}:8003",
            },
        )
        print(json.dumps({"azure": azure, "deployed": True}, indent=2))
        return
    if args.command == "bootstrap":
        print(json.dumps(bootstrap_hosts(args), indent=2))
        return
    if args.command == "status":
        print(json.dumps(collect_status(args), indent=2))
        return
    if args.command == "go-live":
        print(json.dumps(go_live(args), indent=2))
        return

    raise SystemExit(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
