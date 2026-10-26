import os
import hashlib
import json
import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Any
from app.config import settings
from app.core.exceptions import BhumiSetuException

class StorageException(BhumiSetuException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code="STORAGE_ERROR",
            message=message,
            status_code=500,
            details=details
        )

class SecurityValidationException(BhumiSetuException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(
            code="SECURITY_VALIDATION_ERROR",
            message=message,
            status_code=400,
            details=details
        )

# MIME Magic Bytes Signatures
MIME_SIGNATURES = [
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),
    (b"MM\x00*", "image/tiff"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/webp"
}

def detect_mime_type(content: bytes, declared_mime: Optional[str] = None) -> str:
    """
    Sniffs raw bytes for magic file signatures. Never trusts client-supplied MIME blindly.
    """
    if not content:
        raise SecurityValidationException("Empty file content received.")

    # Check WEBP
    if len(content) > 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"

    for prefix, mime in MIME_SIGNATURES:
        if content.startswith(prefix):
            return mime

    # Fallback to declared MIME if recognized in allowed set, else reject
    if declared_mime and declared_mime in ALLOWED_MIME_TYPES:
        return declared_mime

    return "application/octet-stream"

def validate_upload_security(
    content: bytes,
    declared_filename: str,
    declared_mime: str,
    max_size_bytes: int = 50 * 1024 * 1024  # 50 MB
) -> Tuple[str, str, int]:
    """
    Validates MIME type, extension, and file size limits.
    Returns: (detected_mime, sanitized_filename, file_size_bytes)
    """
    file_size = len(content)
    if file_size == 0:
        raise SecurityValidationException("File content cannot be empty.")
    if file_size > max_size_bytes:
        raise SecurityValidationException(
            f"File size exceeds maximum permitted threshold of {max_size_bytes // (1024*1024)}MB."
        )

    detected_mime = detect_mime_type(content, declared_mime)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise SecurityValidationException(f"Unsupported MIME type: {detected_mime}")

    # Sanitize filename cross-platform (handles both Windows \ and POSIX / separators)
    normalized_name = declared_filename.replace("\\", "/")
    sanitized_filename = os.path.basename(normalized_name).replace("..", "").replace("/", "").replace("\\", "").strip() or "document"
    return detected_mime, sanitized_filename, file_size


class DocumentStorage(ABC):
    """
    Canonical Phase 3 DocumentStorage interface.
    The domain layer must not depend directly on filesystem APIs or S3 SDKs.
    """
    @abstractmethod
    def put(
        self,
        content: bytes,
        destination_name: str,
        mime_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Stores file immutably.
        Returns: {
            "storage_reference": str,
            "sha256_hash": str,
            "file_size_bytes": int,
            "mime_type": str,
            "metadata": dict
        }
        """
        pass

    @abstractmethod
    def get(self, storage_reference: str) -> bytes:
        """Retrieves raw binary file content."""
        pass

    @abstractmethod
    def delete(self, storage_reference: str) -> bool:
        """
        Deletes object if allowed by retention policy.
        Note: Primary evidence is immutable; used for temporary staging or test artifacts.
        """
        pass

    @abstractmethod
    def exists(self, storage_reference: str) -> bool:
        """Checks if the object exists in storage."""
        pass

    @abstractmethod
    def get_metadata(self, storage_reference: str) -> Dict[str, Any]:
        """Retrieves metadata associated with the stored object."""
        pass

    @abstractmethod
    def generate_download_reference(self, storage_reference: str, expiry_seconds: int = 3600) -> str:
        """Generates time-limited private signed access URL/reference."""
        pass


class LocalDocumentStorage(DocumentStorage):
    """Local filesystem storage implementation for development and testing."""
    def __init__(self, storage_dir: str):
        self.storage_dir = os.path.abspath(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.meta_dir = os.path.join(self.storage_dir, ".metadata")
        os.makedirs(self.meta_dir, exist_ok=True)

    def _get_path_from_ref(self, storage_reference: str) -> str:
        if storage_reference.startswith("file://"):
            return storage_reference[7:]
        return os.path.join(self.storage_dir, storage_reference)

    def put(
        self,
        content: bytes,
        destination_name: str,
        mime_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        file_size = len(content)
        sha256_hash = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(destination_name)[1] if destination_name else ".bin"
        stored_filename = f"{sha256_hash}{ext}"
        storage_path = os.path.join(self.storage_dir, stored_filename)

        # File is written once (immutability)
        if not os.path.exists(storage_path):
            with open(storage_path, "wb") as f:
                f.write(content)

        # Persist companion metadata
        meta_payload = {
            "sha256_hash": sha256_hash,
            "original_filename": destination_name,
            "mime_type": mime_type,
            "file_size_bytes": file_size,
            "created_at": time.time(),
            "custom_metadata": metadata or {}
        }
        meta_path = os.path.join(self.meta_dir, f"{sha256_hash}.json")
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta_payload, mf)

        storage_uri = f"file://{storage_path}"
        return {
            "storage_reference": storage_uri,
            "sha256_hash": sha256_hash,
            "file_size_bytes": file_size,
            "mime_type": mime_type,
            "metadata": meta_payload
        }

    def get(self, storage_reference: str) -> bytes:
        path = self._get_path_from_ref(storage_reference)
        if not os.path.exists(path):
            raise StorageException(f"Object not found in local storage: {path}")
        with open(path, "rb") as f:
            return f.read()

    def delete(self, storage_reference: str) -> bool:
        path = self._get_path_from_ref(storage_reference)
        if os.path.exists(path):
            os.remove(path)
            # Remove metadata if exists
            filename = os.path.basename(path)
            hash_part = os.path.splitext(filename)[0]
            meta_path = os.path.join(self.meta_dir, f"{hash_part}.json")
            if os.path.exists(meta_path):
                os.remove(meta_path)
            return True
        return False

    def exists(self, storage_reference: str) -> bool:
        path = self._get_path_from_ref(storage_reference)
        return os.path.exists(path)

    def get_metadata(self, storage_reference: str) -> Dict[str, Any]:
        path = self._get_path_from_ref(storage_reference)
        if not os.path.exists(path):
            raise StorageException(f"Object not found: {path}")
        filename = os.path.basename(path)
        hash_part = os.path.splitext(filename)[0]
        meta_path = os.path.join(self.meta_dir, f"{hash_part}.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as mf:
                return json.load(mf)
        # Fallback to filesystem stat
        stat = os.stat(path)
        return {
            "sha256_hash": hash_part,
            "file_size_bytes": stat.st_size,
            "created_at": stat.st_ctime,
            "storage_reference": storage_reference
        }

    def generate_download_reference(self, storage_reference: str, expiry_seconds: int = 3600) -> str:
        # In local storage, return internal file URI
        return storage_reference


try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    BOTO3_AVAILABLE = False


class S3DocumentStorage(DocumentStorage):
    """
    Production AWS S3 / MinIO object storage adapter.
    Preserves immutability via content-hashed keys, calculates and verifies SHA-256 digests,
    and returns time-limited private signed URLs for downloads.
    """
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        use_ssl: Optional[bool] = None,
        client: Any = None
    ):
        self.bucket_name = bucket_name or settings.AWS_S3_BUCKET
        self.region_name = region_name or settings.AWS_REGION
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL
        self.access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY
        self.use_ssl = use_ssl if use_ssl is not None else settings.S3_USE_SSL
        self._client = client
        self.is_connected = bool(self.bucket_name)

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not BOTO3_AVAILABLE:
            raise StorageException("boto3 is required for S3/MinIO storage but is not installed.")
        client_kwargs = {
            "region_name": self.region_name,
            "use_ssl": self.use_ssl
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key_id and self.secret_access_key:
            client_kwargs["aws_access_key_id"] = self.access_key_id
            client_kwargs["aws_secret_access_key"] = self.secret_access_key

        self._client = boto3.client("s3", **client_kwargs)
        return self._client

    def ensure_bucket_exists(self) -> bool:
        """
        Idempotently verifies or creates the configured S3 / MinIO bucket.
        Guarantees that staging object vault is initialized before upload operations.
        """
        if not self.bucket_name:
            raise StorageException("Cannot ensure bucket: AWS_S3_BUCKET is not configured.")
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", ""))
            if error_code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    kwargs = {"Bucket": self.bucket_name}
                    if self.region_name and self.region_name != "us-east-1":
                        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.region_name}
                    client.create_bucket(**kwargs)
                    return True
                except Exception as ce:
                    raise StorageException(f"Failed to create bucket '{self.bucket_name}': {str(ce)}")
            raise StorageException(f"Failed to verify bucket '{self.bucket_name}': {str(e)}")

    def _extract_key(self, storage_reference: str) -> str:
        if storage_reference.startswith("s3://"):
            parts = storage_reference[5:].split("/", 1)
            return parts[1] if len(parts) == 2 else parts[0]
        return storage_reference

    def put(
        self,
        content: bytes,
        destination_name: str,
        mime_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.bucket_name:
            raise StorageException("S3 Object Storage is NOT_CONFIGURED. Please provide AWS_S3_BUCKET.")
        file_size = len(content)
        sha256_hash = hashlib.sha256(content).hexdigest()
        ext = os.path.splitext(destination_name)[1] if destination_name else ".bin"
        key = f"{sha256_hash}{ext}"

        client = self._get_client()
        s3_meta = {
            "sha256": sha256_hash,
            "original_filename": destination_name or "document",
            "filesize": str(file_size)
        }
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    s3_meta[str(k).lower()] = str(v)

        try:
            client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content,
                ContentType=mime_type,
                Metadata=s3_meta
            )
        except Exception as e:
            raise StorageException(f"Failed to store object in S3: {str(e)}")

        storage_uri = f"s3://{self.bucket_name}/{key}"
        return {
            "storage_reference": storage_uri,
            "sha256_hash": sha256_hash,
            "file_size_bytes": file_size,
            "mime_type": mime_type,
            "metadata": {
                "sha256_hash": sha256_hash,
                "original_filename": destination_name,
                "mime_type": mime_type,
                "file_size_bytes": file_size,
                "bucket": self.bucket_name,
                "key": key
            }
        }

    def get(self, storage_reference: str) -> bytes:
        if not self.bucket_name:
            raise StorageException("S3 Object Storage is NOT_CONFIGURED.")
        key = self._extract_key(storage_reference)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self.bucket_name, Key=key)
            content = resp["Body"].read()
        except Exception as e:
            raise StorageException(f"Failed to retrieve object from S3: {str(e)}")

        # Verify SHA-256 integrity
        actual_hash = hashlib.sha256(content).hexdigest()
        expected_hash = os.path.splitext(os.path.basename(key))[0]
        if len(expected_hash) == 64 and actual_hash != expected_hash:
            raise StorageException(
                f"S3 Object SHA-256 integrity check failed. Expected {expected_hash}, got {actual_hash}"
            )
        return content

    def delete(self, storage_reference: str) -> bool:
        if not self.bucket_name:
            raise StorageException("S3 Object Storage is NOT_CONFIGURED.")
        key = self._extract_key(storage_reference)
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            raise StorageException(f"Failed to delete object from S3: {str(e)}")

    def exists(self, storage_reference: str) -> bool:
        if not self.bucket_name:
            return False
        key = self._extract_key(storage_reference)
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageException(f"Error checking S3 object existence: {str(e)}")
        except Exception:
            return False

    def get_metadata(self, storage_reference: str) -> Dict[str, Any]:
        if not self.bucket_name:
            raise StorageException("S3 Object Storage is NOT_CONFIGURED.")
        key = self._extract_key(storage_reference)
        client = self._get_client()
        try:
            head = client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                "sha256_hash": head.get("Metadata", {}).get("sha256", os.path.splitext(key)[0]),
                "file_size_bytes": head.get("ContentLength", 0),
                "mime_type": head.get("ContentType", "application/octet-stream"),
                "storage_reference": storage_reference,
                "metadata": head.get("Metadata", {})
            }
        except Exception as e:
            raise StorageException(f"Failed to retrieve metadata from S3: {str(e)}")

    def generate_download_reference(self, storage_reference: str, expiry_seconds: int = 3600) -> str:
        if not self.bucket_name:
            raise StorageException("S3 Object Storage is NOT_CONFIGURED.")
        key = self._extract_key(storage_reference)
        client = self._get_client()
        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expiry_seconds
            )
            return url
        except Exception as e:
            raise StorageException(f"Failed to generate presigned S3 URL: {str(e)}")


class MinioDocumentStorage(S3DocumentStorage):
    """S3-compatible on-premise / MinIO storage adapter."""
    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        use_ssl: Optional[bool] = None,
        client: Any = None
    ):
        super().__init__(
            bucket_name=bucket_name or settings.AWS_S3_BUCKET or "bhumisetu-vault",
            region_name=region_name,
            endpoint_url=endpoint_url or settings.S3_ENDPOINT_URL or "http://minio:9000",
            access_key_id=access_key_id or settings.AWS_ACCESS_KEY_ID or "minioadmin",
            secret_access_key=secret_access_key or settings.AWS_SECRET_ACCESS_KEY or "minioadmin",
            use_ssl=use_ssl if use_ssl is not None else settings.S3_USE_SSL,
            client=client
        )


# Backwards compatibility wrappers
class BaseStorageAdapter(ABC):
    @abstractmethod
    def store_file(self, content: bytes, original_filename: str, mime_type: str) -> Tuple[str, str, int]:
        pass

    @abstractmethod
    def retrieve_file(self, storage_uri: str) -> bytes:
        pass

    @abstractmethod
    def generate_access_url(self, storage_uri: str, expiry_seconds: int = 3600) -> str:
        pass


class LocalStorageAdapter(BaseStorageAdapter):
    def __init__(self, storage_dir: str):
        self._doc_storage = LocalDocumentStorage(storage_dir=storage_dir)

    def store_file(self, content: bytes, original_filename: str, mime_type: str) -> Tuple[str, str, int]:
        res = self._doc_storage.put(content, original_filename, mime_type)
        return res["storage_reference"], res["sha256_hash"], res["file_size_bytes"]

    def retrieve_file(self, storage_uri: str) -> bytes:
        return self._doc_storage.get(storage_uri)

    def generate_access_url(self, storage_uri: str, expiry_seconds: int = 3600) -> str:
        return self._doc_storage.generate_download_reference(storage_uri, expiry_seconds)


class S3StorageAdapter(BaseStorageAdapter):
    def __init__(self, bucket_name: Optional[str] = None):
        self._doc_storage = S3DocumentStorage(bucket_name=bucket_name)

    def store_file(self, content: bytes, original_filename: str, mime_type: str) -> Tuple[str, str, int]:
        res = self._doc_storage.put(content, original_filename, mime_type)
        return res["storage_reference"], res["sha256_hash"], res["file_size_bytes"]

    def retrieve_file(self, storage_uri: str) -> bytes:
        return self._doc_storage.get(storage_uri)

    def generate_access_url(self, storage_uri: str, expiry_seconds: int = 3600) -> str:
        return self._doc_storage.generate_download_reference(storage_uri, expiry_seconds)


def get_document_storage() -> DocumentStorage:
    """Canonical factory for Phase 3 DocumentStorage."""
    if settings.STORAGE_ADAPTER == "s3":
        return S3DocumentStorage()
    elif settings.STORAGE_ADAPTER == "minio":
        return MinioDocumentStorage()
    return LocalDocumentStorage(storage_dir=settings.STORAGE_DIR)


def get_storage_adapter() -> BaseStorageAdapter:
    """Backwards-compatible factory."""
    if settings.STORAGE_ADAPTER in ("s3", "minio"):
        return S3StorageAdapter(bucket_name=settings.AWS_S3_BUCKET)
    return LocalStorageAdapter(storage_dir=settings.STORAGE_DIR)
