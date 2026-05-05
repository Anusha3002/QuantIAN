from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from shared.config import ServiceSettings

from .json_state import load_json_file, save_json_file


class JsonStateStore(Protocol):
    def load_json(self, default: Any) -> Any:
        ...

    def save_json(self, payload: Any) -> None:
        ...


class FileJsonStateStore:
    def __init__(self, path: str | Path | None) -> None:
        self.path = Path(path) if path is not None else None

    def load_json(self, default: Any) -> Any:
        return load_json_file(self.path, default)

    def save_json(self, payload: Any) -> None:
        save_json_file(self.path, payload)


class AzureBlobJsonStateStore:
    def __init__(self, *, connection_string: str, container_name: str, blob_name: str) -> None:
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_name = blob_name
        self._blob_client: Any | None = None

    def load_json(self, default: Any) -> Any:
        _, resource_exists_error, resource_not_found_error = self._sdk()
        try:
            payload = self._client().download_blob().readall()
        except resource_not_found_error:
            return default
        except resource_exists_error:
            return default
        if not payload:
            return default
        return json.loads(payload.decode("utf-8"))

    def save_json(self, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self._client().upload_blob(body, overwrite=True)

    def _client(self) -> Any:
        if self._blob_client is not None:
            return self._blob_client

        blob_service_client_cls, resource_exists_error, _ = self._sdk()
        service_client = blob_service_client_cls.from_connection_string(self.connection_string)
        container_client = service_client.get_container_client(self.container_name)
        try:
            container_client.create_container()
        except resource_exists_error:
            pass
        self._blob_client = container_client.get_blob_client(self.blob_name)
        return self._blob_client

    @staticmethod
    def _sdk() -> tuple[Any, type[Exception], type[Exception]]:
        try:
            from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
            from azure.storage.blob import BlobServiceClient
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "azure-storage-blob is required when STORAGE_BACKEND=azure_blob."
            ) from exc
        return BlobServiceClient, ResourceExistsError, ResourceNotFoundError


def build_json_state_store(
    *,
    settings: ServiceSettings,
    state_path: str | Path | None,
    service_name: str,
    default_blob_name: str,
) -> JsonStateStore:
    backend = settings.storage_backend.lower()
    if backend not in {"azure_blob", "blob", "azureblob"}:
        return FileJsonStateStore(state_path)

    service_prefix = service_name.upper().replace("-", "_")
    connection_string = (
        os.getenv(f"{service_prefix}_STORAGE_CONNECTION_STRING")
        or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        or ""
    )
    if not connection_string:
        raise RuntimeError(
            f"Missing Azure storage connection string for {service_name}. "
            f"Set {service_prefix}_STORAGE_CONNECTION_STRING or AZURE_STORAGE_CONNECTION_STRING."
        )

    container_name = os.getenv(
        f"{service_prefix}_STORAGE_CONTAINER",
        os.getenv("AZURE_STORAGE_CONTAINER", "quantian-state"),
    )
    blob_name = os.getenv(
        f"{service_prefix}_STATE_BLOB_NAME",
        default_blob_name,
    )
    return AzureBlobJsonStateStore(
        connection_string=connection_string,
        container_name=container_name,
        blob_name=blob_name,
    )
