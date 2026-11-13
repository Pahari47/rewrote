import os
import boto3
from botocore.config import Config

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
    region_name=os.getenv("S3_REGION"),
    config=Config(
        signature_version="s3v4",
        s3={
            "addressing_style": "path",
        },
    ),
)

BUCKET = os.getenv("S3_BUCKET", "media")
UPLOAD_URL_EXPIRY = int(os.getenv("UPLOAD_URL_EXPIRY", "900"))

def generate_upload_url(object_key: str, content_type: str):
    return s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=UPLOAD_URL_EXPIRY,
    )