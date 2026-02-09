# Architecture Overview

![Architecture Diagram](./architecture.png)

## System Components

### Frontend Layer

- **Next.js Frontend** - React-based UI for media upload, job management, and results visualization
- **Agentspace** - User interaction and workflow orchestration

### API & Messaging

- **FastAPI** - RESTful API handling requests, job creation, and status queries
- **Pub/Sub** - Event-driven messaging for asynchronous job processing

### Data Layer

- **Firestore** - NoSQL database storing videos, jobs, prompts, and analysis results
- **Cloud Storage** - Object storage for uploaded media, processed outputs, and context files

### Processing Layer

- **Media Processor** - FFmpeg-based worker for video compression and audio extraction
- **Analysis Engine** - AI-powered scene analysis using Google Gemini (Vertex AI)

### Analytics

- **BigQuery** - Data warehouse for analytics and reporting on job metrics and results

## Data Flow

1. **Upload**: Frontend → API → Cloud Storage
2. **Job Creation**: API → Firestore → Pub/Sub
3. **Media Processing**: Media Processor reads from Pub/Sub, processes files, writes to Cloud Storage
4. **Scene Analysis**: Analysis Engine reads from Pub/Sub, calls Vertex AI, stores results in Firestore
5. **Analytics**: Results exported to BigQuery for analysis

## Key Features

- **Dual Worker Architecture** - Separate processing pipelines for media and AI analysis
- **Event-Driven** - Pub/Sub enables scalable, asynchronous job execution
- **Cloud-Native** - Built entirely on Google Cloud Platform services
- **Flexible AI Integration** - Vertex AI for production-grade Gemini model deployment
