# Vector Search & Dynamic Token Propagation Sequence Diagram

This document details the search, ranking, and dynamic token propagation workflow across the multimodal catalog.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Search User"
    participant Frontend as "Next.js UI (/search)"
    participant API as "FastAPI Gateway (/api/v1/search)"
    participant Propagator as "Dynamic Token Propagator"
    participant VectorDB as "BigQuery / Firestore Vector Store"
    participant Ranker as "Search Ranking Engine (libs/search_ranking)"
    participant DB as "Metadata Database"

    User->>Frontend: Enter Natural Language Search Query (e.g., "dramatic goal celebration")
    Frontend->>API: POST /api/v1/search/query (Query, Filters, Page)
    
    API->>Propagator: Analyze Query & Compute Dynamic Tokens
    Note over Propagator: Extracts intent, entity tokens,<br/>and dynamic weight propagation rules
    Propagator-->>API: Expanded Tokens & Search Vector Embedding

    API->>VectorDB: Perform Hybrid Vector + Keyword Search
    VectorDB-->>API: Candidate Scene Results & Similarity Scores

    API->>Ranker: Re-rank Candidate Scenes
    Note over Ranker: Applies relevance scoring,<br/>recency boost, engagement weights & content owner rules
    Ranker-->>API: Ranked & Filtered Scene List

    API->>DB: Hydrate Scene Metadata, Video Links & Thumbnails
    DB-->>API: Complete Scene Objects

    API-->>Frontend: Return Search Response (Ranked Scenes, Token Trace, Facets)
    Frontend-->>User: Render Visual Search Results Grid with Video Previews
```

## Key Technical Steps

1. **Dynamic Token Propagation**: Expands raw user queries with dynamic contextual tokens and weights.
2. **Hybrid Search**: Combines dense vector semantic similarity search with keyword text matching.
3. **Multi-Factor Ranking**: Re-ranks candidates taking visual relevance, content recency, and engagement signals into account.
