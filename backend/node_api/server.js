require("dotenv").config();
const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const cors = require("cors");
const admin = require("firebase-admin");

// Initialize Firebase Admin (Mock/Placeholder for now)
// In production, we'd load serviceAccountKey.json
try {
  // admin.initializeApp({
  //   credential: admin.credential.cert(serviceAccount)
  // });
  console.log("Firebase Admin initialization deferred until credentials are provided.");
} catch (error) {
  console.error("Firebase Admin Error:", error);
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
  
  socket.on("join_call", (roomId) => {
    socket.join(roomId);
    console.log(`Socket ${socket.id} joined video call room: ${roomId}`);
    // Notify others in the room that a user connected
    socket.to(roomId).emit("user_joined", socket.id);
  });

  socket.on("offer", (payload) => {
    io.to(payload.target).emit("offer", payload);
  });

  socket.on("answer", (payload) => {
    io.to(payload.target).emit("answer", payload);
  });

  socket.on("ice-candidate", (incoming) => {
    io.to(incoming.target).emit("ice-candidate", incoming.candidate);
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

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`GramCare Node.js Data Engine running on port ${PORT}`);
});
