"""S3 service for cloud storage (Future implementation)"""

# This module is a stub for future AWS S3 integration
# Current version uses local filesystem storage
#
# To implement S3 storage in the future:
# 1. Use boto3 S3 client
# 2. Replace local file operations with S3 upload/download
# 3. Update document file_path to use S3 URIs (s3://bucket/key)
# 4. Implement pre-signed URLs for secure file access

import logging

logger = logging.getLogger(__name__)


class S3Service:
    """AWS S3 storage service (future implementation)"""

    def __init__(self):
        logger.info("S3Service is not implemented - using local filesystem storage")

    def upload_file(self, local_path: str, s3_key: str) -> bool:
        """Upload file to S3 (not implemented)"""
        raise NotImplementedError("S3 upload not implemented - using local storage")

    def download_file(self, s3_key: str, local_path: str) -> bool:
        """Download file from S3 (not implemented)"""
        raise NotImplementedError("S3 download not implemented - using local storage")

    def delete_file(self, s3_key: str) -> bool:
        """Delete file from S3 (not implemented)"""
        raise NotImplementedError("S3 delete not implemented - using local storage")

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate pre-signed URL (not implemented)"""
        raise NotImplementedError("S3 presigned URLs not implemented - using local storage")
