"use client";

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Mic, MicOff, Video, VideoOff, PhoneOff, MonitorUp, Activity } from 'lucide-react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';

export default function ConsultationRoom({ params }: { params: { id: string } }) {
  const roomId = params.id;
  const { user } = useAuth();
  const router = useRouter();

  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  
  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);
  
  const socketRef = useRef<Socket | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    // Connect to Signaling Server
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "http://localhost:4000";
    socketRef.current = io(WS_URL);

    // Initialize Media
    const startMedia = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        localStreamRef.current = stream;
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }

        // Join Room
        socketRef.current?.emit("join_room", roomId);

        // WebRTC Setup
        peerRef.current = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
        });

        stream.getTracks().forEach(track => {
          if (peerRef.current && localStreamRef.current) {
            peerRef.current.addTrack(track, localStreamRef.current);
          }
        });

        peerRef.current.ontrack = (event) => {
          if (remoteVideoRef.current) {
            remoteVideoRef.current.srcObject = event.streams[0];
            setIsConnected(true);
          }
        };

        peerRef.current.onicecandidate = (event) => {
          if (event.candidate) {
            socketRef.current?.emit("ice_candidate", { candidate: event.candidate, roomId });
          }
        };

        // Socket Events
        socketRef.current?.on("user_joined", async () => {
          // I am the initiator
          if (!peerRef.current) return;
          const offer = await peerRef.current.createOffer();
          await peerRef.current.setLocalDescription(offer);
          socketRef.current?.emit("offer", { offer, roomId });
        });

        socketRef.current?.on("offer", async (data: any) => {
          // I received an offer
          if (!peerRef.current) return;
          await peerRef.current.setRemoteDescription(new RTCSessionDescription(data.offer));
          const answer = await peerRef.current.createAnswer();
          await peerRef.current.setLocalDescription(answer);
          socketRef.current?.emit("answer", { answer, roomId });
        });

        socketRef.current?.on("answer", async (data: any) => {
          if (!peerRef.current) return;
          await peerRef.current.setRemoteDescription(new RTCSessionDescription(data.answer));
        });

        socketRef.current?.on("ice_candidate", async (data: any) => {
          if (!peerRef.current) return;
          try {
            await peerRef.current.addIceCandidate(new RTCIceCandidate(data.candidate));
          } catch (e) {
            console.error("Error adding received ice candidate", e);
          }
        });

      } catch (err) {
        console.error("Media error:", err);
      }
    };

    startMedia();

    return () => {
      // Cleanup
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      peerRef.current?.close();
      socketRef.current?.disconnect();
    };
  }, [roomId]);

  const toggleMute = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getAudioTracks()[0].enabled = isMuted;
      setIsMuted(!isMuted);
    }
  };

  const toggleVideo = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getVideoTracks()[0].enabled = isVideoOff;
      setIsVideoOff(!isVideoOff);
    }
  };

  const endCall = () => {
    localStreamRef.current?.getTracks().forEach(t => t.stop());
    peerRef.current?.close();
    socketRef.current?.disconnect();
    if (user?.role === 'DOCTOR') {
      router.push('/doctor/dashboard');
    } else {
      router.push('/');
    }
  };

  return (
    <div className="min-h-screen bg-black flex flex-col relative overflow-hidden">
      {/* Remote Video (Full Screen) */}
      <div className="absolute inset-0 z-0 flex items-center justify-center bg-gray-900">
        {!isConnected && (
          <div className="flex flex-col items-center text-white/50 animate-pulse">
            <div className="w-20 h-20 rounded-full border-4 border-t-teal-500 border-white/20 animate-spin mb-4" />
            <p>Waiting for other party to join...</p>
          </div>
        )}
        <video 
          ref={remoteVideoRef} 
          autoPlay 
          playsInline 
          className={`w-full h-full object-cover ${!isConnected ? 'hidden' : ''}`}
        />
      </div>

      {/* Header Overlay */}
      <div className="relative z-10 p-6 flex justify-between items-center bg-gradient-to-b from-black/80 to-transparent">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="text-teal-400" /> Tele-ICU Consultation
          </h1>
          <p className="text-white/70 text-sm">Room: {roomId}</p>
        </div>
        <div className="bg-red-500/20 text-red-500 px-4 py-1 rounded-full text-sm font-bold border border-red-500/50 flex items-center gap-2 animate-pulse">
          <div className="w-2 h-2 bg-red-500 rounded-full" /> LIVE
        </div>
      </div>

      {/* Local Video Picture-in-Picture */}
      <motion.div 
        drag
        dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
        className="absolute bottom-32 right-8 w-48 h-72 bg-gray-800 rounded-2xl overflow-hidden shadow-2xl border-2 border-white/20 z-20 cursor-move"
      >
        <video 
          ref={localVideoRef} 
          autoPlay 
          playsInline 
          muted 
          className="w-full h-full object-cover transform scale-x-[-1]"
        />
        {(isMuted || isVideoOff) && (
          <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-4 text-white">
            {isMuted && <MicOff size={24} />}
            {isVideoOff && <VideoOff size={24} />}
          </div>
        )}
      </motion.div>

      {/* Controls Footer */}
      <div className="mt-auto relative z-10 p-8 flex justify-center items-center gap-6 bg-gradient-to-t from-black/80 to-transparent">
        <button 
          onClick={toggleMute}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isMuted ? 'bg-red-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
        </button>
        
        <button 
          onClick={toggleVideo}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isVideoOff ? 'bg-red-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          {isVideoOff ? <VideoOff size={24} /> : <Video size={24} />}
        </button>

        <button 
          className="w-14 h-14 rounded-full flex items-center justify-center bg-white/20 text-white hover:bg-white/30 backdrop-blur-md transition-colors"
        >
          <MonitorUp size={24} />
        </button>

        <button 
          onClick={endCall}
          className="w-16 h-16 rounded-full flex items-center justify-center bg-red-600 hover:bg-red-700 text-white shadow-lg transition-transform hover:scale-110"
        >
          <PhoneOff size={28} />
        </button>
      </div>
    </div>
  );
}
