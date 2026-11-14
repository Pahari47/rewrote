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
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "104857600"))
MIN_UPLOAD_SIZE = int(os.getenv("MIN_UPLOAD_SIZE", "1"))

def generate_upload_url(object_key: str):
    return s3_client.generate_presigned_post(
        Bucket=BUCKET,
        Key=object_key,
        Fields={
            "Content-Type": "application/octet-stream",
        },
        Conditions=[
            {"Content-Type": "application/octet-stream"},
            ["content-length-range", MIN_UPLOAD_SIZE, MAX_UPLOAD_SIZE],
        ],
        ExpiresIn=UPLOAD_URL_EXPIRY,
    )

def get_object_metada(object_key: str):
    return s3_client.head_object(
        Bucket=BUCKET,
        Key=object_key,
    )

def read_object_header(object_key: str):
    response = s3_client.get_object(
        Bucket=BUCKET,
        Key=object_key,
        Range="bytes=0-31",
    )

    try:
        return response["Body"].read()
    finally:
        response["Body"].close()

def delete_object(object_key: str):
    s3_client.delete_object(
        Bucket=BUCKET,
        Key=object_key,
    )