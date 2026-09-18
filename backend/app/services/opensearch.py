import json
import time
from typing import Optional, Dict, Any, List
from app.core.aws_clients import get_opensearch_client
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenSearchService:
    def __init__(self):
        self.client = get_opensearch_client()
        self.settings = get_settings()
        self.index_name = self.settings.OPENSEARCH_INDEX
        self.embedding_dimension = self.settings.BEDROCK_EMBEDDING_DIMENSION

    def is_available(self) -> bool:
        return self.client is not None

    def ensure_index(self) -> bool:
        if not self.is_available():
            logger.warning("opensearch_not_configured")
            return False

        try:
            exists = self.client.indices.exists(index=self.index_name)
            if not exists:
                mapping = self._get_index_mapping()
                self.client.indices.create(index=self.index_name, body=mapping)
                logger.info("opensearch_index_created", index=self.index_name)
            return True
        except Exception as e:
            logger.error("opensearch_ensure_index_failed", error=str(e))
            return False

    def _get_index_mapping(self) -> Dict[str, Any]:
        return {
            "settings": {
                "index": {
                    "knn": True,
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": "1s",
                }
            },
            "mappings": {
                "properties": {
                    "memory_id": {"type": "keyword"},
                    "s3_key": {"type": "keyword"},
                    "file": {
                        "properties": {
                            "original_filename": {"type": "keyword"},
                            "mime_type": {"type": "keyword"},
                            "size_bytes": {"type": "long"},
                        }
                    },
                    "time": {
                        "properties": {
                            "uploaded_at": {"type": "date"},
                            "captured_at": {"type": "date"},
                        }
                    },
                    "text": {
                        "properties": {
                            "ocr": {"type": "text", "analyzer": "standard"},
                        }
                    },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self.embedding_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {"ef_construction": 128, "m": 24},
                        },
                    },
                    "processing": {
                        "properties": {
                            "status": {"type": "keyword"},
                            "updated_at": {"type": "date"},
                            "error_message": {"type": "text"},
                        }
                    },
                    "moderation": {
                        "properties": {
                            "status": {"type": "keyword"},
                            "updated_at": {"type": "date"},
                            "flagged_reason": {"type": "text"},
                        }
                    },
                }
            },
        }

    def index_memory(self, document: Dict[str, Any]) -> bool:
        if not self.is_available():
            logger.warning("opensearch_not_available_skip_index")
            return False

        try:
            self.client.index(
                index=self.index_name,
                id=document["memory_id"],
                body=document,
                refresh=True,
            )
            logger.info("memory_indexed", memory_id=document["memory_id"])
            return True
        except Exception as e:
            logger.error("opensearch_index_failed", memory_id=document.get("memory_id"), error=str(e))
            return False

    def update_memory_status(
        self,
        memory_id: str,
        processing_status: str,
        error_message: Optional[str] = None,
        moderation_status: Optional[str] = None,
    ) -> bool:
        if not self.is_available():
            return False

        try:
            doc = {
                "processing": {"status": processing_status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            }
            if error_message:
                doc["processing"]["error_message"] = error_message
            if moderation_status:
                doc["moderation"] = {"status": moderation_status, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

            self.client.update(
                index=self.index_name,
                id=memory_id,
                body={"doc": doc},
                refresh=True,
            )
            logger.info("memory_status_updated", memory_id=memory_id, processing_status=processing_status)
            return True
        except Exception as e:
            logger.error("opensearch_update_failed", memory_id=memory_id, error=str(e))
            return False

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        try:
            response = self.client.get(index=self.index_name, id=memory_id)
            return response["_source"]
        except Exception:
            return None

    def delete_memory(self, memory_id: str) -> bool:
        if not self.is_available():
            return False

        try:
            self.client.delete(index=self.index_name, id=memory_id, refresh=True)
            logger.info("memory_deleted_from_opensearch", memory_id=memory_id)
            return True
        except Exception as e:
            logger.error("opensearch_delete_failed", memory_id=memory_id, error=str(e))
            return False

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []

        must_clauses = [
            {"term": {"processing.status": "ready"}},
            {"term": {"moderation.status": "approved"}},
        ]

        should_clauses = []

        if query_text:
            should_clauses.append(
                {
                    "match": {
                        "text.ocr": {
                            "query": query_text,
                            "boost": 2.0,
                        }
                    }
                }
            )
            should_clauses.append(
                {
                    "match": {
                        "file.original_filename": {
                            "query": query_text,
                            "boost": 1.0,
                        }
                    }
                }
            )

        if query_embedding:
            should_clauses.append(
                {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": limit * 2,
                        }
                    }
                }
            )

        query = {
            "size": limit,
            "query": {
                "bool": {
                    "must": must_clauses,
                    "should": should_clauses,
                    "minimum_should_match": 1,
                }
            },
            "_source": {"excludes": ["embedding"]},
        }

        try:
            response = self.client.search(index=self.index_name, body=query)
            hits = response["hits"]["hits"]
            results = []
            for hit in hits:
                source = hit["_source"]
                source["_score"] = hit["_score"]
                results.append(source)
            logger.info("hybrid_search_completed", query=query_text[:50], results=len(results))
            return results
        except Exception as e:
            logger.error("hybrid_search_failed", error=str(e))
            return []


opensearch_service = OpenSearchService()