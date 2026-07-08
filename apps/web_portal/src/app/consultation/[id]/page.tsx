"use client";

import React, { use, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Mic, MicOff, Video, VideoOff, PhoneOff, MonitorUp, Activity, Wifi, WifiOff, MessageSquare, Send } from 'lucide-react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from '../../../contexts/AuthContext';
import { useRouter } from 'next/navigation';

type CallMode = 'video' | 'audio' | 'text';
type NetworkQuality = 'good' | 'poor' | 'critical';

interface ChatMessage {
  text: string;
  from: string;
  at: string;
  mine: boolean;
}

// See doctor/prescription/[appointmentId]/page.tsx for why `params` must be
// unwrapped with `use()` on this Next.js version rather than destructured
// synchronously.
export default function ConsultationRoom({ params }: { params: Promise<{ id: string }> }) {
  const { id: roomId } = use(params);
  const { user } = useAuth();
  const router = useRouter();

  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isScreenSharing, setIsScreenSharing] = useState(false);

  // Adaptive Bandwidth Switching (planning doc: video -> audio -> text as
  // network quality degrades, so a poor rural connection degrades gracefully
  // instead of dropping the consultation entirely).
  const [callMode, setCallMode] = useState<CallMode>('video');
  const [networkQuality, setNetworkQuality] = useState<NetworkQuality>('good');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const modeRef = useRef<CallMode>('video');
  const streakRef = useRef(0); // consecutive readings pushing toward a mode change (+ = degrade, - = recover)

  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);

  const socketRef = useRef<Socket | null>(null);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  // The original camera track, kept aside while screen-sharing so it can be
  // restored on stop (either via our own button or the browser's native
  // "Stop sharing" bar, which only fires the track's `onended`).
  const cameraTrackRef = useRef<MediaStreamTrack | null>(null);

  // Applies an Adaptive Bandwidth Switching transition: enables/disables the
  // local audio/video tracks to match the target mode and updates state.
  // Only touches refs/setters, so it's safe to close over from the stats
  // interval below without a stale-closure dependency on `roomId`.
  const applyCallMode = (next: CallMode) => {
    const videoTrack = localStreamRef.current?.getVideoTracks()[0];
    const audioTrack = localStreamRef.current?.getAudioTracks()[0];
    if (videoTrack) videoTrack.enabled = next === 'video';
    if (audioTrack) audioTrack.enabled = next !== 'text';
    setIsVideoOff(next !== 'video');
    setIsMuted(next === 'text');
    setCallMode(next);
    modeRef.current = next;
  };

  useEffect(() => {
    // Connect to Signaling Server. join_room/offer/answer/ice_candidate now
    // require an authenticated socket on the server side, so pass the same
    // access token used for REST calls.
    const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "https://gramcare-signaling.onrender.com";
    socketRef.current = io(WS_URL, {
      auth: { token: localStorage.getItem('access_token') },
    });

    // Initialize Media
    const startMedia = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        localStreamRef.current = stream;
        cameraTrackRef.current = stream.getVideoTracks()[0] ?? null;
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }

        // Join Room
        socketRef.current?.emit("join_room", roomId);

        // WebRTC Setup - Fetch dynamic TURN credentials from signaling server
        let iceServers = [{ urls: "stun:stun.l.google.com:19302" }]; // fallback
        try {
          // WS_URL is our signaling server (e.g. localhost:4000) where the /api/webrtc/turn-credentials route lives
          const res = await fetch(`${WS_URL}/api/webrtc/turn-credentials`);
          const data = await res.json();
          if (data.iceServers && Array.isArray(data.iceServers) && data.iceServers.length > 0) {
            iceServers = data.iceServers;
          }
        } catch (e) {
          console.warn("Failed to fetch TURN credentials from signaling server, using basic STUN fallback", e);
        }

        peerRef.current = new RTCPeerConnection({ iceServers });

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

        socketRef.current?.on("chat_message", (msg: { text: string; from: string; at: string }) => {
          setChatMessages((prev) => [...prev, { ...msg, mine: false }]);
        });

      } catch (err) {
        console.error("Media error:", err);
      }
    };

    startMedia();

    // Poll WebRTC stats every 4s and auto-degrade/recover the call mode.
    // Hysteresis (3 consecutive readings) avoids flapping on a single blip.
    const statsInterval = setInterval(async () => {
      const pc = peerRef.current;
      if (!pc || pc.connectionState !== 'connected') return;

      let packetsLost = 0;
      let packetsReceived = 0;
      let rttMs = 0;
      try {
        const stats = await pc.getStats();
        stats.forEach((report) => {
          if (report.type === 'inbound-rtp' && !report.isRemote) {
            packetsLost += report.packetsLost || 0;
            packetsReceived += report.packetsReceived || 0;
          }
          if (report.type === 'candidate-pair' && report.state === 'succeeded' && report.currentRoundTripTime != null) {
            rttMs = Math.max(rttMs, report.currentRoundTripTime * 1000);
          }
        });
      } catch {
        return; // getStats unsupported/failed — leave mode as-is
      }

      const totalPackets = packetsLost + packetsReceived;
      const lossRatio = totalPackets > 0 ? packetsLost / totalPackets : 0;

      const tier: NetworkQuality =
        lossRatio > 0.3 || rttMs > 1000 ? 'critical'
        : lossRatio > 0.1 || rttMs > 400 ? 'poor'
        : 'good';
      setNetworkQuality(tier);

      const current = modeRef.current;
      const desired: CallMode = tier === 'critical' ? 'text' : tier === 'poor' ? 'audio' : 'video';

      if (desired === current) {
        streakRef.current = 0;
        return;
      }
      // desired < current (worse) increments toward degrading; desired > current (better) toward recovering.
      const rank: Record<CallMode, number> = { video: 2, audio: 1, text: 0 };
      const degrading = rank[desired] < rank[current];
      streakRef.current = degrading ? Math.max(1, streakRef.current + 1) : Math.min(-1, streakRef.current - 1);

      const REQUIRED_STREAK = 3;
      if (degrading && streakRef.current >= REQUIRED_STREAK) {
        applyCallMode(desired);
        streakRef.current = 0;
      } else if (!degrading && streakRef.current <= -REQUIRED_STREAK) {
        // Recover only one step at a time (video is only reachable from audio, not straight from text).
        const nextUp: CallMode = current === 'text' ? 'audio' : 'video';
        applyCallMode(nextUp);
        streakRef.current = 0;
      }
    }, 4000);

    return () => {
      // Cleanup
      clearInterval(statsInterval);
      localStreamRef.current?.getTracks().forEach(t => t.stop());
      peerRef.current?.close();
      socketRef.current?.disconnect();
    };
  }, [roomId]);

  const sendChatMessage = () => {
    const text = chatInput.trim();
    if (!text) return;
    socketRef.current?.emit('chat_message', { roomId, text });
    setChatMessages((prev) => [...prev, { text, from: 'me', at: new Date().toISOString(), mine: true }]);
    setChatInput('');
  };

  // Previously read `isMuted`/`isVideoOff` (the state BEFORE this toggle) to
  // set `.enabled`, then flipped the state after — it happened to produce
  // the right result only because of a double-negative coincidence
  // (enabled = wasMuted, then isMuted = !wasMuted, so enabled ends up ==
  // !isMutedNew). It also had no guard: if getAudioTracks()/getVideoTracks()
  // returned an empty array (mic/camera permission denied, or an
  // audio-only/video-only stream), `[0]` was undefined and `.enabled = ...`
  // threw. Now computes the new state first and guards against missing
  // tracks.
  const toggleMute = () => {
    const track = localStreamRef.current?.getAudioTracks()[0];
    if (!track) return;
    const nextMuted = !isMuted;
    track.enabled = !nextMuted;
    setIsMuted(nextMuted);
  };

  const toggleVideo = () => {
    const track = localStreamRef.current?.getVideoTracks()[0];
    if (!track) return;
    const nextVideoOff = !isVideoOff;
    track.enabled = !nextVideoOff;
    setIsVideoOff(nextVideoOff);
  };

  // Screen share: swaps the outgoing video track on the existing peer
  // connection (renegotiation-free via replaceTrack) so the remote party
  // sees the screen without a new offer/answer round-trip.
  const stopScreenShare = () => {
    const camTrack = cameraTrackRef.current;
    const sender = peerRef.current?.getSenders().find((s) => s.track?.kind === 'video');
    if (sender && camTrack) sender.replaceTrack(camTrack);
    if (localStreamRef.current && camTrack) {
      localStreamRef.current.getVideoTracks().forEach((t) => {
        if (t !== camTrack) {
          localStreamRef.current?.removeTrack(t);
          t.stop();
        }
      });
      localStreamRef.current.addTrack(camTrack);
      if (localVideoRef.current) localVideoRef.current.srcObject = localStreamRef.current;
    }
    setIsScreenSharing(false);
  };

  const toggleScreenShare = async () => {
    if (isScreenSharing) {
      stopScreenShare();
      return;
    }
    try {
      const displayStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const screenTrack = displayStream.getVideoTracks()[0];
      const sender = peerRef.current?.getSenders().find((s) => s.track?.kind === 'video');
      if (sender) await sender.replaceTrack(screenTrack);
      if (localStreamRef.current) {
        localStreamRef.current.getVideoTracks().forEach((t) => localStreamRef.current?.removeTrack(t));
        localStreamRef.current.addTrack(screenTrack);
        if (localVideoRef.current) localVideoRef.current.srcObject = localStreamRef.current;
      }
      // Browser's own "Stop sharing" control only notifies via this event.
      screenTrack.onended = () => stopScreenShare();
      setIsScreenSharing(true);
    } catch {
      // Permission denied or unsupported — no-op, stays on camera.
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

  const qualityBadge = {
    good: { label: 'Good connection', className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50', icon: Wifi },
    poor: { label: 'Poor connection', className: 'bg-orange-500/20 text-orange-400 border-orange-500/50', icon: Wifi },
    critical: { label: 'Very poor connection', className: 'bg-red-500/20 text-red-400 border-red-500/50', icon: WifiOff },
  }[networkQuality];
  const QualityIcon = qualityBadge.icon;

  return (
    <div className="min-h-screen bg-black flex flex-col relative overflow-hidden">
      {/* Remote Video (Full Screen) — replaced by text chat once Adaptive
          Bandwidth Switching drops all the way down (planning doc: video ->
          audio -> text as the connection degrades). */}
      <div className="absolute inset-0 z-0 flex items-center justify-center bg-gray-900">
        {callMode === 'text' ? (
          <div className="w-full h-full flex flex-col p-6 pt-28 pb-32 max-w-2xl mx-auto">
            <div className="flex-1 overflow-y-auto space-y-3 mb-4">
              {chatMessages.length === 0 ? (
                <p className="text-center text-white/40 mt-10">
                  Connection is too weak for audio/video — continuing by text.
                </p>
              ) : (
                chatMessages.map((m, i) => (
                  <div key={i} className={`max-w-[75%] p-3 rounded-2xl text-sm ${m.mine ? 'ml-auto bg-teal-500 text-white' : 'bg-white/10 text-white'}`}>
                    {m.text}
                  </div>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendChatMessage()}
                placeholder="Type a message…"
                className="flex-1 p-3 rounded-xl bg-white/10 text-white placeholder-white/40 border border-white/20 focus:outline-none focus:ring-2 focus:ring-teal-400"
              />
              <button onClick={sendChatMessage} className="w-12 h-12 rounded-xl bg-teal-500 text-white flex items-center justify-center shrink-0">
                <Send size={18} />
              </button>
            </div>
          </div>
        ) : (
          <>
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
              className={`w-full h-full object-cover ${!isConnected || callMode === 'audio' ? 'hidden' : ''}`}
            />
            {isConnected && callMode === 'audio' && (
              <div className="flex flex-col items-center text-white/70 gap-3">
                <WifiOff size={48} className="text-orange-400" />
                <p className="font-semibold">Audio-only — weak connection detected</p>
                <p className="text-sm text-white/40">Video will resume automatically once the connection improves.</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Header Overlay */}
      <div className="relative z-10 p-6 flex justify-between items-center bg-gradient-to-b from-black/80 to-transparent">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="text-teal-400" /> Tele-ICU Consultation
          </h1>
          <p className="text-white/70 text-sm">Room: {roomId}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-2 ${qualityBadge.className}`}>
            <QualityIcon size={14} /> {qualityBadge.label}
          </div>
          <div className="bg-red-500/20 text-red-500 px-4 py-1 rounded-full text-sm font-bold border border-red-500/50 flex items-center gap-2 animate-pulse">
            <div className="w-2 h-2 bg-red-500 rounded-full" /> LIVE
          </div>
        </div>
      </div>

      {/* Local Video Picture-in-Picture */}
      {callMode !== 'text' && (
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
      )}

      {/* Controls Footer */}
      <div className="mt-auto relative z-10 p-8 flex justify-center items-center gap-6 bg-gradient-to-t from-black/80 to-transparent">
        <button
          onClick={toggleMute}
          aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
          aria-pressed={isMuted}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isMuted ? 'bg-red-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
        </button>

        <button
          onClick={toggleVideo}
          aria-label={isVideoOff ? 'Turn camera on' : 'Turn camera off'}
          aria-pressed={isVideoOff}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isVideoOff ? 'bg-red-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          {isVideoOff ? <VideoOff size={24} /> : <Video size={24} />}
        </button>

        <button
          onClick={toggleScreenShare}
          title={isScreenSharing ? 'Stop sharing your screen' : 'Share your screen'}
          aria-label={isScreenSharing ? 'Stop sharing your screen' : 'Share your screen'}
          aria-pressed={isScreenSharing}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${isScreenSharing ? 'bg-teal-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          <MonitorUp size={24} />
        </button>

        <button
          onClick={() => applyCallMode(callMode === 'text' ? 'video' : 'text')}
          title={callMode === 'text' ? 'Return to video' : 'Switch to text chat'}
          aria-label={callMode === 'text' ? 'Return to video call' : 'Switch to text chat (for low bandwidth)'}
          aria-pressed={callMode === 'text'}
          className={`w-14 h-14 rounded-full flex items-center justify-center transition-colors ${callMode === 'text' ? 'bg-teal-500 text-white' : 'bg-white/20 text-white hover:bg-white/30 backdrop-blur-md'}`}
        >
          <MessageSquare size={24} />
        </button>

        <button
          onClick={endCall}
          aria-label="End call"
          className="w-16 h-16 rounded-full flex items-center justify-center bg-red-600 hover:bg-red-700 text-white shadow-lg transition-transform hover:scale-110"
        >
          <PhoneOff size={28} />
        </button>
      </div>
    </div>
  );
}
