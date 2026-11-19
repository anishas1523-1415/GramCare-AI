import 'package:flutter/material.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:provider/provider.dart';
import 'package:socket_io_client/socket_io_client.dart' as io;
import 'package:go_router/go_router.dart';

import '../services/app_strings.dart';
import '../services/secure_store.dart';
import '../theme/app_theme.dart';

/// Signaling server for the WebRTC handshake — the same Node service the
/// web portal's doctor dashboard connects to
/// (frontend/patient_web_portal/.../doctor/dashboard/page.tsx's WS_URL).
/// This screen previously hardcoded 'http://10.0.2.2:4000' — the special
/// alias an ANDROID EMULATOR uses to reach its host machine's localhost —
/// which is meaningless on a real physical device (what this app actually
/// ships to) and doesn't point at any deployed signaling server anyway.
/// Every real video consultation attempt would have failed to connect.
const String _signalingUrl = 'https://gramcare-signaling.onrender.com';

class VideoConsultationScreen extends StatefulWidget {
  final int appointmentId;
  const VideoConsultationScreen({super.key, required this.appointmentId});

  @override
  State<VideoConsultationScreen> createState() => _VideoConsultationScreenState();
}

class _VideoConsultationScreenState extends State<VideoConsultationScreen> {
  final RTCVideoRenderer _localRenderer = RTCVideoRenderer();
  final RTCVideoRenderer _remoteRenderer = RTCVideoRenderer();
  
  io.Socket? _socket;
  RTCPeerConnection? _peerConnection;
  MediaStream? _localStream;
  
  bool _isMuted = false;
  bool _isVideoOff = false;
  bool _isConnected = false;
  // A failure in _startMedia() was debugPrint only, so a denied camera or
  // any WebRTC error left this screen spinning on black forever with no
  // message and no way out. _callError drives a real panel with a retry.
  String? _callError;

  @override
  void initState() {
    super.initState();
    _initRenderers();
    _connect();
  }

  @override
  void dispose() {
    _localRenderer.dispose();
    _remoteRenderer.dispose();
    _localStream?.dispose();
    _peerConnection?.dispose();
    _socket?.disconnect();
    super.dispose();
  }

  Future<void> _initRenderers() async {
    await _localRenderer.initialize();
    await _remoteRenderer.initialize();
  }

  Future<void> _connect() async {
    final token = await SecureStore().getToken();
    final roomId = widget.appointmentId.toString();
    
    // Connect to Signaling Server
    _socket = io.io(_signalingUrl, io.OptionBuilder()
        .setTransports(['websocket'])
        .setAuth({'token': token})
        .build());

    _socket?.onConnect((_) async {
      debugPrint('Connected to signaling server');
      await _startMedia();
      _socket?.emit('join_room', roomId);
    });

    _socket?.on('user_joined', (_) async {
      // I am the initiator
      if (_peerConnection == null) return;
      final offer = await _peerConnection!.createOffer();
      await _peerConnection!.setLocalDescription(offer);
      _socket?.emit('offer', {'offer': offer.toMap(), 'roomId': roomId});
    });

    _socket?.on('offer', (data) async {
      if (_peerConnection == null) return;
      final desc = RTCSessionDescription(data['offer']['sdp'], data['offer']['type']);
      await _peerConnection!.setRemoteDescription(desc);
      final answer = await _peerConnection!.createAnswer();
      await _peerConnection!.setLocalDescription(answer);
      _socket?.emit('answer', {'answer': answer.toMap(), 'roomId': roomId});
    });

    _socket?.on('answer', (data) async {
      if (_peerConnection == null) return;
      final desc = RTCSessionDescription(data['answer']['sdp'], data['answer']['type']);
      await _peerConnection!.setRemoteDescription(desc);
    });

    _socket?.on('ice_candidate', (data) async {
      if (_peerConnection == null) return;
      final candidate = RTCIceCandidate(
          data['candidate']['candidate'],
          data['candidate']['sdpMid'],
          data['candidate']['sdpMLineIndex']);
      await _peerConnection!.addCandidate(candidate);
    });
    
    _socket?.connect();
  }

  Future<void> _startMedia() async {
    final mediaConstraints = {
      'audio': true,
      'video': {
        'facingMode': 'user',
      }
    };
    
    try {
      _localStream = await navigator.mediaDevices.getUserMedia(mediaConstraints);
      _localRenderer.srcObject = _localStream;
      
      final configuration = {
        'iceServers': [
          {'urls': 'stun:stun.l.google.com:19302'},
        ]
      };
      
      _peerConnection = await createPeerConnection(configuration);
      
      _peerConnection!.onIceCandidate = (candidate) {
        _socket?.emit('ice_candidate', {
          'candidate': candidate.toMap(),
          'roomId': widget.appointmentId.toString(),
        });
      };
      
      _peerConnection!.onAddStream = (stream) {
        _remoteRenderer.srcObject = stream;
        setState(() {
          _isConnected = true;
        });
      };
      
      _localStream!.getTracks().forEach((track) {
        _peerConnection!.addTrack(track, _localStream!);
      });
      
    } catch (e) {
      debugPrint('Failed to start media: $e');
      if (!mounted) return;
      final message = e.toString().toLowerCase();
      setState(() {
        if (message.contains('permission') || message.contains('notallowed')) {
          _callError = 'Camera and microphone permission was denied. '
              'Allow them in Settings, then try again.';
        } else if (message.contains('notfound')) {
          _callError = 'No camera or microphone was found on this device.';
        } else {
          _callError = 'The call could not be started on this device.';
        }
      });
    }
  }

  Future<void> _retryCall() async {
    setState(() => _callError = null);
    await _startMedia();
  }

  void _toggleMute() {
    setState(() {
      _isMuted = !_isMuted;
    });
    _localStream?.getAudioTracks().forEach((track) {
      track.enabled = !_isMuted;
    });
  }

  void _toggleVideo() {
    setState(() {
      _isVideoOff = !_isVideoOff;
    });
    _localStream?.getVideoTracks().forEach((track) {
      track.enabled = !_isVideoOff;
    });
  }
  
  void _endCall() {
    context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(locale.t('video_consultation'), style: const TextStyle(color: Colors.white)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      extendBodyBehindAppBar: true,
      body: Stack(
        children: [
          // Remote Video
          Positioned.fill(
            child: _callError != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 32),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.videocam_off, color: Colors.redAccent, size: 44),
                          const SizedBox(height: 16),
                          const Text(
                            'Cannot start the call',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _callError!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white70, fontSize: 14),
                          ),
                          const SizedBox(height: 20),
                          ElevatedButton(
                            onPressed: _retryCall,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF2DD4BF),
                              foregroundColor: Colors.black,
                            ),
                            child: const Text('Try again'),
                          ),
                        ],
                      ),
                    ),
                  )
                : _isConnected 
              ? RTCVideoView(_remoteRenderer, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover)
              : const Center(child: CircularProgressIndicator(color: AppTheme.primaryBlue)),
          ),
          
          // Local Video Picture-in-Picture
          Positioned(
            right: 20,
            bottom: 120,
            width: 120,
            height: 160,
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white38, width: 2),
                color: Colors.black54,
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: RTCVideoView(_localRenderer, mirror: true, objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover),
              ),
            ),
          ),
          
          // Controls
          Positioned(
            left: 0,
            right: 0,
            bottom: 40,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                FloatingActionButton(
                  heroTag: 'audio',
                  backgroundColor: _isMuted ? Colors.red : Colors.white24,
                  onPressed: _toggleMute,
                  child: Icon(_isMuted ? Icons.mic_off : Icons.mic, color: Colors.white),
                ),
                FloatingActionButton(
                  heroTag: 'video',
                  backgroundColor: _isVideoOff ? Colors.red : Colors.white24,
                  onPressed: _toggleVideo,
                  child: Icon(_isVideoOff ? Icons.videocam_off : Icons.videocam, color: Colors.white),
                ),
                FloatingActionButton(
                  heroTag: 'end',
                  backgroundColor: AppTheme.cancelledRed,
                  onPressed: _endCall,
                  child: const Icon(Icons.call_end, color: Colors.white),
                ),
              ],
            ),
          )
        ],
      ),
    );
  }
}
