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
GCP_CLOUDRUN_CONTEXT_DIR = DIST_DIR / "gcp-cloudrun-src"
GCP_CLOUDRUN_DOCKERFILE = ROOT_DIR / "gcp_risk" / "cloudrun.Dockerfile"
APPRUNNER_REGISTRY_CONTEXT_DIR = DIST_DIR / "aws-apprunner-registry-src"
APPRUNNER_REGISTRY_DOCKERFILE = ROOT_DIR / "registry_service" / "apprunner.Dockerfile"
APPRUNNER_INGESTION_CONTEXT_DIR = DIST_DIR / "aws-apprunner-ingestion-src"
APPRUNNER_INGESTION_DOCKERFILE = ROOT_DIR / "aws_ingestion" / "apprunner.Dockerfile"
PACKAGE_SCRIPT = ROOT_DIR / "scripts" / "package_deployment_bundle.sh"
SSH_KEY_PATH = Path("/tmp/quantian_demo_key")
SSH_PUBLIC_KEY_PATH = Path("/tmp/quantian_demo_key.pub")
AZURE_CONTAINERAPP_PORT = 8002
AZURE_CONTAINERAPP_SECRET_NAME = "storconn"
GCP_CLOUDRUN_PORT = 8003
APPRUNNER_REGISTRY_PORT = 8000
APPRUNNER_INGESTION_PORT = 8001
APPRUNNER_ECR_ACCESS_ROLE_NAME = "QuantIANAppRunnerECRAccessRole"
APPRUNNER_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "build.apprunner.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}
APPRUNNER_ECR_ACCESS_POLICY_ARN = (
    "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
)
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


def package_gcp_cloudrun_context() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if GCP_CLOUDRUN_CONTEXT_DIR.exists():
        shutil.rmtree(GCP_CLOUDRUN_CONTEXT_DIR)
    GCP_CLOUDRUN_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(GCP_CLOUDRUN_DOCKERFILE, GCP_CLOUDRUN_CONTEXT_DIR / "Dockerfile")
    shutil.copy2(
        ROOT_DIR / "gcp_risk" / "requirements-cloudrun.txt",
        GCP_CLOUDRUN_CONTEXT_DIR / "requirements-cloudrun.txt",
    )
    copy_filtered_tree(ROOT_DIR / "gcp_risk", GCP_CLOUDRUN_CONTEXT_DIR / "gcp_risk")
    copy_filtered_tree(ROOT_DIR / "shared", GCP_CLOUDRUN_CONTEXT_DIR / "shared")
    return GCP_CLOUDRUN_CONTEXT_DIR


def package_apprunner_registry_context() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if APPRUNNER_REGISTRY_CONTEXT_DIR.exists():
        shutil.rmtree(APPRUNNER_REGISTRY_CONTEXT_DIR)
    APPRUNNER_REGISTRY_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(APPRUNNER_REGISTRY_DOCKERFILE, APPRUNNER_REGISTRY_CONTEXT_DIR / "Dockerfile")
    shutil.copy2(
        ROOT_DIR / "registry_service" / "requirements-apprunner.txt",
        APPRUNNER_REGISTRY_CONTEXT_DIR / "requirements-apprunner.txt",
    )
    copy_filtered_tree(ROOT_DIR / "registry_service", APPRUNNER_REGISTRY_CONTEXT_DIR / "registry_service")
    copy_filtered_tree(ROOT_DIR / "shared", APPRUNNER_REGISTRY_CONTEXT_DIR / "shared")
    return APPRUNNER_REGISTRY_CONTEXT_DIR


def package_apprunner_ingestion_context() -> Path:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if APPRUNNER_INGESTION_CONTEXT_DIR.exists():
        shutil.rmtree(APPRUNNER_INGESTION_CONTEXT_DIR)
    APPRUNNER_INGESTION_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(APPRUNNER_INGESTION_DOCKERFILE, APPRUNNER_INGESTION_CONTEXT_DIR / "Dockerfile")
    shutil.copy2(
        ROOT_DIR / "aws_ingestion" / "requirements-apprunner.txt",
        APPRUNNER_INGESTION_CONTEXT_DIR / "requirements-apprunner.txt",
    )
    copy_filtered_tree(ROOT_DIR / "aws_ingestion", APPRUNNER_INGESTION_CONTEXT_DIR / "aws_ingestion")
    copy_filtered_tree(ROOT_DIR / "shared", APPRUNNER_INGESTION_CONTEXT_DIR / "shared")
    return APPRUNNER_INGESTION_CONTEXT_DIR


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


def ensure_apprunner_ecr_role(account_id: str) -> str:
    role_arn = f"arn:aws:iam::{account_id}:role/{APPRUNNER_ECR_ACCESS_ROLE_NAME}"
    role_check = run(
        ["aws", "iam", "get-role", "--role-name", APPRUNNER_ECR_ACCESS_ROLE_NAME, "--output", "json"],
        check=False,
    )
    if role_check.returncode != 0:
        run(
            [
                "aws",
                "iam",
                "create-role",
                "--role-name",
                APPRUNNER_ECR_ACCESS_ROLE_NAME,
                "--assume-role-policy-document",
                json.dumps(APPRUNNER_TRUST_POLICY),
                "--description",
                "Allows AWS App Runner to pull QuantIAN images from ECR",
                "--output",
                "json",
            ]
        )
        run(
            [
                "aws",
                "iam",
                "attach-role-policy",
                "--role-name",
                APPRUNNER_ECR_ACCESS_ROLE_NAME,
                "--policy-arn",
                APPRUNNER_ECR_ACCESS_POLICY_ARN,
            ]
        )
        time.sleep(8)
    return role_arn


def ensure_ecr_repository(region: str, repository_name: str) -> str:
    describe = run(
        [
            "aws",
            "ecr",
            "describe-repositories",
            "--region",
            region,
            "--repository-names",
            repository_name,
            "--output",
            "json",
        ],
        check=False,
    )
    if describe.returncode == 0:
        payload = parse_json_output(describe.stdout)
        return payload["repositories"][0]["repositoryUri"]
    create = run_json(
        [
            "aws",
            "ecr",
            "create-repository",
            "--region",
            region,
            "--repository-name",
            repository_name,
            "--image-scanning-configuration",
            "scanOnPush=true",
            "--output",
            "json",
        ]
    )
    return create["repository"]["repositoryUri"]


def docker_login_ecr(region: str, registry_host: str) -> None:
    password = output_value(["aws", "ecr", "get-login-password", "--region", region])
    completed = subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry_host],
        input=password,
        text=True,
        cwd=ROOT_DIR,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        raise SystemExit(completed.returncode)


def load_apprunner_service(service_arn: str, region: str) -> dict[str, Any] | None:
    result = run(
        [
            "aws",
            "apprunner",
            "describe-service",
            "--region",
            region,
            "--service-arn",
            service_arn,
            "--output",
            "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    return parse_json_output(result.stdout)


def find_apprunner_service(service_name: str, region: str) -> dict[str, Any] | None:
    payload = run_json(
        ["aws", "apprunner", "list-services", "--region", region, "--output", "json"]
    )
    for entry in payload.get("ServiceSummaryList", []):
        if entry.get("ServiceName") == service_name:
            return entry
    return None


def wait_for_apprunner_running(service_arn: str, region: str, *, timeout_seconds: float = 600.0) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        payload = load_apprunner_service(service_arn, region)
        if payload:
            last = payload
            status_value = payload.get("Service", {}).get("Status")
            if status_value == "RUNNING":
                return payload
            if status_value in {"CREATE_FAILED", "DELETE_FAILED", "PAUSED"}:
                raise SystemExit(f"App Runner service entered terminal state: {status_value}")
        time.sleep(8)
    raise SystemExit(f"Timed out waiting for App Runner service {service_arn} to become RUNNING; last status was {last.get('Service', {}).get('Status')}")


def apprunner_env_pairs(kind: str, endpoints: dict[str, str], *, base_url: str, port: int) -> dict[str, str]:
    common = {
        "APP_ENV": "cloud",
        "SERVICE_HOST": "0.0.0.0",
        "SERVICE_PORT": str(port),
        "ENABLE_SERVICE_RUNTIME": "true",
        "REQUEST_TIMEOUT_SECONDS": "8",
        "HEARTBEAT_INTERVAL_SECONDS": "20",
        "QUANTIAN_DATA_DIR": "/tmp/quantian-data",
        "STORAGE_BACKEND": "memory",
        "BASE_URL": base_url,
        "REGISTRY_URL": endpoints.get("REGISTRY_URL", base_url if kind == "registry" else ""),
        "LEDGER_URL": endpoints.get("REGISTRY_URL", base_url if kind == "registry" else ""),
    }
    if kind == "registry":
        common["LEDGER_VERIFY_INTERVAL_SECONDS"] = "60"
    if kind == "ingestion":
        common["AWS_INGESTION_BASE_URL"] = base_url
        common["AWS_INGESTION_URL"] = base_url
        common["AZURE_ANOMALY_URL"] = endpoints.get("ANOMALY_URL", "")
        common["GCP_RISK_URL"] = endpoints.get("RISK_URL", "")
    return common


def load_cloudrun_service(project: str, region: str, service_name: str) -> dict[str, Any] | None:
    result = run(
        [
            "gcloud",
            "run",
            "services",
            "describe",
            service_name,
            "--project",
            project,
            "--region",
            region,
            "--platform",
            "managed",
            "--format",
            "json",
        ],
        check=False,
    )
    if result.returncode != 0:
        return None
    return parse_json_output(result.stdout)


def extract_cloudrun_url(payload: dict[str, Any]) -> str | None:
    status_block = payload.get("status", {})
    return status_block.get("url") or payload.get("url")


def gcp_cloudrun_env_pairs(endpoints: dict[str, str], *, base_url: str) -> dict[str, str]:
    return {
        "APP_ENV": "cloud",
        "SERVICE_HOST": "0.0.0.0",
        "SERVICE_PORT": str(GCP_CLOUDRUN_PORT),
        "ENABLE_SERVICE_RUNTIME": "true",
        "REQUEST_TIMEOUT_SECONDS": "8",
        "HEARTBEAT_INTERVAL_SECONDS": "20",
        "QUANTIAN_DATA_DIR": "/tmp/quantian-data",
        "STORAGE_BACKEND": "memory",
        "BASE_URL": base_url,
        "GCP_RISK_BASE_URL": base_url,
        "GCP_RISK_URL": base_url,
        "REGISTRY_URL": endpoints["REGISTRY_URL"],
        "LEDGER_URL": endpoints["REGISTRY_URL"],
        "AWS_INGESTION_URL": endpoints["INGESTION_URL"],
        "AZURE_ANOMALY_URL": endpoints.get("ANOMALY_URL", ""),
    }


def encode_cloudrun_env_vars(env_pairs: dict[str, str]) -> str:
    parts = []
    for key, value in env_pairs.items():
        if "@" in value:
            raise SystemExit(f"Cloud Run env var {key} cannot contain '@' (used as our delimiter)")
        parts.append(f"{key}={value}")
    return "^@^" + "@".join(parts)


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
    existing = load_manifest("aws") or {}
    existing = existing if existing.get("type") == "app_runner" and not args.replace else {}

    region = args.aws_region or existing.get("region") or "us-east-1"
    account_id = (
        args.aws_account_id
        or existing.get("account_id")
        or output_value(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])
    )
    if not account_id:
        raise SystemExit("Unable to resolve AWS account ID; configure aws CLI credentials.")

    registry_host = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    role_arn = ensure_apprunner_ecr_role(account_id)

    registry_repo_name = (
        args.aws_registry_repo or existing.get("registry", {}).get("ecr_repository") or "quantian-registry"
    )
    ingestion_repo_name = (
        args.aws_ingestion_repo or existing.get("ingestion", {}).get("ecr_repository") or "quantian-ingestion"
    )
    registry_repo_uri = ensure_ecr_repository(region, registry_repo_name)
    ingestion_repo_uri = ensure_ecr_repository(region, ingestion_repo_name)

    registry_service_name = (
        args.aws_registry_service_name
        or existing.get("registry", {}).get("service_name")
        or "quantian-aws-registry"
    )
    ingestion_service_name = (
        args.aws_ingestion_service_name
        or existing.get("ingestion", {}).get("service_name")
        or "quantian-aws-ingestion"
    )

    return save_manifest(
        "aws",
        {
            "type": "app_runner",
            "account_id": account_id,
            "region": region,
            "registry_host": registry_host,
            "ecr_access_role_arn": role_arn,
            "registry": {
                "service_name": registry_service_name,
                "ecr_repository": registry_repo_name,
                "ecr_repository_uri": registry_repo_uri,
                "port": APPRUNNER_REGISTRY_PORT,
                "cpu": existing.get("registry", {}).get("cpu", args.aws_cpu),
                "memory": existing.get("registry", {}).get("memory", args.aws_memory),
                "service_arn": existing.get("registry", {}).get("service_arn"),
                "base_url": existing.get("registry", {}).get("base_url"),
                "image_ref": existing.get("registry", {}).get("image_ref"),
                "image_tag": existing.get("registry", {}).get("image_tag"),
            },
            "ingestion": {
                "service_name": ingestion_service_name,
                "ecr_repository": ingestion_repo_name,
                "ecr_repository_uri": ingestion_repo_uri,
                "port": APPRUNNER_INGESTION_PORT,
                "cpu": existing.get("ingestion", {}).get("cpu", args.aws_cpu),
                "memory": existing.get("ingestion", {}).get("memory", args.aws_memory),
                "service_arn": existing.get("ingestion", {}).get("service_arn"),
                "base_url": existing.get("ingestion", {}).get("base_url"),
                "image_ref": existing.get("ingestion", {}).get("image_ref"),
                "image_tag": existing.get("ingestion", {}).get("image_tag"),
            },
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
    existing = load_manifest("gcp") or {}
    existing = existing if existing.get("type") == "cloud_run" and not args.replace else {}

    project = args.gcp_project or existing.get("project") or output_value(
        ["gcloud", "config", "get-value", "project"]
    )
    if not project:
        raise SystemExit("Unable to resolve GCP project (set --gcp-project or gcloud config).")

    region = args.gcp_region or existing.get("region") or "us-central1"
    service_name = args.gcp_service_name or existing.get("service_name") or "quantian-gcp-risk"
    repository = args.gcp_repository or existing.get("repository") or "quantian"
    image_repository = (
        args.gcp_image_repository or existing.get("image_repository") or "gcp-risk"
    )
    registry_host = f"{region}-docker.pkg.dev"

    for api in ("run.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com"):
        run(
            [
                "gcloud",
                "services",
                "enable",
                api,
                "--project",
                project,
            ],
            capture_output=False,
        )

    repo_check = run(
        [
            "gcloud",
            "artifacts",
            "repositories",
            "describe",
            repository,
            "--project",
            project,
            "--location",
            region,
            "--format",
            "json",
        ],
        check=False,
    )
    if repo_check.returncode != 0:
        run(
            [
                "gcloud",
                "artifacts",
                "repositories",
                "create",
                repository,
                "--project",
                project,
                "--location",
                region,
                "--repository-format",
                "docker",
                "--description",
                "QuantIAN GCP Cloud Run images",
                "--format",
                "json",
            ]
        )

    service_data = load_cloudrun_service(project, region, service_name) or {}
    base_url = extract_cloudrun_url(service_data)

    return save_manifest(
        "gcp",
        {
            "type": "cloud_run",
            "project": project,
            "region": region,
            "service_name": service_name,
            "repository": repository,
            "image_repository": image_repository,
            "registry_host": registry_host,
            "base_url": base_url,
            "default_hostname": base_url.removeprefix("https://") if base_url else None,
            "target_port": GCP_CLOUDRUN_PORT,
            "cpu": existing.get("cpu", args.gcp_cpu),
            "memory": existing.get("memory", args.gcp_memory),
            "min_instances": existing.get("min_instances", args.gcp_min_instances),
            "max_instances": existing.get("max_instances", args.gcp_max_instances),
        },
    )


def upload_bundle(provider: str, manifest: dict[str, Any]) -> None:
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


def build_gcp_container_image(gcp: dict[str, Any], *, deploy_id: str | None = None) -> tuple[str, str]:
    package_gcp_cloudrun_context()
    image_tag = deploy_id or utc_deploy_id()
    image_ref = (
        f"{gcp['registry_host']}/{gcp['project']}/"
        f"{gcp['repository']}/{gcp['image_repository']}:{image_tag}"
    )
    run(
        [
            "gcloud",
            "builds",
            "submit",
            str(GCP_CLOUDRUN_CONTEXT_DIR),
            "--project",
            gcp["project"],
            "--tag",
            image_ref,
        ],
        capture_output=False,
    )
    return image_ref, image_tag


def deploy_gcp_cloud_run(gcp: dict[str, Any], endpoints: dict[str, str]) -> dict[str, Any]:
    image_ref, image_tag = build_gcp_container_image(gcp)

    provisional_base_url = gcp.get("base_url") or "https://bootstrap.invalid"
    env_pairs = gcp_cloudrun_env_pairs(endpoints, base_url=provisional_base_url)

    run(
        [
            "gcloud",
            "run",
            "deploy",
            gcp["service_name"],
            "--project",
            gcp["project"],
            "--region",
            gcp["region"],
            "--platform",
            "managed",
            "--image",
            image_ref,
            "--port",
            str(gcp["target_port"]),
            "--cpu",
            str(gcp["cpu"]),
            "--memory",
            gcp["memory"],
            "--min-instances",
            str(gcp["min_instances"]),
            "--max-instances",
            str(gcp["max_instances"]),
            "--allow-unauthenticated",
            "--set-env-vars",
            encode_cloudrun_env_vars(env_pairs),
            "--quiet",
            "--format",
            "json",
        ],
        capture_output=False,
    )

    service_data = load_cloudrun_service(gcp["project"], gcp["region"], gcp["service_name"]) or {}
    base_url = extract_cloudrun_url(service_data)
    if not base_url:
        raise SystemExit("Cloud Run service did not return a public URL.")

    if base_url != provisional_base_url:
        run(
            [
                "gcloud",
                "run",
                "services",
                "update",
                gcp["service_name"],
                "--project",
                gcp["project"],
                "--region",
                gcp["region"],
                "--platform",
                "managed",
                "--update-env-vars",
                f"BASE_URL={base_url},GCP_RISK_BASE_URL={base_url},GCP_RISK_URL={base_url}",
                "--quiet",
                "--format",
                "json",
            ],
            capture_output=False,
        )
        service_data = load_cloudrun_service(gcp["project"], gcp["region"], gcp["service_name"]) or service_data

    latest_revision = (
        service_data.get("status", {}).get("latestReadyRevisionName")
        or service_data.get("status", {}).get("latestCreatedRevisionName")
    )

    return save_manifest(
        "gcp",
        {
            **gcp,
            "base_url": base_url,
            "default_hostname": base_url.removeprefix("https://") if base_url else None,
            "image_ref": image_ref,
            "image_tag": image_tag,
            "latest_revision_name": latest_revision,
        },
    )


def build_aws_container_image(
    aws: dict[str, Any],
    *,
    kind: str,
    deploy_id: str | None = None,
) -> tuple[str, str]:
    if kind == "registry":
        context_dir = package_apprunner_registry_context()
    elif kind == "ingestion":
        context_dir = package_apprunner_ingestion_context()
    else:
        raise SystemExit(f"Unknown AWS App Runner kind: {kind}")
    repo_uri = aws[kind]["ecr_repository_uri"]
    image_tag = deploy_id or utc_deploy_id()
    image_ref = f"{repo_uri}:{image_tag}"

    docker_login_ecr(aws["region"], aws["registry_host"])
    run(
        ["docker", "build", "--platform", "linux/amd64", "-t", image_ref, str(context_dir)],
        capture_output=False,
    )
    run(["docker", "push", image_ref], capture_output=False)
    return image_ref, image_tag


def deploy_aws_app_runner(
    aws: dict[str, Any],
    *,
    kind: str,
    endpoints: dict[str, str],
) -> dict[str, Any]:
    service_block = aws[kind]
    service_name = service_block["service_name"]
    region = aws["region"]
    port = service_block["port"]
    cpu = str(service_block["cpu"])
    memory = str(service_block["memory"])

    image_ref, image_tag = build_aws_container_image(aws, kind=kind)

    provisional_base_url = service_block.get("base_url") or "https://bootstrap.invalid"
    env_pairs = apprunner_env_pairs(kind, endpoints, base_url=provisional_base_url, port=port)

    source_config = {
        "ImageRepository": {
            "ImageIdentifier": image_ref,
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": str(port),
                "RuntimeEnvironmentVariables": env_pairs,
            },
        },
        "AutoDeploymentsEnabled": False,
        "AuthenticationConfiguration": {"AccessRoleArn": aws["ecr_access_role_arn"]},
    }
    instance_config = {"Cpu": cpu, "Memory": memory}
    health_check_config = {
        "Protocol": "HTTP",
        "Path": "/health",
        "Interval": 10,
        "Timeout": 5,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5,
    }

    summary = find_apprunner_service(service_name, region)
    if summary is None:
        run(
            [
                "aws",
                "apprunner",
                "create-service",
                "--region",
                region,
                "--service-name",
                service_name,
                "--source-configuration",
                json.dumps(source_config),
                "--instance-configuration",
                json.dumps(instance_config),
                "--health-check-configuration",
                json.dumps(health_check_config),
                "--output",
                "json",
            ]
        )
        summary = find_apprunner_service(service_name, region)
        if summary is None:
            raise SystemExit(f"Failed to locate App Runner service {service_name} after creation.")
        service_arn = summary["ServiceArn"]
    else:
        service_arn = summary["ServiceArn"]
        run(
            [
                "aws",
                "apprunner",
                "update-service",
                "--region",
                region,
                "--service-arn",
                service_arn,
                "--source-configuration",
                json.dumps(source_config),
                "--instance-configuration",
                json.dumps(instance_config),
                "--health-check-configuration",
                json.dumps(health_check_config),
                "--output",
                "json",
            ]
        )

    payload = wait_for_apprunner_running(service_arn, region)
    service_data = payload.get("Service", {})
    service_url = service_data.get("ServiceUrl")
    if not service_url:
        raise SystemExit(f"App Runner service {service_name} did not expose a ServiceUrl.")
    base_url = f"https://{service_url}"

    if base_url != provisional_base_url:
        env_pairs = apprunner_env_pairs(kind, endpoints, base_url=base_url, port=port)
        source_config["ImageRepository"]["ImageConfiguration"]["RuntimeEnvironmentVariables"] = env_pairs
        run(
            [
                "aws",
                "apprunner",
                "update-service",
                "--region",
                region,
                "--service-arn",
                service_arn,
                "--source-configuration",
                json.dumps(source_config),
                "--output",
                "json",
            ]
        )
        wait_for_apprunner_running(service_arn, region)

    updated_block = {
        **service_block,
        "service_arn": service_arn,
        "base_url": base_url,
        "default_hostname": service_url,
        "image_ref": image_ref,
        "image_tag": image_tag,
    }
    aws[kind] = updated_block
    save_manifest("aws", aws)
    return updated_block


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

    missing = []
    if (
        not aws
        or aws.get("type") != "app_runner"
        or not aws.get("registry", {}).get("ecr_repository_uri")
        or not aws.get("ingestion", {}).get("ecr_repository_uri")
    ):
        missing.append("aws")
    if not azure or not azure.get("app_name"):
        missing.append("azure")
    if not gcp or not gcp.get("service_name") or not gcp.get("project") or not gcp.get("region"):
        missing.append("gcp")
    if missing:
        raise SystemExit(f"Missing live manifest(s): {', '.join(missing)}")

    registry_block = deploy_aws_app_runner(aws, kind="registry", endpoints={})
    aws = load_manifest("aws") or aws
    registry_url = registry_block["base_url"]

    ingestion_endpoints = {"REGISTRY_URL": registry_url}
    ingestion_block = deploy_aws_app_runner(aws, kind="ingestion", endpoints=ingestion_endpoints)
    aws = load_manifest("aws") or aws
    ingestion_url = ingestion_block["base_url"]

    gcp_endpoints = {"REGISTRY_URL": registry_url, "INGESTION_URL": ingestion_url}
    gcp = deploy_gcp_cloud_run(gcp, gcp_endpoints)
    risk_url = gcp["base_url"]

    azure_endpoints = {**gcp_endpoints, "RISK_URL": risk_url}
    azure = deploy_azure_container_app(azure, azure_endpoints)
    anomaly_url = azure["base_url"]

    run(
        [
            "gcloud",
            "run",
            "services",
            "update",
            gcp["service_name"],
            "--project",
            gcp["project"],
            "--region",
            gcp["region"],
            "--platform",
            "managed",
            "--update-env-vars",
            f"AZURE_ANOMALY_URL={anomaly_url}",
            "--quiet",
            "--format",
            "json",
        ],
        capture_output=False,
    )

    final_ingestion_endpoints = {
        "REGISTRY_URL": registry_url,
        "ANOMALY_URL": anomaly_url,
        "RISK_URL": risk_url,
    }
    deploy_aws_app_runner(aws, kind="ingestion", endpoints=final_ingestion_endpoints)
    aws = load_manifest("aws") or aws

    endpoints = {
        "REGISTRY_URL": registry_url,
        "INGESTION_URL": ingestion_url,
        "RISK_URL": risk_url,
        "ANOMALY_URL": anomaly_url,
    }

    health = {
        "registry": wait_for_http(f"{endpoints['REGISTRY_URL']}/health"),
        "ingestion": wait_for_http(f"{endpoints['INGESTION_URL']}/health"),
        "anomaly": wait_for_http(f"{endpoints['ANOMALY_URL']}/health"),
        "risk": wait_for_http(f"{endpoints['RISK_URL']}/health"),
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

    if aws and aws.get("registry", {}).get("base_url"):
        status["health"]["registry"] = wait_for_http(f"{aws['registry']['base_url']}/health", timeout_seconds=5)
    if aws and aws.get("ingestion", {}).get("base_url"):
        status["health"]["ingestion"] = wait_for_http(f"{aws['ingestion']['base_url']}/health", timeout_seconds=5)
    if azure and azure.get("base_url"):
        status["health"]["anomaly"] = wait_for_http(f"{azure['base_url']}/health", timeout_seconds=5)
    if gcp and gcp.get("base_url"):
        status["health"]["risk"] = wait_for_http(f"{gcp['base_url']}/health", timeout_seconds=5)
    return status


def go_live(args: argparse.Namespace) -> dict[str, Any]:
    provision_aws(args)
    provision_azure(args)
    provision_gcp(args)
    return bootstrap_hosts(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision and deploy the QuantIAN live multi-cloud stack.")
    parser.add_argument("--replace", action="store_true", help="Recreate a provider resource instead of reusing dist/live manifests.")
    parser.add_argument("--deploy-id", help="Override the image tag suffix used for built containers.")
    parser.add_argument("--aws-region", default="us-east-1")
    parser.add_argument("--aws-account-id")
    parser.add_argument("--aws-registry-repo", default="quantian-registry")
    parser.add_argument("--aws-ingestion-repo", default="quantian-ingestion")
    parser.add_argument("--aws-registry-service-name", default="quantian-aws-registry")
    parser.add_argument("--aws-ingestion-service-name", default="quantian-aws-ingestion")
    parser.add_argument("--aws-cpu", default="256")
    parser.add_argument("--aws-memory", default="512")
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
    parser.add_argument("--gcp-project")
    parser.add_argument("--gcp-region", default="us-central1")
    parser.add_argument("--gcp-service-name", default="quantian-gcp-risk")
    parser.add_argument("--gcp-repository", default="quantian")
    parser.add_argument("--gcp-image-repository", default="gcp-risk")
    parser.add_argument("--gcp-cpu", default="1")
    parser.add_argument("--gcp-memory", default="512Mi")
    parser.add_argument("--gcp-min-instances", type=int, default=1)
    parser.add_argument("--gcp-max-instances", type=int, default=1)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "package-azure",
        aliases=["package-webapp"],
        help="Build the Azure Container Apps source bundle.",
    )
    subparsers.add_parser(
        "package-gcp",
        help="Build the GCP Cloud Run source bundle.",
    )
    subparsers.add_parser(
        "package-aws-registry",
        help="Build the AWS App Runner source bundle for the registry service.",
    )
    subparsers.add_parser(
        "package-aws-ingestion",
        help="Build the AWS App Runner source bundle for the ingestion service.",
    )
    subparsers.add_parser(
        "provision-aws",
        help="Create or reuse the AWS App Runner ECR repos + IAM role; persist dist/live/aws.json.",
    )
    subparsers.add_parser(
        "provision-azure",
        help="Create or reuse the Azure Container Apps infrastructure and persist dist/live/azure.json.",
    )
    subparsers.add_parser(
        "provision-gcp",
        help="Enable GCP APIs and create the Artifact Registry repo for Cloud Run; persist dist/live/gcp.json.",
    )
    subparsers.add_parser(
        "deploy-aws-registry",
        help="Build the registry image and deploy it to AWS App Runner; refresh its runtime settings.",
    )
    subparsers.add_parser(
        "deploy-aws-ingestion",
        help="Build the ingestion image and deploy it to AWS App Runner; refresh its runtime settings.",
    )
    subparsers.add_parser(
        "deploy-azure",
        help="Deploy the Azure anomaly app to Azure Container Apps and refresh its runtime settings.",
    )
    subparsers.add_parser(
        "deploy-gcp",
        help="Build the GCP risk image and deploy it to Cloud Run; refresh its runtime settings.",
    )
    subparsers.add_parser("bootstrap", help="Build, push, and deploy every cloud peer in dependency order.")
    subparsers.add_parser("status", help="Check the current public health endpoints.")
    subparsers.add_parser("go-live", help="Provision all clouds and run bootstrap end-to-end.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {"package-azure", "package-webapp"}:
        print(str(package_azure_containerapp_context()))
        return
    if args.command == "package-gcp":
        print(str(package_gcp_cloudrun_context()))
        return
    if args.command == "package-aws-registry":
        print(str(package_apprunner_registry_context()))
        return
    if args.command == "package-aws-ingestion":
        print(str(package_apprunner_ingestion_context()))
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
    if args.command == "deploy-aws-registry":
        aws = load_manifest("aws")
        if not aws or aws.get("type") != "app_runner":
            raise SystemExit("Run provision-aws first to create the App Runner manifest.")
        block = deploy_aws_app_runner(aws, kind="registry", endpoints={})
        print(json.dumps({"registry": block, "deployed": True}, indent=2))
        return
    if args.command == "deploy-aws-ingestion":
        aws = load_manifest("aws")
        if not aws or aws.get("type") != "app_runner":
            raise SystemExit("Run provision-aws first to create the App Runner manifest.")
        registry_url = aws.get("registry", {}).get("base_url")
        if not registry_url:
            raise SystemExit("Registry base_url missing; run deploy-aws-registry before deploy-aws-ingestion.")
        gcp = load_manifest("gcp")
        azure = load_manifest("azure")
        endpoints = {"REGISTRY_URL": registry_url}
        if gcp and gcp.get("base_url"):
            endpoints["RISK_URL"] = gcp["base_url"]
        if azure and azure.get("base_url"):
            endpoints["ANOMALY_URL"] = azure["base_url"]
        block = deploy_aws_app_runner(aws, kind="ingestion", endpoints=endpoints)
        print(json.dumps({"ingestion": block, "deployed": True}, indent=2))
        return
    if args.command == "deploy-azure":
        azure = load_manifest("azure")
        aws = load_manifest("aws")
        gcp = load_manifest("gcp")
        if not azure or not azure.get("app_name") or not aws or not gcp:
            raise SystemExit("Missing aws/gcp/azure manifests required for Azure deployment.")
        registry_url = aws.get("registry", {}).get("base_url")
        ingestion_url = aws.get("ingestion", {}).get("base_url")
        risk_url = gcp.get("base_url")
        if not registry_url or not ingestion_url:
            raise SystemExit(
                "AWS App Runner base_urls missing; run deploy-aws-registry and deploy-aws-ingestion first."
            )
        if not risk_url:
            raise SystemExit("GCP Cloud Run base_url missing; run deploy-gcp before deploy-azure.")
        azure = deploy_azure_container_app(
            azure,
            {
                "REGISTRY_URL": registry_url,
                "INGESTION_URL": ingestion_url,
                "RISK_URL": risk_url,
            },
        )
        print(json.dumps({"azure": azure, "deployed": True}, indent=2))
        return
    if args.command == "deploy-gcp":
        gcp = load_manifest("gcp")
        aws = load_manifest("aws")
        azure = load_manifest("azure")
        if not gcp or not gcp.get("service_name") or not aws:
            raise SystemExit("Missing aws/gcp manifests required for Cloud Run deployment.")
        registry_url = aws.get("registry", {}).get("base_url")
        ingestion_url = aws.get("ingestion", {}).get("base_url")
        if not registry_url or not ingestion_url:
            raise SystemExit(
                "AWS App Runner base_urls missing; run deploy-aws-registry and deploy-aws-ingestion first."
            )
        endpoints = {"REGISTRY_URL": registry_url, "INGESTION_URL": ingestion_url}
        if azure and azure.get("base_url"):
            endpoints["ANOMALY_URL"] = azure["base_url"]
        gcp = deploy_gcp_cloud_run(gcp, endpoints)
        print(json.dumps({"gcp": gcp, "deployed": True}, indent=2))
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
