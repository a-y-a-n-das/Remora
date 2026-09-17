#!/usr/bin/env python3
"""
S3 to SQS Notification Configuration Script

This script configures an S3 bucket to send ObjectCreated events to an SQS queue.

Usage:
    python scripts/setup_s3_sqs_notification.py

Environment variables required:
    AWS_REGION (default: us-east-1)
    AWS_ENDPOINT_URL (optional, for LocalStack)
    S3_BUCKET (required)
    SQS_QUEUE_URL (required)

The script will:
1. Get the SQS queue ARN from the queue URL
2. Configure the S3 bucket notification to send ObjectCreated events to the SQS queue
3. Only notify for objects with prefix "memories/"
"""

import os
import sys
import boto3
from botocore.config import Config


def get_boto3_config():
    return Config(
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=30,
        read_timeout=60,
    )


def main():
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    region = os.getenv("AWS_REGION", "us-east-1")
    bucket = os.getenv("S3_BUCKET")
    queue_url = os.getenv("SQS_QUEUE_URL")

    if not bucket:
        print("ERROR: S3_BUCKET environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not queue_url:
        print("ERROR: SQS_QUEUE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)

    s3 = boto3.client("s3", endpoint_url=endpoint_url, config=get_boto3_config())
    sqs = boto3.client("sqs", endpoint_url=endpoint_url, config=get_boto3_config())

    try:
        queue_attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["QueueArn"],
        )
        queue_arn = queue_attrs["Attributes"]["QueueArn"]
        print(f"SQS Queue ARN: {queue_arn}")
    except Exception as e:
        print(f"ERROR: Failed to get SQS queue ARN: {e}", file=sys.stderr)
        sys.exit(1)

    notification_config = {
        "QueueConfigurations": [
            {
                "Id": "memory-processing",
                "QueueArn": queue_arn,
                "Events": ["s3:ObjectCreated:*"],
                "Filter": {
                    "Key": {
                        "FilterRules": [
                            {"Name": "prefix", "Value": "memories/"}
                        ]
                    }
                }
            }
        ]
    }

    try:
        s3.put_bucket_notification_configuration(
            Bucket=bucket,
            NotificationConfiguration=notification_config,
        )
        print(f"SUCCESS: Configured S3 bucket '{bucket}' to notify SQS queue for ObjectCreated events with prefix 'memories/'")
    except Exception as e:
        print(f"ERROR: Failed to configure S3 bucket notification: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        response = s3.get_bucket_notification_configuration(Bucket=bucket)
        print(f"VERIFIED: Current notification configuration: {response}")
    except Exception as e:
        print(f"WARNING: Could not verify configuration: {e}")


if __name__ == "__main__":
    main()