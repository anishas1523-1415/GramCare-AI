require("dotenv").config();
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const cors = require("cors");
const { initializeApp, cert } = require("firebase-admin/app");
const { getMessaging } = require("firebase-admin/messaging");
const jwt = require("jsonwebtoken");

// Initialize Firebase Admin for Push Notifications
let firebaseInitialized = false;
try {
  const serviceAccount = require("./firebase-service-account.json");
  initializeApp({
    credential: cert(serviceAccount)
  });
  firebaseInitialized = true;
  console.log("Firebase Admin initialized successfully. Push notifications enabled.");
} catch (error) {
  console.warn("Firebase Admin Initialization Failed:", error.message);
  console.warn("FCM Push Notifications will not be sent, but Socket.io broadcast will still work.");
}

// Shared JWT secret. MUST match apps/backend_service's JWT_SECRET_KEY so tokens
// minted by the FastAPI service validate here too. (Previously this file read a
// different env var, SECRET_KEY, with a different default, which meant tokens
// silently failed to validate across the two services.)
const DEV_DEFAULT_SECRET = "gramcare_jwt_secret_change_this_in_production_2026";
const IS_PRODUCTION =
  (process.env.NODE_ENV || "").toLowerCase() === "production" ||
  (process.env.ENVIRONMENT || "").toLowerCase() === "production";
const JWT_SECRET =
  process.env.JWT_SECRET_KEY || process.env.SECRET_KEY || DEV_DEFAULT_SECRET;

// Security: refuse to run on the publicly-known default secret in production.
// The signaling service validates tokens minted by FastAPI; if it fell back to
// the committed default while FastAPI used a real secret, either cross-service
// auth breaks OR (worse) both run on a guessable secret and tokens are
// forgeable. Fail fast so misconfiguration is caught at boot, not in prod.
if (IS_PRODUCTION && JWT_SECRET === DEV_DEFAULT_SECRET) {
  console.error(
    "FATAL: JWT_SECRET_KEY is unset or equals the public development default " +
      "while NODE_ENV/ENVIRONMENT=production. Set a strong secret shared with " +
      "the FastAPI backend."
  );
  process.exit(1);
}

// Allowed origins for both REST (Express) and Socket.io. Defaults cover local
// dev for web_portal (3000), react_dashboard (80 in Docker / 5173 in dev).
// In production this MUST be set explicitly via ALLOWED_ORIGINS.
const ALLOWED_ORIGINS = (
  process.env.ALLOWED_ORIGINS ||
  "http://localhost:3000,http://localhost:5173,http://localhost:80,http://localhost"
)
  .split(",")
  .map((o) => o.trim())
  .filter(Boolean);

const corsOptions = {
  origin: (origin, callback) => {
    // Allow non-browser tools (curl, health checks) which send no Origin header.
    if (!origin || ALLOWED_ORIGINS.includes(origin)) {
      return callback(null, true);
    }
    console.warn(`Blocked CORS request from disallowed origin: ${origin}`);
    return callback(new Error("Not allowed by CORS"));
  },
  methods: ["GET", "POST", "PUT"]
};

const app = express();
app.use(cors(corsOptions));
app.use(express.json());

const server = http.createServer(app);

// Initialize Socket.io for Realtime Doctor Portal Synchronization
const io = new Server(server, {
  cors: corsOptions
});

// --- AUTHENTICATION MIDDLEWARE ---
// Design note: the connection itself stays open to unauthenticated sockets,
// because the public "guest symptom checker" on the web portal legitimately
// broadcasts a triage alert (new_triage_alert) before a user logs in. What
// changed vs. before: sockets are now explicitly tagged authenticated/not,
// and every SENSITIVE action (joining a call room, WebRTC signaling,
// department joins) is gated on socket.authenticated below, instead of auth
// being decorative and unenforced everywhere. If a valid token is supplied,
// it is verified — an invalid (not just missing) token is still rejected.
io.use((socket, next) => {
  const token = socket.handshake.auth?.token;
  socket.authenticated = false;

  if (!token) {
    console.warn("Unauthenticated socket connection (guest mode):", socket.id);
    return next();
  }

  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) {
      console.warn("Rejected socket connection with invalid JWT:", socket.id, err.message);
      return next(new Error("Authentication error: invalid token"));
    }
    socket.user = decoded;
    socket.authenticated = true;
    next();
  });
});

// Helper: reject an event from an unauthenticated socket with a clear error
// event back to the client, instead of silently processing or silently
// dropping it (both of which make client-side debugging painful).
function requireAuth(socket, eventName) {
  if (!socket.authenticated) {
    console.warn(`Blocked unauthenticated "${eventName}" from socket ${socket.id}`);
    socket.emit("error", { event: eventName, message: "Authentication required" });
    return false;
  }
  return true;
}

// Realtime connection handler
io.on("connection", (socket) => {
  console.log(`A user connected to the socket: ${socket.id} (authenticated: ${socket.authenticated})`);

  // Doctors can join specific department rooms — requires auth, since this
  // controls which triage/emergency alerts a client receives.
  socket.on("join_department", (department) => {
    if (!requireAuth(socket, "join_department")) return;
    if (typeof department !== "string" || !department.trim()) return;
    socket.join(department);
    console.log(`Socket ${socket.id} joined department: ${department}`);
  });

  // Handle incoming emergency triage alerts and broadcast to doctors.
  // Left open to unauthenticated sockets intentionally: the public "guest"
  // symptom checker on the web portal broadcasts this before login, and a
  // CRITICAL result must still reach doctors even for a not-yet-logged-in
  // user (planning doc: "Critical Risk -> Emergency SOS activated").
  socket.on("new_triage_alert", (alertData) => {
    if (!alertData || typeof alertData !== "object") return;
    console.log("New Triage Alert Received:", alertData);

    if (alertData.department && typeof alertData.department === "string") {
      io.to(alertData.department).emit("triage_update", alertData);
    }

    if (alertData.severity === "CRITICAL") {
      // Scoped to on-duty responders (doctors/hospital desks join the
      // "emergency_responders" room on connect) instead of every socket.
      io.to("emergency_responders").emit("emergency_alert", alertData);
    }
  });

  // --- WEBRTC SIGNALING LOGIC (Tele-ICU) ---
  // All signaling actions require auth: an unauthenticated caller has no
  // business joining or injecting messages into a private consultation room.

  socket.on("join_room", (roomId) => {
    if (!requireAuth(socket, "join_room")) return;
    if (typeof roomId !== "string" || !roomId.trim()) return;
    socket.join(roomId);
    console.log(`Socket ${socket.id} joined video call room: ${roomId}`);
    socket.to(roomId).emit("user_joined", socket.id);
  });

  // Relay helper: only forward signaling payloads to a room the sender has
  // actually joined. Previously any socket could emit "offer"/"answer" with
  // an arbitrary roomId and inject signaling into a session it never joined —
  // this closes that gap without requiring clients to change their payload
  // shape (they still just send { roomId, ...sdp/ice }).
  function relayToRoom(eventName, payload) {
    if (!requireAuth(socket, eventName)) return;
    const roomId = payload?.roomId;
    if (typeof roomId !== "string" || !socket.rooms.has(roomId)) {
      console.warn(`Blocked "${eventName}" from ${socket.id}: not a member of room ${roomId}`);
      return;
    }
    socket.to(roomId).emit(eventName, payload);
  }

  socket.on("offer", (payload) => relayToRoom("offer", payload));
  socket.on("answer", (payload) => relayToRoom("answer", payload));
  socket.on("ice_candidate", (incoming) => relayToRoom("ice_candidate", incoming));

  // Text-chat fallback for the consultation room's Adaptive Bandwidth
  // Switching (planning doc: video -> audio -> text as network quality
  // degrades). Room-scoped like the other signaling events; message content
  // itself isn't persisted server-side, just relayed live.
  socket.on("chat_message", (payload) => {
    if (!requireAuth(socket, "chat_message")) return;
    const roomId = payload?.roomId;
    const text = typeof payload?.text === "string" ? payload.text.slice(0, 2000) : "";
    if (typeof roomId !== "string" || !socket.rooms.has(roomId) || !text.trim()) return;
    socket.to(roomId).emit("chat_message", {
      text,
      from: socket.user?.sub || socket.user?.id || "unknown",
      at: new Date().toISOString(),
    });
  });

  // --- IOT VITALS STREAMING (PHASE 15) ---
  socket.on("vitals_update", (vitalsData) => {
    if (!requireAuth(socket, "vitals_update")) return;
    if (!vitalsData || typeof vitalsData.roomId !== "string" || !socket.rooms.has(vitalsData.roomId)) {
      return;
    }
    console.log(`Vitals update from ${vitalsData.patientId}: HR ${vitalsData.heartRate}, SpO2 ${vitalsData.spO2}`);
    socket.to(vitalsData.roomId).emit("live_vitals", vitalsData);
  });

  // -----------------------------

  socket.on("disconnect", () => {
    console.log("User disconnected:", socket.id);
    // Note: socket.io automatically removes the socket from all rooms on disconnect.
  });

  socket.on("error", (err) => {
    console.error(`Socket error on ${socket.id}:`, err?.message || err);
  });
});

// Basic health check route
app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "GramCare Node API" });
});

// --- Minimal in-memory rate limiter for the SOS endpoint ---
// No new npm dependency introduced (this environment currently cannot run
// `npm install` to verify a new package resolves), so this is a small
// hand-rolled fixed-window limiter: max SOS_MAX_REQUESTS triggers per
// SOS_WINDOW_MS per patient_id. Good enough to stop trivial spam; for a real
// multi-instance production deployment this should move to a shared store
// (e.g. Redis) since this in-memory map won't be consistent across replicas.
const SOS_WINDOW_MS = 60 * 1000;
const SOS_MAX_REQUESTS = 3;
const sosRateLimitLog = new Map(); // patient_id -> [timestamps]

function isRateLimited(patientId) {
  const now = Date.now();
  const timestamps = (sosRateLimitLog.get(patientId) || []).filter(
    (t) => now - t < SOS_WINDOW_MS
  );
  timestamps.push(now);
  sosRateLimitLog.set(patientId, timestamps);
  return timestamps.length > SOS_MAX_REQUESTS;
}

// Simple Bearer-token auth guard for REST routes (mirrors the Socket.io check).
function requireJwtAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  if (!token) {
    return res.status(401).json({ error: "Authentication required" });
  }
  jwt.verify(token, JWT_SECRET, (err, decoded) => {
    if (err) {
      return res.status(401).json({ error: "Invalid or expired token" });
    }
    req.user = decoded;
    next();
  });
}

// SOS REST Endpoint. Previously this was fully unauthenticated with no
// payload validation and no rate limiting, meaning anyone who could reach
// the API could broadcast fake CRITICAL emergency alerts to every connected
// doctor/responder, drowning out real emergencies. Now: requires a valid
// JWT, validates the minimum required fields, and rate-limits per patient.
app.post("/api/sos/trigger", requireJwtAuth, async (req, res) => {
  try {
    const sosData = req.body || {};
    const patientId = sosData.patient_id;

    if (!patientId || typeof patientId !== "string" && typeof patientId !== "number") {
      return res.status(400).json({ error: "patient_id is required" });
    }
    if (!sosData.location) {
      return res.status(400).json({ error: "location is required" });
    }
    const allowedSeverities = ["LOW", "MODERATE", "HIGH", "CRITICAL"];
    if (sosData.severity && !allowedSeverities.includes(sosData.severity)) {
      return res.status(400).json({ error: `severity must be one of ${allowedSeverities.join(", ")}` });
    }

    if (isRateLimited(String(patientId))) {
      console.warn(`SOS rate limit exceeded for patient_id=${patientId}`);
      return res.status(429).json({ error: "Too many SOS requests. Please wait before retrying." });
    }

    console.log("REST SOS Triggered by user", req.user?.sub || req.user?.id, ":", sosData);

    const payload = {
      ...sosData,
      triggered_by: req.user?.sub || req.user?.id || null,
      time: new Date().toLocaleTimeString(),
      isEmergency: true
    };

    // 1. Broadcast via WebSocket to on-duty responders. The doctor dashboard
    // joins the "emergency_responders" room on connect (authenticated), so
    // alerts no longer flood every visitor's socket.
    io.to("emergency_responders").emit("emergency_alert", payload);

    // 2. Fire Push Notification via Firebase Cloud Messaging (FCM)
    if (firebaseInitialized && payload.severity === "CRITICAL") {
      try {
        const message = {
          notification: {
            title: "🚨 CRITICAL EMERGENCY SOS",
            body: `Patient ${payload.patient_id} triggered an SOS at ${payload.location}`,
          },
          data: {
            patient_id: String(payload.patient_id),
            type: "sos_alert"
          },
          topic: "doctors_global"
        };

        const fcmRes = await getMessaging().send(message);
        console.log("FCM Push Notification Sent successfully:", fcmRes);
      } catch (err) {
        console.error("Failed to send FCM Push Notification:", err.message);
      }
    }

    res.json({ success: true, message: "SOS Broadcasted & Push Notification Triggered" });
  } catch (err) {
    console.error("Unhandled error in /api/sos/trigger:", err);
    res.status(500).json({ error: "Internal server error while processing SOS" });
  }
});

// ICE server configuration for WebRTC. STUN alone fails behind symmetric
// NAT — common on rural mobile networks, this platform's exact audience —
// This now dynamically fetches production TURN credentials from Metered.live.
app.get("/api/webrtc/turn-credentials", async (req, res) => {
  try {
    const meteredDomain = process.env.METERED_DOMAIN || "gramcareai.metered.live";
    const apiKey = process.env.METERED_API_KEY || "23816ffe3b9d86735741551f2855d89a303a";
    
    // Using dynamic fetch from Metered REST API for rotating credentials/load balancing
    const response = await fetch(`https://${meteredDomain}/api/v1/turn/credentials?apiKey=${apiKey}`);
    const iceServers = await response.json();
    
    res.json({ iceServers });
  } catch (error) {
    console.error("Failed to fetch dynamic TURN credentials from Metered:", error);
    
    // Safe fallback to the static credentials provided
    const fallbackServers = [
      { urls: "stun:stun.relay.metered.ca:80" },
      {
        urls: "turn:global.relay.metered.ca:80",
        username: "d4b2caec759c5ca31ab26c83",
        credential: "yHHfjzfaVx7rDglm",
      },
      {
        urls: "turn:global.relay.metered.ca:80?transport=tcp",
        username: "d4b2caec759c5ca31ab26c83",
        credential: "yHHfjzfaVx7rDglm",
      },
      {
        urls: "turn:global.relay.metered.ca:443",
        username: "d4b2caec759c5ca31ab26c83",
        credential: "yHHfjzfaVx7rDglm",
      },
      {
        urls: "turns:global.relay.metered.ca:443?transport=tcp",
        username: "d4b2caec759c5ca31ab26c83",
        credential: "yHHfjzfaVx7rDglm",
      }
    ];
    res.json({ iceServers: fallbackServers });
  }
});

// Express-level error handler: catches CORS rejections (thrown by the
// corsOptions.origin callback above) and any error passed via next(err) from
// a route, and returns a clean JSON response instead of the default HTML
// stack trace / hung connection.
app.use((err, req, res, next) => {
  if (err && err.message === "Not allowed by CORS") {
    return res.status(403).json({ error: "Origin not allowed" });
  }
  console.error("Unhandled Express error:", err);
  res.status(500).json({ error: "Internal server error" });
});

// Process-level safety net. Previously this service had no
// uncaughtException/unhandledRejection handlers at all, so a malformed
// payload or a rejected promise anywhere (e.g. the FCM call, a socket
// handler) could silently crash the whole signaling server — taking down
// WebRTC signaling and SOS broadcasting for every connected user at once.
// We log loudly and keep the process alive rather than exiting, since an
// abrupt exit here is worse for an emergency-response service than
// continuing in a degraded state; the underlying bug should still be fixed,
// this is a backstop, not a substitute for handling errors at the source.
process.on("uncaughtException", (err) => {
  console.error("uncaughtException — GramCare Node signaling service:", err);
});
process.on("unhandledRejection", (reason) => {
  console.error("unhandledRejection — GramCare Node signaling service:", reason);
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`GramCare Node.js Data Engine running on port ${PORT}`);
});
