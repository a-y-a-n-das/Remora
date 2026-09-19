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


def get_textract_client():
    return boto3.client("textract", config=get_boto3_config())


def get_bedrock_runtime_client():
    return boto3.client("bedrock-runtime", config=get_boto3_config())


def get_s3_vectors_client():
    settings = get_settings()
    return boto3.client(
        "s3vectors",
        config=Config(
            region_name=settings.AWS_REGION,
            retries={"max_attempts": settings.S3_VECTORS_MAX_RETRIES, "mode": "standard"},
            connect_timeout=30,
            read_timeout=60,
        ),
    )


def get_opensearch_client():
    from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

    settings = get_settings()
    if not settings.OPENSEARCH_ENDPOINT:
        return None

    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, settings.AWS_REGION, "aoss")

    host = settings.OPENSEARCH_ENDPOINT.replace("https://", "")

    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
        max_retries=settings.OPENSEARCH_MAX_RETRIES,
        retry_on_timeout=True,
    )