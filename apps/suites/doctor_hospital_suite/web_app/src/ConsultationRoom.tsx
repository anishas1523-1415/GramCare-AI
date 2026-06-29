import React, { useEffect, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { Mic, MicOff, Video, VideoOff, PhoneOff, Activity, FileText } from 'lucide-react';

const SERVER_URL = 'http://localhost:4000'; // Node.js Signaling Server

export default function ConsultationRoom({ onEndCall, roomId = "emergency_room_1", patientName = "P1" }: { onEndCall: () => void, roomId?: string, patientName?: string }) {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStream, setRemoteStream] = useState<MediaStream | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  
  // Phase 15: IoT Vitals State
  const [vitals, setVitals] = useState({ heartRate: '--', spO2: '--' });
  const [vitalsActive, setVitalsActive] = useState(false);
  
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

        // Phase 15: Listen for Live Vitals
        socket.on("live_vitals", (data) => {
          setVitals({ heartRate: data.heartRate, spO2: data.spO2 });
          setVitalsActive(true);
        });

        const peer = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
        });
        peerRef.current = peer;

        stream.getTracks().forEach(track => peer.addTrack(track, stream));

        peer.ontrack = (event) => {
          setRemoteStream(event.streams[0]);
          if (remoteVideoRef.current) {
            remoteVideoRef.current.srcObject = event.streams[0];
          }
        };

        peer.onicecandidate = (event) => {
          if (event.candidate) {
            socket.emit("ice-candidate", { target: roomId, candidate: event.candidate });
          }
        };

        socket.on("user_joined", async () => {
          console.log("Patient joined, creating offer...");
          const offer = await peer.createOffer();
          await peer.setLocalDescription(offer);
          socket.emit("offer", { target: roomId, offer });
        });

        socket.on("offer", async (payload) => {
          console.log("Received offer from Patient...");
          await peer.setRemoteDescription(new RTCSessionDescription(payload.offer));
          const answer = await peer.createAnswer();
          await peer.setLocalDescription(answer);
          socket.emit("answer", { target: roomId, answer });
        });

        socket.on("answer", async (payload) => {
          console.log("Received answer from Patient...");
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
    <div className="h-full flex gap-6 p-6">
      
      {/* Video Call Area */}
      <div className="flex-1 bg-gray-900 rounded-3xl overflow-hidden relative shadow-2xl flex flex-col">
        {/* Remote Patient Video */}
        <div className="flex-1 bg-black flex items-center justify-center relative">
          {remoteStream ? (
            <video ref={remoteVideoRef} autoPlay playsInline className="w-full h-full object-cover" />
          ) : (
            <div className="flex flex-col items-center">
              <div className="w-20 h-20 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
              <p className="text-gray-400 text-lg">Waiting for Patient ({patientName}) to connect...</p>
            </div>
          )}
          
          <div className="absolute top-6 left-6 bg-black/50 backdrop-blur-md px-4 py-2 rounded-xl text-white flex items-center gap-2">
            <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></span>
            <span className="font-bold">LIVE • Emergency Triage Room</span>
          </div>
        </div>

        {/* Local Doctor Video (PiP) */}
        <div className="absolute bottom-24 right-6 w-48 h-32 bg-gray-800 rounded-2xl overflow-hidden border-2 border-white/20 shadow-2xl">
          <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
        </div>

        {/* Call Controls */}
        <div className="h-20 bg-gray-900 flex justify-center items-center gap-6 border-t border-white/10">
          <button onClick={toggleMute} className={`p-4 rounded-full transition-colors ${isMuted ? 'bg-red-500 text-white' : 'bg-gray-700 text-white hover:bg-gray-600'}`}>
            {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
          </button>
          
          <button onClick={handleEndCall} className="px-8 py-3 bg-red-600 rounded-full text-white font-bold shadow-[0_0_15px_rgba(220,38,38,0.5)] hover:bg-red-700 transition-colors flex items-center gap-2">
            <PhoneOff size={20} /> End Consultation
          </button>
          
          <button onClick={toggleVideo} className={`p-4 rounded-full transition-colors ${isVideoOff ? 'bg-red-500 text-white' : 'bg-gray-700 text-white hover:bg-gray-600'}`}>
            {isVideoOff ? <VideoOff size={20} /> : <Video size={20} />}
          </button>
        </div>
      </div>

      {/* Side Panel for EHR & Live Vitals */}
      <div className="w-96 flex flex-col gap-6">
        {/* Live Vitals Panel (Phase 15 placeholder) */}
        <div className={`rounded-3xl p-6 shadow-sm border flex-1 transition-colors ${vitalsActive ? 'bg-red-50 border-red-100' : 'bg-white border-gray-100'}`}>
          <h3 className="font-bold text-gray-800 mb-4 flex items-center gap-2">
            <Activity size={20} className={vitalsActive ? "text-red-500 animate-pulse" : "text-blue-500"}/> 
            Live Vitals (IoT)
          </h3>
          <div className="space-y-4">
            <div className="bg-white rounded-2xl p-4 border border-gray-100 flex justify-between items-center shadow-sm">
              <div>
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">Heart Rate</p>
                <p className="text-3xl font-black text-gray-800">{vitals.heartRate} <span className="text-sm font-medium text-gray-500">BPM</span></p>
              </div>
              <Activity size={32} className={`opacity-50 ${vitalsActive ? 'text-red-500' : 'text-red-400'}`} />
            </div>
            <div className="bg-white rounded-2xl p-4 border border-gray-100 flex justify-between items-center shadow-sm">
              <div>
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">SpO2</p>
                <p className="text-3xl font-black text-gray-800">{vitals.spO2} <span className="text-sm font-medium text-gray-500">%</span></p>
              </div>
              <Activity size={32} className={`opacity-50 ${vitalsActive ? 'text-blue-500' : 'text-blue-400'}`} />
            </div>
            {!vitalsActive && <div className="text-xs text-gray-400 text-center mt-4">Waiting for Smartwatch Sync...</div>}
            {vitalsActive && <div className="text-xs text-red-500 font-bold text-center mt-4 flex items-center justify-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span> Streaming Live via Socket.io</div>}
          </div>
        </div>

        {/* Quick EHR Snapshot */}
        <div className="bg-blue-600 rounded-3xl p-6 shadow-lg text-white flex-1">
          <h3 className="font-bold mb-4 flex items-center gap-2"><FileText size={20}/> Patient Context</h3>
          <p className="text-sm text-blue-100 mb-2"><span className="font-bold text-white">Patient:</span> {patientName}</p>
          <p className="text-sm text-blue-100 mb-2"><span className="font-bold text-white">Age:</span> 62</p>
          <p className="text-sm text-blue-100 mb-2"><span className="font-bold text-white">Pre-existing:</span> Hypertension</p>
          <div className="mt-4 p-3 bg-black/20 rounded-xl text-sm border border-white/10">
            <p className="font-bold mb-1 text-red-200">AI Triage Reason:</p>
            <p className="text-blue-50">"Severe chest pain radiating to left arm. High risk of cardiac event."</p>
          </div>
        </div>
      </div>
    </div>
  );
}
