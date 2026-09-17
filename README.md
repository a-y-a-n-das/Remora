# REMORA

**Your knowledge, actually retrievable.**

Remora is a personal knowledge management system that ingests your documents, extracts their meaning, and lets you query them in natural language. Upload PDFs, markdown, and text files — then ask questions and get answers grounded in your own content, with citations back to the source.

---

## The Problem

Information accumulates faster than we can organize it. Research papers, meeting notes, technical docs, contracts, and articles pile up across folders, drives, and tools. When you need a specific detail later, you remember *that it exists* but not *where it is*. Traditional search finds filenames and keywords; it doesn't understand context or synthesize answers across documents.

## The Solution

Remora builds a private, local-first knowledge base with semantic search and RAG (Retrieval-Augmented Generation):

1. **Ingest** — Upload documents (PDF, Markdown, TXT) via the web UI or API
2. **Process** — Extract text, chunk intelligently, generate embeddings
3. **Store** — Persist vectors and metadata in a vector database
4. **Query** — Ask questions in natural language
5. **Answer** — Retrieve relevant chunks, feed to an LLM, return a grounded response with source citations

```mermaid
flowchart LR
    A[Upload Document] --> B[Text Extraction]
    B --> C[Chunking]
    C --> D[Embedding Generation]
    D --> E[(Vector Store)]
    F[User Query] --> G[Query Embedding]
    G --> H[Semantic Search]
    H --> E
    E --> I[Retrieved Chunks]
    I --> J[LLM + Context]
    J --> K[Answer + Citations]
```

---

## Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| Document upload (PDF, MD, TXT) | 🟡 Planned | Drag-and-drop UI + REST API |
| Text extraction & chunking | 🟡 Planned | PDF parsing, smart chunking with overlap |
| Embedding generation | 🟡 Planned | Local or API-based embeddings |
| Vector storage & semantic search | 🟡 Planned | pgvector / Qdrant / Pinecone |
| RAG query pipeline | 🟡 Planned | Retrieval → rerank → LLM synthesis |
| Source citations in answers | 🟡 Planned | Inline references to doc chunks |
| User authentication | 🟡 Planned | JWT-based, local accounts |
| Multi-collection organization | 🟡 Planned | Group docs by project/topic |
| Chat-style query interface | 🟡 Planned | Conversational history per collection |

> **Status legend**: 🟢 Implemented · 🟡 Planned · 🔴 Not started

---

## How It Works

### Document Processing Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Upload    │────▶│  Extract    │────▶│   Chunk     │────▶│  Embed      │
│  (API/UI)   │     │  (pdfplumber│     │ (recursive, │     │ (sentence-  │
│             │     │  /markdown) │     │  overlap)   │     │  transformers│
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                    │
                                                                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Metadata   │◀───│  Persist    │◀───│  Vector     │◀───│  Index      │
│  (filename, │     │  to Vector  │     │  Store      │     │  (HNSW/IVF) │
│   page,     │     │  DB         │     │             │     │             │
│   section)  │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Query Pipeline (RAG)

```
User Query
    │
    ▼
┌─────────────────────┐
│  Embed Query        │  (same model as ingestion)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Semantic Search    │  → Top-k chunks by cosine similarity
│  (Vector DB)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Rerank (optional)  │  → Cross-encoder for precision
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Construct Prompt   │  → System prompt + chunks + query
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LLM Generation     │  → Streaming response with citations
│  (local / API)      │
└─────────────────────┘
```

---

## Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend (React + Vite + TypeScript)"]
        UI[Upload / Chat UI]
        Auth[Auth Context]
    end

    subgraph API["Backend (FastAPI / Python)"]
        Router[API Routes]
        AuthSvc[Auth Service]
        Ingest[Ingestion Pipeline]
        Query[Query / RAG Pipeline]
        Collections[Collection Manager]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL + pgvector)]
        Redis[(Redis - Job Queue / Cache)]
        ObjectStore[(S3 / MinIO - Raw Files)]
    end

    subgraph AI["AI Services"]
        Embedder[Embedding Model]
        LLM[LLM (Ollama / Bedrock / OpenAI)]
        Reranker[Cross-Encoder Reranker]
    end

    UI --> Router
    Auth --> AuthSvc
    Router --> Ingest
    Router --> Query
    Router --> Collections
    Ingest --> ObjectStore
    Ingest --> Embedder
    Ingest --> PG
    Query --> Embedder
    Query --> PG
    Query --> Reranker
    Query --> LLM
    Collections --> PG
```

### Component Status

| Component | Technology | Status | Runs Locally | AWS Target |
|-----------|------------|--------|--------------|------------|
| Frontend | React 18, Vite, TypeScript, Tailwind | 🟡 Planned | ✅ | Amplify / S3 + CloudFront |
| Backend API | FastAPI, Python 3.11+ | 🟡 Planned | ✅ | ECS Fargate / App Runner |
| Vector DB | PostgreSQL + pgvector | 🟡 Planned | ✅ (Docker) | RDS for PostgreSQL + pgvector |
| Object Storage | MinIO (local) / S3 | 🟡 Planned | ✅ (Docker) | S3 |
| Job Queue | Redis + Celery | 🟡 Planned | ✅ (Docker) | ElastiCache + SQS |
| Embeddings | sentence-transformers (local) / Bedrock Titan | 🟡 Planned | ✅ | Bedrock |
| LLM | Ollama (local) / Bedrock Claude | 🟡 Planned | ✅ | Bedrock |
| Auth | JWT, bcrypt | 🟡 Planned | ✅ | Cognito (future) |

---

## AWS / Ship It

This project targets the **Ship It** track. The architecture is designed for AWS from day one.

### AWS Services (Planned / Configured)

| Service | Purpose | Why |
|---------|---------|-----|
| **ECS Fargate** | Run backend API containers | Serverless compute, no EC2 management |
| **RDS PostgreSQL + pgvector** | Primary + vector storage | Managed, ACID, pgvector extension native |
| **S3** | Raw document storage | Durable, cheap, integrates with Lambda/ECS |
| **CloudFront + S3 (or Amplify)** | Frontend hosting | Global CDN, HTTPS, custom domain |
| **Bedrock (Titan Embeddings, Claude 3)** | Embeddings + LLM | Fully managed, no GPU instances, data stays in AWS |
| **ElastiCache Redis** | Job queue backend, caching | Managed Redis for Celery broker |
| **SQS** | Async ingestion queue | Decouple upload from processing |
| **Cognito** | User authentication (future) | Managed auth, MFA, social providers |
| **Secrets Manager** | API keys, DB passwords | No secrets in code/env |
| **CloudWatch / X-Ray** | Observability | Logs, metrics, distributed tracing |

### Deployment Status

> 🚧 **NOT YET DEPLOYED** — Infrastructure as Code (Terraform/CDK) and CI/CD pipeline are **planned**. See [Deployment](#deployment) for intended process.

**Live Demo:** `[COMING SOON]`

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand |
| **Backend** | FastAPI, Pydantic v2, Python 3.11+, Uvicorn |
| **Vector Search** | pgvector (PostgreSQL extension), asyncpg / SQLAlchemy 2.0 |
| **Document Processing** | pdfplumber, python-docx, markdown-it-py, tiktoken |
| **Embeddings** | sentence-transformers (BAAI/bge-small-en-v1.5), optional: Bedrock Titan |
| **LLM** | Ollama (local), AWS Bedrock (Claude 3 Haiku/Sonnet) |
| **Reranking** | cross-encoder/ms-marco-MiniLM-L-6-v2 (optional) |
| **Task Queue** | Celery, Redis |
| **Auth** | python-jose (JWT), passlib (bcrypt) |
| **Storage** | MinIO (S3-compatible) local, boto3 for S3 |
| **Observability** | structlog, prometheus-client, OpenTelemetry (planned) |
| **Infrastructure** | Docker, Docker Compose, Terraform (planned), GitHub Actions (planned) |
| **Testing** | pytest, pytest-asyncio, httpx, pytest-mock |

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** v2+
- **Python 3.11+** (for local development without Docker)
- **Node.js 20+** and **pnpm** (for frontend development)
- **Ollama** (optional, for local LLM) — `curl -fsSL https://ollama.ai/install.sh | sh`

### Quick Start (Docker Compose)

```bash
# Clone and enter
git clone <repo-url> remora
cd remora

# Copy environment template
cp .env.example .env
# Edit .env with your settings (see Environment Variables below)

# Start all services
docker compose up -d --build

# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# MinIO Console: http://localhost:9001
```

### Local Development (Without Docker)

**Backend**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start Redis & Postgres (via Docker)
docker compose up -d postgres redis minio

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000

# In another terminal, start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

**Frontend**
```bash
cd frontend
pnpm install
pnpm dev  # http://localhost:5173
```

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | ✅ | `postgresql://postgres:postgres@localhost:5432/remora` |
| `REDIS_URL` | Redis connection string | ✅ | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` | MinIO/S3 endpoint | ✅ | `http://localhost:9000` |
| `MINIO_ACCESS_KEY` | MinIO access key | ✅ | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO secret key | ✅ | `minioadmin` |
| `MINIO_BUCKET` | Bucket for raw documents | ✅ | `remora-documents` |
| `JWT_SECRET` | Secret for JWT signing | ✅ | **generate a strong random string** |
| `JWT_ALGORITHM` | JWT algorithm | ❌ | `HS256` |
| `JWT_EXPIRE_MINUTES` | Access token TTL | ❌ | `60` |
| `EMBEDDING_MODEL` | sentence-transformers model name | ❌ | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DEVICE` | `cpu` or `cuda` | ❌ | `cpu` |
| `LLM_PROVIDER` | `ollama` or `bedrock` | ❌ | `ollama` |
| `OLLAMA_BASE_URL` | Ollama API base URL | If `ollama` | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model tag | If `ollama` | `llama3.1:8b` |
| `AWS_REGION` | AWS region for Bedrock/S3 | If `bedrock` | `us-east-1` |
| `BEDROCK_EMBEDDING_MODEL` | Bedrock embedding model ID | If `bedrock` | `amazon.titan-embed-text-v2:0` |
| `BEDROCK_LLM_MODEL` | Bedrock LLM model ID | If `bedrock` | `anthropic.claude-3-haiku-20240307-v1:0` |
| `CHUNK_SIZE` | Token chunk size | ❌ | `512` |
| `CHUNK_OVERLAP` | Token overlap between chunks | ❌ | `64` |
| `TOP_K` | Retrieval count | ❌ | `8` |
| `RERANK_TOP_K` | Rerank count (if enabled) | ❌ | `4` |

---

## Usage

### Upload a Document (API)

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer <token>" \
  -F "file=@research_paper.pdf" \
  -F "collection_id=my-research"
```

### Query Your Knowledge Base

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What methodology did the paper use for evaluation?",
    "collection_id": "my-research",
    "stream": true
  }'
```

**Response (streaming):**
```json
{
  "answer": "The paper used a randomized controlled trial...",
  "citations": [
    {"doc_id": "uuid", "filename": "research_paper.pdf", "page": 3, "chunk_index": 2, "text": "We evaluated using a randomized controlled trial..."}
  ],
  "usage": {"prompt_tokens": 1240, "completion_tokens": 180}
}
```

### Web UI

1. Open `http://localhost:5173`
2. Register / log in
3. Create a collection (e.g., "Work Projects", "Research")
4. Drag and drop PDFs, Markdown, or text files
5. Wait for processing (status shows in UI)
6. Switch to **Chat** tab, select the collection, ask questions

---

## Project Structure

```
remora/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/            # API routes (documents, query, collections, auth)
│   │   ├── core/           # Config, security, database, exceptions
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas (request/response)
│   │   ├── services/       # Business logic (ingestion, query, embeddings)
│   │   ├── workers/        # Celery tasks for async processing
│   │   └── main.py         # App entrypoint
│   ├── alembic/            # Database migrations
│   ├── tests/              # Backend tests (pytest)
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/               # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Route pages (Login, Collections, Chat, Upload)
│   │   ├── hooks/          # Custom React hooks
│   │   ├── store/          # Zustand stores (auth, collections, query)
│   │   ├── api/            # API client (TanStack Query + Axios)
│   │   └── utils/
│   ├── index.html
│   ├── package.json
│   └── Dockerfile
├── infrastructure/         # IaC (planned)
│   ├── terraform/          # AWS resources
│   └── docker-compose.yml  # Local development stack
├── scripts/                # Utility scripts (ingest, benchmark, etc.)
├── .env.example
├── docker-compose.yml      # Root compose for full stack
├── Makefile                # Common commands
└── README.md
```

---

## Deployment

### Intended AWS Deployment Process

> ⚠️ **Not yet implemented** — The following describes the target deployment flow.

1. **Infrastructure Provisioning (Terraform)**
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan -var-file=prod.tfvars
   terraform apply -var-file=prod.tfvars
   ```
   Creates: VPC, RDS (pgvector), ElastiCache, ECS Cluster, S3 buckets, CloudFront, IAM roles, Secrets Manager entries.

2. **Container Images (GitHub Actions)**
   - On push to `main`: Build backend & frontend Docker images → push to ECR
   - Run tests, lint, type-check in pipeline

3. **Service Deployment**
   - ECS Services for backend (API + Celery worker) with Fargate
   - Frontend: Amplify (auto-deploy from `main`) or S3 + CloudFront via pipeline

4. **Database Migrations**
   - Run as ECS one-off task or via GitHub Actions step before deploy

5. **Secrets Management**
   - All secrets in AWS Secrets Manager, injected as env vars at runtime

### Local Docker Compose (Current)

```bash
# Full stack
docker compose -f infrastructure/docker-compose.yml up -d

# View logs
docker compose logs -f backend

# Stop
docker compose down -v  # -v removes volumes (data loss!)
```

---

## Hackathon

**WeMakeDevs × AWS — First Commit**  
**Bharat Builds Tour**  
**Track: Ship It** (Sep 17–20, 2026)

### How Remora Addresses the Hackathon Criteria

| Criterion | Remora's Approach |
|-----------|-------------------|
| **Real Problem** | Solves personal knowledge retrieval — a daily pain point for developers, researchers, students. Not a toy demo. |
| **AWS Integration** | Architected for managed AWS services (RDS pgvector, Bedrock, ECS, S3, ElastiCache). No "AWS-washing" — each service has a clear role. |
| **Execution** | Working local stack (Docker Compose), clean separation of concerns, typed APIs, async processing, streaming responses. |
| **Learning** | Building RAG from scratch: chunking strategies, embedding models, reranking, prompt engineering, vector DB tuning, production Docker/ECS patterns. |

> This project is being developed *for* the hackathon. No awards, rankings, or judging outcomes are claimed.

---

## Roadmap

| Phase | Items |
|-------|-------|
| **MVP (Hackathon)** | Document upload → processing → chat query with citations; local Docker stack; deploy to AWS (ECS + RDS + Bedrock) |
| **Post-Hackathon v0.2** | Multi-user with Cognito; collection sharing; Obsidian/Notion import; hybrid keyword+vector search |
| **v0.3** | Agentic RAC (multi-hop reasoning); automatic graph extraction; Slack/Discord bot; browser extension |
| **v1.0** | Plugin system; fine-tuned embeddings for domain-specific corpora; on-prem air-gapped deployment guide |

---

## License

**Licensing decision pending.**  
No license file exists in the repository yet. A license (likely MIT or Apache-2.0) will be added before the hackathon submission deadline.

---

## Author / Credits

Developed for the **WeMakeDevs × AWS First Commit hackathon** by:

- **Ayandas** — [GitHub](https://github.com/ayandas)

*No other contributors at this time.*