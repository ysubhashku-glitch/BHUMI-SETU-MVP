import hashlib
import io
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from app.core.storage import S3DocumentStorage, MinioDocumentStorage, StorageException


class MockS3Client:
    """Mock boto3 S3 client for in-memory object storage testing."""
    def __init__(self):
        self.objects = {}  # (bucket, key) -> {"body": bytes, "metadata": dict, "content_type": str}

    def put_object(self, Bucket, Key, Body, ContentType, Metadata):
        content = Body if isinstance(Body, bytes) else Body.read()
        self.objects[(Bucket, Key)] = {
            "body": content,
            "metadata": Metadata,
            "content_type": ContentType
        }
        return {"ETag": '"mock-etag"'}

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject"
            )
        data = self.objects[(Bucket, Key)]
        return {
            "Body": io.BytesIO(data["body"]),
            "ContentType": data["content_type"],
            "ContentLength": len(data["body"]),
            "Metadata": data["metadata"]
        }

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject"
            )
        data = self.objects[(Bucket, Key)]
        return {
            "ContentType": data["content_type"],
            "ContentLength": len(data["body"]),
            "Metadata": data["metadata"]
        }

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        return {"DeleteMarker": True}

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
        bucket = Params.get("Bucket")
        key = Params.get("Key")
        return f"https://s3.ap-south-1.amazonaws.com/{bucket}/{key}?expires={ExpiresIn}&signature=mock-sig"


def test_s3_storage_put_and_get():
    mock_client = MockS3Client()
    storage = S3DocumentStorage(bucket_name="test-vault-bucket", client=mock_client)

    sample_bytes = b"%PDF-1.4 simulated pdf document content for staging test"
    res = storage.put(
        content=sample_bytes,
        destination_name="sample_deed.pdf",
        mime_type="application/pdf",
        metadata={"case_id": "test-case-123"}
    )

    expected_hash = hashlib.sha256(sample_bytes).hexdigest()
    assert res["sha256_hash"] == expected_hash
    assert res["file_size_bytes"] == len(sample_bytes)
    assert res["storage_reference"] == f"s3://test-vault-bucket/{expected_hash}.pdf"

    # Retrieve and verify
    retrieved = storage.get(res["storage_reference"])
    assert retrieved == sample_bytes


def test_s3_storage_sha256_integrity_check():
    mock_client = MockS3Client()
    storage = S3DocumentStorage(bucket_name="test-vault-bucket", client=mock_client)

    sample_bytes = b"original uncorrupted payload"
    res = storage.put(content=sample_bytes, destination_name="doc.bin", mime_type="application/octet-stream")

    # Manually tamper with the stored object in S3
    key = f"{res['sha256_hash']}.bin"
    mock_client.objects[("test-vault-bucket", key)]["body"] = b"tampered corrupt payload"

    with pytest.raises(StorageException, match="SHA-256 integrity check failed"):
        storage.get(res["storage_reference"])


def test_s3_storage_exists_and_delete():
    mock_client = MockS3Client()
    storage = S3DocumentStorage(bucket_name="test-vault-bucket", client=mock_client)

    content = b"test payload"
    res = storage.put(content=content, destination_name="doc.txt", mime_type="text/plain")

    assert storage.exists(res["storage_reference"]) is True
    assert storage.exists("s3://test-vault-bucket/nonexistent.bin") is False

    # Delete
    assert storage.delete(res["storage_reference"]) is True
    assert storage.exists(res["storage_reference"]) is False


def test_s3_storage_metadata():
    mock_client = MockS3Client()
    storage = S3DocumentStorage(bucket_name="test-vault-bucket", client=mock_client)

    content = b"hello metadata"
    res = storage.put(content=content, destination_name="meta.txt", mime_type="text/plain")

    meta = storage.get_metadata(res["storage_reference"])
    assert meta["file_size_bytes"] == len(content)
    assert meta["mime_type"] == "text/plain"


def test_s3_storage_presigned_url():
    mock_client = MockS3Client()
    storage = S3DocumentStorage(bucket_name="test-vault-bucket", client=mock_client)

    res = storage.put(content=b"test", destination_name="doc.pdf", mime_type="application/pdf")
    url = storage.generate_download_reference(res["storage_reference"], expiry_seconds=1800)

    assert "https://s3.ap-south-1.amazonaws.com/test-vault-bucket/" in url
    assert "expires=1800" in url


def test_minio_document_storage_inheritance():
    mock_client = MockS3Client()
    storage = MinioDocumentStorage(
        bucket_name="minio-local-vault",
        endpoint_url="http://localhost:9000",
        client=mock_client
    )

    res = storage.put(content=b"minio content", destination_name="file.bin", mime_type="application/octet-stream")
    assert res["storage_reference"] == f"s3://minio-local-vault/{res['sha256_hash']}.bin"
    assert storage.get(res["storage_reference"]) == b"minio content"
