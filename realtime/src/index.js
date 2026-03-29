/**
 * PredIndex — Real-time server entry point.
 *
 * Provides WebSocket connections for live market data streaming
 * and REST endpoints for real-time subscriptions.
 */

require("dotenv").config();
const express = require("express");
const http = require("http");
const { WebSocketServer } = require("ws");
const cors = require("cors");

const PORT = process.env.REALTIME_PORT || 5001;
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:5000";

const app = express();
app.use(cors());
app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", service: "predindex-realtime", version: "0.1.0" });
});

// Create HTTP server
const server = http.createServer(app);

// WebSocket server for real-time data
const wss = new WebSocketServer({ server, path: "/ws" });

const clients = new Set();

wss.on("connection", (ws) => {
  console.log("📡 New WebSocket client connected");
  clients.add(ws);

  ws.on("message", (message) => {
    try {
      const data = JSON.parse(message);
      console.log("📩 Received:", data);
      // TODO: Handle subscriptions, filter by index, etc.
    } catch {
      console.warn("⚠️ Invalid message received");
    }
  });

  ws.on("close", () => {
    console.log("📡 Client disconnected");
    clients.delete(ws);
  });

  // Welcome message
  ws.send(
    JSON.stringify({
      type: "connected",
      message: "PredIndex real-time feed active",
      indices: ["^BVSP", "^GSPC", "USDBRL=X"],
    })
  );
});

// Broadcast helper
function broadcast(data) {
  const message = JSON.stringify(data);
  clients.forEach((client) => {
    if (client.readyState === 1) {
      client.send(message);
    }
  });
}

// TODO: Set up polling interval to fetch from backend and broadcast
// setInterval(async () => {
//   const quotes = await fetch(`${BACKEND_URL}/api/v1/indices`).then(r => r.json());
//   broadcast({ type: "quotes", data: quotes });
// }, 5000);

server.listen(PORT, () => {
  console.log(`⚡ PredIndex Real-time server running on port ${PORT}`);
  console.log(`   WebSocket endpoint: ws://localhost:${PORT}/ws`);
  console.log(`   Backend URL: ${BACKEND_URL}`);
});
