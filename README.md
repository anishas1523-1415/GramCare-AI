# GramCare AI 🏥

GramCare AI is a comprehensive, offline-capable rural telemedicine ecosystem designed to bridge the healthcare gap in remote areas.

## Ecosystem Architecture

The platform consists of a distributed microservices architecture:
1. **Patient App** (React UI for Web & Mobile): AI Triage, WebRTC Video Consultations, IoT Vitals Sync.
2. **Doctor Portal** (Next.js): Central dashboard for managing triage alerts, EHR, and conducting telehealth video calls.
3. **FastAPI Backend**: Core Python service handling PostgreSQL database connections, JWT Authentication, and Gemini AI Triage orchestration.
4. **Node.js Signaling Server**: Ultra-low latency WebSocket server managing WebRTC video handshakes and real-time IoT Vitals streams.
5. **PostgreSQL Database**: Relational datastore for Users, EHR, and IoT Vitals persistence.

## 🚀 Deployment

GramCare AI is fully dockerized and ready for production deployment on modern cloud infrastructure (e.g. Google Cloud Run).

To run the entire ecosystem locally:

```bash
# Start all 5 microservices in detached mode
docker-compose up --build -d
```

### Services Started:
- **Patient App**: `http://localhost:80`
- **Doctor Portal**: `http://localhost:3000`
- **FastAPI Backend**: `http://localhost:8000`
- **Node.js WebRTC Signaling**: `ws://localhost:4000`
- **PostgreSQL Database**: Port `5432`

---
*Developed as part of the advanced agentic coding session.*
