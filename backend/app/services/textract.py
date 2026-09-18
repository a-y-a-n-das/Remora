import time
from typing import Optional
from app.core.aws_clients import get_textract_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TextractService:
    def __init__(self):
        self.client = get_textract_client()
        self.settings = get_settings()

    def extract_text(self, s3_bucket: str, s3_key: str) -> Optional[str]:
        start_time = time.time()
        try:
            response = self.client.detect_document_text(
                Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}}
            )

            text_blocks = []
            for block in response.get("Blocks", []):
                if block["BlockType"] == "LINE":
                    text_blocks.append(block["Text"])

            full_text = "\n".join(text_blocks)
            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "textract_ocr_completed",
                s3_key=s3_key,
                text_length=len(full_text),
                duration_ms=duration_ms,
            )
            return full_text if full_text else None

        except self.client.exceptions.InvalidParameterException as e:
            logger.error("textract_invalid_parameter", s3_key=s3_key, error=str(e))
            return None
        except self.client.exceptions.ProvisionedThroughputExceededException as e:
            logger.error("textract_throttled", s3_key=s3_key, error=str(e))
            raise
        except Exception as e:
            logger.error("textract_ocr_failed", s3_key=s3_key, error=str(e))
            raise


textract_service = TextractService()