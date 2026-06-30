# GramCare AI

An offline-first, AI-powered telemedicine ecosystem designed to bridge the healthcare gap in rural regions. 

GramCare AI provides a complete suite of tools for Patients, Doctors, and Pharmacists, integrating LLM-based triage, WebRTC video consultations, automated prescription routing, and Razorpay-powered appointment booking.

## 🚀 Architecture

The platform is composed of 5 core microservices:

1. **Patient Suite & Doctor Portal (`apps/web_portal`)**
   - Built with Next.js 14 and TailwindCSS.
   - Serves as the unified web interface for both patients (AI Triage, Appointment Booking, Family Profiles) and doctors (Live Queue, WebRTC Tele-ICU, E-Prescriptions).

2. **Pharmacy Network (`apps/react_dashboard`)**
   - Built with React + Vite.
   - A live dashboard for pharmacists to track inventory and fulfill incoming digital prescriptions in real-time.

3. **Mobile App (`apps/mobile_app`)**
   - Built with Flutter.
   - An offline-first mobile application utilizing Hive local storage, allowing rural patients to access their Health Wallet and run the AI Symptom Checker natively.

4. **FastAPI Backend (`apps/backend_service`)**
   - Powered by Python, FastAPI, and PostgreSQL.
   - Handles the core business logic: Authentication, Razorpay processing, AI prompting (Gemini API), EHR (Electronic Health Records), and Pharmacy Inventory.

5. **Realtime Signaling Engine (`backend/node_api`)**
   - Built with Node.js and Socket.io.
   - Manages strict JWT-authenticated WebRTC signaling for Tele-ICU video calls, as well as global SOS emergency broadcasting.

---

## 🛠️ Quick Start (Docker)

The entire ecosystem is containerized for easy deployment.

### Prerequisites
- Docker & Docker Compose
- Node.js (for local development)
- Python 3.11+ (for local development)
- Flutter SDK (for mobile app compilation)

### Running Locally

1. **Configure Environment Variables:**
   Copy the example environment file and fill in your keys (Gemini API, Razorpay):
   ```bash
   cp apps/backend_service/.env.example apps/backend_service/.env
   ```

2. **Launch with Docker Compose:**
   Run the following command at the root of the project to spin up the database, backend, signaling server, and frontend portals simultaneously:
   ```bash
   docker-compose up --build
   ```

3. **Access the Portals:**
   - **Unified Web Portal:** `http://localhost:3000`
   - **Pharmacy Dashboard:** `http://localhost:80`
   - **FastAPI Docs (Swagger):** `http://localhost:8000/docs`

---

## 🧪 Testing & CI/CD

This repository is configured with a complete **GitHub Actions** CI/CD pipeline (`.github/workflows/main.yml`) which automatically runs on every push and PR to the `main` branch. 

The pipeline ensures:
- The PostgreSQL database boots successfully.
- The Python `pytest` backend integration suite passes.
- The Next.js, Vite React, and Flutter apps compile without errors.

To run the backend tests locally:
```bash
cd apps/backend_service
pip install -r requirements.txt
pytest tests/
```

## 🔒 License
Proprietary / Closed Source.
