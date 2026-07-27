# Live Interactive AI Avatars Sequence Diagram

This sequence diagram documents the authentication, session creation, token handling, and live streaming interactions with AI Avatars.

```mermaid
sequenceDiagram
    autonumber
    actor User as "Web Client"
    participant Frontend as "Next.js UI"
    participant API as "FastAPI Gateway (/api/v1/avatars)"
    participant Auth as "Token Service (libs/avatar_token)"
    participant AvatarSvc as "Avatar Service (libs/avatar_service)"
    participant StreamEngine as "Live WebRTC / Streaming Engine"

    User->>Frontend: Select AI Avatar Profile & Click "Start Live Session"
    Frontend->>API: POST /api/v1/avatars/token (Avatar ID, User Session)
    API->>Auth: Mint Secure Session Token & Credentials
    Auth-->>API: Return Signed Avatar Session Token

    API->>AvatarSvc: Initialize Live Session (Token, Persona Config)
    AvatarSvc->>StreamEngine: Provision WebRTC Streaming Channel
    StreamEngine-->>AvatarSvc: WebRTC Session SDP Offer & ICE Candidates
    AvatarSvc-->>API: Session Connection Details
    API-->>Frontend: Return Session Token & Connection Details

    Frontend->>StreamEngine: Establish WebRTC Peer Connection (SDP Answer / ICE)
    StreamEngine-->>Frontend: WebRTC Connection Established (Active Media Stream)

    loop Real-Time User Interaction Loop
        User->>Frontend: Send User Audio / Text Input
        Frontend->>StreamEngine: Stream Audio / Text Packet
        StreamEngine->>AvatarSvc: Process Voice & Synthesize Avatar Response
        AvatarSvc->>StreamEngine: Output Synchronized Audio + Lip-Synced Avatar Video
        StreamEngine-->>Frontend: Stream Rendered Avatar Video Frames & Audio
        Frontend-->>User: Real-Time Interactive Avatar Display
    end

    User->>Frontend: End Session
    Frontend->>API: POST /api/v1/avatars/session/end
    API->>AvatarSvc: Close Stream & Release Resources
    AvatarSvc->>StreamEngine: Terminate WebRTC Channel
```

## Key Technical Steps

1. **Session Authentication**: Issues secure ephemeral tokens to restrict avatar session access.
2. **WebRTC Peer Handshake**: Establishes low-latency WebRTC streams between client and streaming backend.
3. **Synchronized Lip-Sync**: Delivers real-time multimodal responses with lip-synced video output.
