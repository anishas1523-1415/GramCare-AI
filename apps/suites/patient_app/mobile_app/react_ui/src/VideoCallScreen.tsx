import React, { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { Mic, MicOff, Video, VideoOff, PhoneOff } from 'lucide-react';
import { motion } from 'framer-motion';

const SERVER_URL = 'http://localhost:4000'; // Node.js Signaling Server

export default function VideoCallScreen({ onEndCall, roomId = "emergency_room_1" }: { onEndCall: () => void, roomId?: string }) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  const socketRef = useRef<Socket | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);

  useEffect(() => {
    socketRef.current = io(SERVER_URL);
    const socket = socketRef.current;

    const initWebRTC = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        setLocalStream(stream);
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }

        socket.emit("join_call", roomId);

        const peer = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
        });
        peerRef.current = peer;

        // Add local tracks to peer
        stream.getTracks().forEach(track => peer.addTrack(track, stream));

        // Listen for remote tracks
        peer.ontrack = (event) => {
          setRemoteStream(event.streams[0]);
          if (remoteVideoRef.current) {
            remoteVideoRef.current.srcObject = event.streams[0];
          }
        };

        // Send ICE candidates
        peer.onicecandidate = (event) => {
          if (event.candidate) {
            socket.emit("ice-candidate", { target: roomId, candidate: event.candidate });
          }
        };

        // Handle incoming WebRTC signaling
        socket.on("user_joined", async () => {
          console.log("Doctor joined, creating offer...");
          const offer = await peer.createOffer();
          await peer.setLocalDescription(offer);
          socket.emit("offer", { target: roomId, offer });
        });

        socket.on("offer", async (payload) => {
          console.log("Received offer...");
          await peer.setRemoteDescription(new RTCSessionDescription(payload.offer));
          const answer = await peer.createAnswer();
          await peer.setLocalDescription(answer);
          socket.emit("answer", { target: roomId, answer });
        });

        socket.on("answer", async (payload) => {
          console.log("Received answer...");
          await peer.setRemoteDescription(new RTCSessionDescription(payload.answer));
        });

        socket.on("ice-candidate", async (candidate) => {
          console.log("Received ICE Candidate...");
          try {
            await peer.addIceCandidate(new RTCIceCandidate(candidate));
          } catch (e) {
            console.error("Error adding received ice candidate", e);
          }
        });

      } catch (err) {
        console.error("Failed to access media devices", err);
      }
    };

    initWebRTC();

    return () => {
      socket.disconnect();
      if (peerRef.current) peerRef.current.close();
      if (localStream) localStream.getTracks().forEach(track => track.stop());
    };
  }, [roomId]);

  const toggleMute = () => {
    if (localStream) {
      localStream.getAudioTracks().forEach(track => {
        track.enabled = !track.enabled;
      });
      setIsMuted(!isMuted);
    }
  };

  const toggleVideo = () => {
    if (localStream) {
      localStream.getVideoTracks().forEach(track => {
        track.enabled = !track.enabled;
      });
      setIsVideoOff(!isVideoOff);
    }
  };

  const handleEndCall = () => {
    if (peerRef.current) peerRef.current.close();
    if (localStream) localStream.getTracks().forEach(track => track.stop());
    onEndCall();
  };

  return (
    <div className="h-full bg-gray-900 flex flex-col relative overflow-hidden rounded-[30px]">
      
      {/* Remote Video (Full Screen) */}
      <div className="absolute inset-0 bg-black flex items-center justify-center">
        {remoteStream ? (
          <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
        ) : (
          <div className="flex flex-col items-center">
            <div className="w-20 h-20 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
            <p className="text-white text-lg animate-pulse">Waiting for Doctor to join...</p>
          </div>
        )}
      </div>

      {/* Local Video (PiP) */}
      <motion.div 
        initial={{ opacity: 0, scale: 0.8, x: 20, y: 20 }}
        animate={{ opacity: 1, scale: 1, x: 0, y: 0 }}
        className="absolute bottom-28 right-6 w-32 h-48 bg-gray-800 rounded-2xl overflow-hidden border-2 border-white/20 shadow-2xl z-20"
      >
        <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
      </motion.div>

      {/* Call Controls Overlay */}
      <div className="absolute bottom-8 left-0 right-0 flex justify-center items-center gap-6 z-30">
        <button onClick={toggleMute} className={`p-4 rounded-full backdrop-blur-md transition-colors ${isMuted ? 'bg-red-500/80 text-white' : 'bg-white/20 text-white hover:bg-white/30'}`}>
          {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
        </button>
        
        <button onClick={handleEndCall} className="p-5 bg-red-600 rounded-full text-white shadow-[0_0_20px_rgba(220,38,38,0.6)] hover:bg-red-700 transition-colors">
          <PhoneOff size={32} />
        </button>
        
        <button onClick={toggleVideo} className={`p-4 rounded-full backdrop-blur-md transition-colors ${isVideoOff ? 'bg-red-500/80 text-white' : 'bg-white/20 text-white hover:bg-white/30'}`}>
          {isVideoOff ? <VideoOff size={24} /> : <Video size={24} />}
        </button>
      </div>

    </div>
  );
}
