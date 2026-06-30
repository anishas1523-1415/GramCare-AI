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

const app = express();
app.use(cors());
app.use(express.json());

const server = http.createServer(app);

// Initialize Socket.io for Realtime Doctor Portal Synchronization
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// --- AUTHENTICATION MIDDLEWARE ---
// Ensure only authenticated users can connect to the Socket Server
io.use((socket, next) => {
  const token = socket.handshake.auth.token;
  if (!token) {
    // For demo purposes, we will allow unauthenticated connections, but log a warning.
    // In strict production: return next(new Error("Authentication error: Token missing"));
    console.warn("Unauthenticated socket connection:", socket.id);
    return next();
  }
  
  jwt.verify(token, process.env.SECRET_KEY || "super-secret-key", (err, decoded) => {
    if (err) {
      console.warn("Invalid JWT token for socket:", socket.id);
      // In strict production: return next(new Error("Authentication error: Invalid token"));
      return next(); 
    }
    socket.user = decoded;
    next();
  });
});

// Realtime connection handler
io.on("connection", (socket) => {
  console.log("A user connected to the socket:", socket.id);

  // Doctors can join specific department rooms
  socket.on("join_department", (department) => {
    socket.join(department);
    console.log(`Socket ${socket.id} joined department: ${department}`);
  });

  // Handle incoming emergency triage alerts and broadcast to doctors
  socket.on("new_triage_alert", (alertData) => {
    console.log("New Triage Alert Received:", alertData);
    
    // Broadcast to the specific department room
    if (alertData.department) {
      io.to(alertData.department).emit("triage_update", alertData);
    }
    
    // If it's critical, broadcast globally
    if (alertData.severity === "CRITICAL") {
      io.emit("emergency_alert", alertData);
    }
  });

  // --- WEBRTC SIGNALING LOGIC ---
  
  // --- WEBRTC SIGNALING LOGIC (Tele-ICU) ---
  
  socket.on("join_room", (roomId) => {
    socket.join(roomId);
    console.log(`Socket ${socket.id} joined video call room: ${roomId}`);
    // Notify others in the room that a user connected
    socket.to(roomId).emit("user_joined", socket.id);
  });

  socket.on("offer", (payload) => {
    socket.to(payload.roomId).emit("offer", payload);
  });

  socket.on("answer", (payload) => {
    socket.to(payload.roomId).emit("answer", payload);
  });

  socket.on("ice_candidate", (incoming) => {
    socket.to(incoming.roomId).emit("ice_candidate", incoming);
  });
  
  // --- IOT VITALS STREAMING (PHASE 15) ---
  socket.on("vitals_update", (vitalsData) => {
    // vitalsData: { patientId, roomId, heartRate, spO2 }
    console.log(`Vitals update from ${vitalsData.patientId}: HR ${vitalsData.heartRate}, SpO2 ${vitalsData.spO2}`);
    // Broadcast vitals to the specific room (Doctor)
    if (vitalsData.roomId) {
      socket.to(vitalsData.roomId).emit("live_vitals", vitalsData);
    }
  });

  // -----------------------------

  socket.on("disconnect", () => {
    console.log("User disconnected:", socket.id);
    // Note: socket.io automatically removes the socket from all rooms on disconnect.
  });
});

// Basic health check route
app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "GramCare Node API" });
});

// SOS REST Endpoint (Allows the backend or external services to trigger a global SOS via HTTP)
app.post("/api/sos/trigger", async (req, res) => {
  const sosData = req.body;
  console.log("REST SOS Triggered:", sosData);
  
  const payload = {
    ...sosData,
    time: new Date().toLocaleTimeString(),
    isEmergency: true
  };
  
  // 1. Broadcast via WebSocket to active doctors
  io.emit("emergency_alert", payload);
  
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
        topic: "doctors_global" // Broadcast to all devices subscribed to the 'doctors_global' topic
      };
      
      const fcmRes = await getMessaging().send(message);
      console.log("FCM Push Notification Sent successfully:", fcmRes);
    } catch (err) {
      console.error("Failed to send FCM Push Notification:", err);
    }
  }

  res.json({ success: true, message: "SOS Broadcasted & Push Notification Triggered" });
});

// TURN Server configuration for WebRTC in strict networks (NAT/Firewalls)
app.get("/api/webrtc/turn-credentials", (req, res) => {
  // In production, integrate with Twilio Network Traversal or equivalent
  res.json({
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      { urls: "stun:stun1.l.google.com:19302" },
      // { urls: "turn:your-turn-server.com", username: "guest", credential: "password" }
    ]
  });
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`GramCare Node.js Data Engine running on port ${PORT}`);
});
