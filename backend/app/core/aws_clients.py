import boto3
from botocore.config import Config
from app.core.config import get_settings


def get_boto3_config() -> Config:
    settings = get_settings()
    return Config(
        region_name=settings.AWS_REGION,
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=30,
        read_timeout=60,
    )


def get_s3_client():
    return boto3.client("s3", config=get_boto3_config())


def get_async_s3_client():
    import aiobotocore.session

    session = aiobotocore.session.get_session()
    return session.create_client("s3", config=get_boto3_config())


def get_sqs_client():
    return boto3.client("sqs", config=get_boto3_config())


def get_async_sqs_client():
    import aiobotocore.session

    session = aiobotocore.session.get_session()
    return session.create_client("sqs", config=get_boto3_config())