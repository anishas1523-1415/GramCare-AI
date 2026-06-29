import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Activity, FileText, CreditCard, Camera, Phone, User, Settings, ArrowRight, HeartPulse, Moon, Zap, AlertTriangle, X, MapPin, Video } from 'lucide-react';
import './index.css';
import VideoCallScreen from './VideoCallScreen';

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('jwt_token'));
  const [activeTab, setActiveTab] = useState('triage');
  const [sosActive, setSosActive] = useState(false);
  const [inVideoCall, setInVideoCall] = useState(false);

  if (!token) {
    return <LoginScreen onLogin={(t) => setToken(t)} />;
  }

  return (
    <div className="w-full h-screen bg-[#F8FAFC] overflow-hidden flex flex-col font-sans relative">
      
      {/* Top Header */}
      <header className="pt-12 pb-4 px-6 bg-white/40 backdrop-blur-xl border-b border-white/50 shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex justify-between items-center z-10 relative">
        <div>
          <h1 className="text-2xl font-black text-gray-800 tracking-tight flex items-center gap-2">
            GramCare <span className="text-blue-500">AI</span>
          </h1>
          <p className="text-gray-500 font-medium text-sm">Welcome, Anish</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setSosActive(true)}
            className="w-12 h-12 rounded-full bg-red-500 text-white flex items-center justify-center shadow-[0_4px_16px_rgba(239,68,68,0.4)] animate-pulse"
          >
            <AlertTriangle size={24} strokeWidth={2.5} />
          </button>
          <button onClick={() => { localStorage.removeItem('jwt_token'); setToken(null); }} className="w-12 h-12 rounded-full neo-bg flex items-center justify-center shadow-neo-out border border-white/60">
            <User size={24} className="text-gray-600" />
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto pb-24 relative z-0">
        <AnimatePresence mode="wait">
          {inVideoCall && (
            <motion.div key="videoCall" initial={{opacity: 0, scale: 0.9}} animate={{opacity: 1, scale: 1}} exit={{opacity: 0, scale: 0.9}} className="absolute inset-0 z-40 bg-gray-900">
               <VideoCallScreen onEndCall={() => setInVideoCall(false)} />
            </motion.div>
          )}

          {!inVideoCall && activeTab === 'triage' && (
            <motion.div key="triage" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <TriageScreen onStartCall={() => setInVideoCall(true)} />
            </motion.div>
          )}
          {!inVideoCall && activeTab === 'vitals' && (
            <motion.div key="vitals" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <VitalsScreen />
            </motion.div>
          )}
          {!inVideoCall && activeTab === 'wallet' && (
            <motion.div key="wallet" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <WalletScreen token={token} />
            </motion.div>
          )}
          {!inVideoCall && activeTab === 'payments' && (
            <motion.div key="payments" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <PaymentsScreen />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* SOS Overlay */}
      <AnimatePresence>
        {sosActive && <EmergencyOverlay onClose={() => setSosActive(false)} />}
      </AnimatePresence>

      {/* Bottom Navigation */}
      <nav className="absolute bottom-0 w-full h-24 bg-white/60 backdrop-blur-2xl border-t border-white/50 shadow-[0_-8px_32px_rgba(0,0,0,0.04)] px-6 flex justify-between items-center z-20 pb-4">
        <NavBtn icon={<Activity />} label="Triage" active={activeTab === 'triage'} onClick={() => setActiveTab('triage')} />
        <NavBtn icon={<HeartPulse />} label="Vitals" active={activeTab === 'vitals'} onClick={() => setActiveTab('vitals')} />
        <NavBtn icon={<FileText />} label="EHR" active={activeTab === 'wallet'} onClick={() => setActiveTab('wallet')} />
        <NavBtn icon={<CreditCard />} label="Pay" active={activeTab === 'payments'} onClick={() => setActiveTab('payments')} />
      </nav>
    </div>
  );
}

function LoginScreen({ onLogin }: { onLogin: (t: string) => void }) {
  const [username, setUsername] = useState('P1');
  const [password, setPassword] = useState('password123');
  const [loading, setLoading] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString()
    })
    .then(res => res.json())
    .then(data => {
      setLoading(false);
      if (data.access_token) {
        localStorage.setItem('jwt_token', data.access_token);
        onLogin(data.access_token);
      } else {
        alert("Login failed: " + (data.detail || "Unknown error"));
      }
    })
    .catch(err => {
      setLoading(false);
      alert("Failed to connect to backend: " + err);
    });
  };

  return (
    <div className="w-full h-screen bg-[#F8FAFC] flex flex-col justify-center px-8 relative overflow-hidden">
      <div className="absolute top-[-100px] right-[-100px] w-64 h-64 bg-blue-400 rounded-full blur-[100px] opacity-40"></div>
      <div className="absolute bottom-[-100px] left-[-100px] w-64 h-64 bg-green-400 rounded-full blur-[100px] opacity-30"></div>
      
      <div className="mb-12 relative z-10">
        <h1 className="text-4xl font-black text-gray-800 tracking-tight flex items-center gap-2 mb-2">
          GramCare <span className="text-blue-500">AI</span>
        </h1>
        <p className="text-gray-500 font-medium">Secure Telemedicine Portal</p>
      </div>

      <form onSubmit={handleLogin} className="neo-bg p-8 rounded-[40px] shadow-neo-out border border-white/60 relative z-10">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Patient Login</h2>
        
        <div className="mb-4">
          <label className="block text-sm font-bold text-gray-500 mb-2">Patient ID (Username)</label>
          <input 
            type="text" 
            value={username}
            onChange={e => setUsername(e.target.value)}
            className="w-full bg-white/50 border border-white/80 rounded-2xl p-4 text-gray-800 shadow-neo-in outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <div className="mb-8">
          <label className="block text-sm font-bold text-gray-500 mb-2">Password</label>
          <input 
            type="password" 
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full bg-white/50 border border-white/80 rounded-2xl p-4 text-gray-800 shadow-neo-in outline-none focus:ring-2 focus:ring-blue-400"
          />
        </div>

        <button 
          disabled={loading}
          type="submit" 
          className="w-full py-4 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-2xl font-black text-lg shadow-[0_8px_24px_rgba(59,130,246,0.3)] active:scale-95 transition-transform disabled:opacity-50"
        >
          {loading ? 'Authenticating...' : 'Secure Login'}
        </button>
      </form>
    </div>
  );
}

// ----------------------------------------------------------------------
// Screens
// ----------------------------------------------------------------------

function VideoCallScreen({ onEndCall }: { onEndCall: () => void }) {
// [Truncated existing code logic]
  const localVideoRef = React.useRef<HTMLVideoElement>(null);
  const [callActive, setCallActive] = useState(false);

  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      .then((stream) => {
        if (localVideoRef.current) localVideoRef.current.srcObject = stream;
        setCallActive(true);
      })
      .catch((err) => console.error("Failed to access camera", err));

    return () => {
      if (localVideoRef.current && localVideoRef.current.srcObject) {
        const stream = localVideoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  return (
    <div className="w-full h-full bg-black relative flex flex-col">
      <div className="absolute top-12 left-6 z-10">
        <p className="text-white font-bold drop-shadow-md">Dr. Sarah Jenkins</p>
        <p className="text-green-400 text-sm font-bold flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span> Connected securely
        </p>
      </div>
      <div className="flex-1 bg-gray-800 flex items-center justify-center">
        {callActive ? (
          <p className="text-gray-500 font-bold">Waiting for Dr. Sarah to turn on camera...</p>
        ) : (
          <p className="text-gray-500 font-bold animate-pulse">Connecting to GramCare WebRTC Server...</p>
        )}
      </div>
      <div className="absolute bottom-32 right-6 w-32 h-48 bg-gray-900 rounded-2xl overflow-hidden border-2 border-white/20 shadow-2xl">
        <video ref={localVideoRef} autoPlay playsInline muted className="w-full h-full object-cover transform scale-x-[-1]" />
      </div>
      <div className="absolute bottom-12 w-full flex justify-center gap-6">
        <button className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white border border-white/30"><Mic size={24} /></button>
        <button onClick={onEndCall} className="w-16 h-16 rounded-full bg-red-600 flex items-center justify-center text-white shadow-[0_4px_16px_rgba(220,38,38,0.4)]"><Phone size={28} className="transform rotate-[135deg]" /></button>
        <button className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center text-white border border-white/30"><Camera size={24} /></button>
      </div>
    </div>
  );
}

function TriageScreen({ onStartCall }: { onStartCall?: () => void }) {
  const [scanning, setScanning] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [messages, setMessages] = useState<any[]>([]);
  const [inputText, setInputText] = useState("");
  const [showTelehealthBtn, setShowTelehealthBtn] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const startChat = (type: string) => {
    setIsChatting(true);
    setMessages([
      { 
        type: 'bot', 
        content: 'Hello! I am GramCare AI. How are you feeling today? Please describe your symptoms.', 
        isDisclaimer: true,
        disclaimer: "DISCLAIMER: This is an AI assessment tool, not a substitute for professional medical advice. Call emergency services immediately if you are experiencing a medical emergency."
      }
    ]);
  };

  const handleSend = () => {
    if (!inputText.trim()) return;
    const newMsg = { type: 'user', content: inputText };
    setMessages(prev => [...prev, newMsg]);
    setInputText("");
    setIsProcessing(true);
    
    // Call real Backend AI Triage Endpoint
    fetch('http://localhost:8000/api/v1/triage/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symptoms_text: newMsg.content,
        patient_id: "P1", // Hardcoded for now
        age: 35 // Hardcoded for MVP
      })
    })
    .then(res => res.json())
    .then(data => {
      setIsProcessing(false);
      
      const botResponse = { 
        type: 'bot', 
        content: `Based on your symptoms, this could be: **${data.predicted_condition}**.\n\n` + 
                 `${data.doctor_recommendation}\n\n` +
                 `Suggested Care: ${data.home_remedies}`,
        isExplainable: true, 
        explanation: data.explanation,
        confidence: data.confidence_score,
        severity: data.severity_score
      };
      
      setMessages(prev => [...prev, botResponse]);
      
      if (data.severity_score >= 50) {
        setShowTelehealthBtn(true);
      }
    })
    .catch(err => {
      setIsProcessing(false);
      setMessages(prev => [...prev, { type: 'bot', content: 'Sorry, I am currently unable to reach the AI Engine. Please try again or contact a doctor directly.' }]);
    });
  };

  return (
    <div className="p-6 h-full flex flex-col relative">
      <AnimatePresence mode="wait">
        {scanning ? (
          <motion.div key="scan" initial={{opacity: 0}} animate={{opacity: 1}} exit={{opacity: 0}} className="absolute inset-0 bg-[#F8FAFC] z-10 flex flex-col items-center justify-center p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-8">Scanning Image...</h2>
            <div className="w-64 h-64 border-4 border-dashed border-blue-400 rounded-3xl relative overflow-hidden bg-blue-50">
              <div className="absolute top-0 w-full h-2 bg-blue-500 shadow-[0_0_20px_rgba(59,130,246,1)] animate-[scan_2s_ease-in-out_infinite]" />
              <div className="absolute inset-0 flex items-center justify-center text-blue-300">
                <Camera size={64} />
              </div>
            </div>
            <p className="text-gray-500 mt-8 text-center px-4">GramCare AI is analyzing your symptom photo...</p>
          </motion.div>
        ) : isChatting ? (
          <motion.div key="chat" initial={{opacity: 0, scale: 0.95}} animate={{opacity: 1, scale: 1}} className="flex flex-col h-full">
            <div className="flex-1 overflow-y-auto space-y-4 pb-4 pr-2">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[85%] rounded-3xl p-4 ${msg.type === 'user' ? 'bg-blue-600 text-white rounded-br-sm shadow-[0_4px_16px_rgba(37,99,235,0.3)]' : 'bg-white border border-white/60 text-gray-800 rounded-bl-sm shadow-neo-out'}`}>
                    
                    {msg.isDisclaimer && (
                      <div className="mb-3 p-3 bg-red-50/80 rounded-2xl border border-red-100 flex items-start gap-2">
                        <AlertTriangle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                        <p className="text-[10px] font-bold text-red-600 leading-tight">{msg.disclaimer}</p>
                      </div>
                    )}
                    
                    <p className="text-gray-700 font-medium whitespace-pre-wrap">{msg.content}</p>
                    
                    {msg.isExplainable && (
                      <div className="mt-4 pt-3 border-t border-gray-100">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-[10px] font-black text-blue-600 tracking-wider uppercase flex items-center gap-1">
                            <Zap size={12} /> Explainable AI
                          </div>
                          <div className={`text-[10px] font-bold px-2 py-1 rounded-full ${msg.severity >= 75 ? 'bg-red-100 text-red-700' : msg.severity >= 50 ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
                            Severity: {msg.severity}/100
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 font-medium italic mb-2">"{msg.explanation}"</p>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] text-gray-400 font-bold">Confidence Score</span>
                          <span className="text-[10px] text-gray-600 font-black">{(msg.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-gray-100 h-1.5 rounded-full mt-1 overflow-hidden">
                          <div className="bg-blue-500 h-full rounded-full" style={{width: `${msg.confidence * 100}%`}}></div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isProcessing && (
                <div className="flex justify-start">
                  <div className="bg-white border border-white/60 rounded-3xl rounded-bl-sm p-4 shadow-neo-out flex items-center gap-2">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay: '150ms'}}></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{animationDelay: '300ms'}}></span>
                  </div>
                </div>
              )}
            </div>
            
            {showTelehealthBtn && (
              <div className="pb-4">
                <button onClick={onStartCall} className="w-full py-4 bg-green-500 text-white rounded-2xl font-bold shadow-[0_8px_24px_rgba(34,197,94,0.3)] flex items-center justify-center gap-2 animate-bounce">
                  <Phone size={20} /> Consult Doctor via Telehealth
                </button>
              </div>
            )}
            
            <div className="pt-2 flex gap-2 relative z-10">
              <input type="text" value={inputText} onChange={(e) => setInputText(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && handleSend()} placeholder="Type your symptoms..." className="flex-1 neo-bg rounded-full px-6 py-4 shadow-neo-in border-none outline-none text-gray-700" disabled={isProcessing} />
              <button onClick={handleSend} disabled={isProcessing} className="w-14 h-14 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-[0_4px_12px_rgba(37,99,235,0.3)] disabled:opacity-50"><ArrowRight size={24} /></button>
            </div>
          </motion.div>
        ) : (
          <motion.div key="home" className="h-full flex flex-col items-center justify-center">
            <div className="w-full neo-bg rounded-[40px] p-8 shadow-neo-out border border-white/60 flex flex-col items-center">
              <h2 className="text-2xl font-bold text-gray-800 mb-2">How can I help?</h2>
              <p className="text-gray-500 text-center mb-10">Tap to speak or type your symptoms.</p>
              <button onClick={() => startChat('voice')} className="w-32 h-32 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-[0_12px_32px_rgba(59,130,246,0.4)] relative mb-8 active:scale-95 transition-transform">
                <div className="absolute inset-0 rounded-full border-[6px] border-blue-400/30 animate-ping"></div>
                <Mic size={48} className="text-white" />
              </button>
              <div className="flex w-full gap-4">
                <button onClick={() => startChat('text')} className="flex-1 py-4 neo-bg rounded-2xl shadow-neo-out border border-white/60 font-bold text-gray-700 flex items-center justify-center gap-2 active:shadow-neo-in transition-all"><FileText size={20} className="text-blue-500" /> Type Symptoms</button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

import localforage from 'localforage';

function WalletScreen({ token }: { token: string }) {
  const [ocrScanning, setOcrScanning] = useState(false);
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [ocrResult, setOcrResult] = useState<any>(null);

  useEffect(() => {
    // 1. First, try to load cached data to show immediately
    localforage.getItem('ehr_records').then((cachedData) => {
      if (cachedData) {
        setRecords(cachedData as any[]);
        setLoading(false);
      }
    });

    // 2. Fetch fresh data from backend
    fetch('http://localhost:8000/api/v1/ehr/patient/P1', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
      .then(res => {
        if (!res.ok) throw new Error("Unauthorized or Network Error");
        return res.json();
      })
      .then(data => {
        setRecords(data);
        localforage.setItem('ehr_records', data); // Cache the fresh data
        setLoading(false);
        setIsOffline(false);
      })
      .catch(err => {
        console.error("Failed to fetch EHR records, using offline cache.", err);
        setIsOffline(true);
        setLoading(false);
      });
  }, [token]);

  const handleScan = () => {
    setOcrScanning(true);
    setOcrResult(null);
    
    // Call the real backend OCR endpoint
    fetch('http://localhost:8000/api/v1/triage/ocr', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: "dummy_base64_data_representing_image" })
    })
    .then(res => res.json())
    .then(data => {
      setOcrResult(data);
      // Automatically add it to the UI (In a real app, we'd confirm first)
      const newRecord = {
        medicines: data.medicines_parsed.join(', '),
        doctor_id: "AI Extracted (Unverified)",
        timestamp: new Date().toISOString(),
        notes: "Extracted via AI OCR."
      };
      setRecords([newRecord, ...records]);
      setTimeout(() => setOcrScanning(false), 3000);
    })
    .catch(err => {
      console.error(err);
      setOcrScanning(false);
    });
  };

  return (
    <div className="p-6 h-full flex flex-col relative">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-black text-gray-800">Health Wallet</h2>
        <button onClick={handleScan} className="w-12 h-12 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center shadow-sm">
          <Camera size={20} />
        </button>
      </div>

      {isOffline && (
        <div className="mb-4 bg-orange-100 text-orange-700 p-3 rounded-xl flex items-center gap-2 text-sm font-bold border border-orange-200">
          <AlertTriangle size={16} /> Offline Mode: Showing locally saved records.
        </div>
      )}

      <AnimatePresence>
        {ocrScanning ? (
          <motion.div initial={{opacity: 0, y: 20}} animate={{opacity: 1, y: 0}} exit={{opacity: 0, y: 20}} className="w-full neo-bg p-6 rounded-3xl shadow-neo-out border border-white/60 mb-6 flex flex-col items-center">
             <div className="w-full h-32 border-2 border-dashed border-gray-300 rounded-2xl mb-4 flex flex-col items-center justify-center text-gray-400 relative overflow-hidden bg-gray-50">
                <div className="absolute top-0 w-full h-1 bg-green-500 shadow-[0_0_15px_rgba(34,197,94,1)] animate-[scan_1.5s_ease-in-out_infinite]" />
                <FileText size={32} className="mb-2" />
                <span className="text-sm font-bold">Scanning Paper Prescription...</span>
             </div>
             {ocrResult ? (
               <div className="text-center">
                 <p className="text-green-600 font-bold mb-2">Extraction Successful ({ocrResult.confidence * 100}% Confidence)</p>
                 <div className="bg-gray-100 p-3 rounded-xl text-left text-xs text-gray-600 mb-4 whitespace-pre-wrap">
                   {ocrResult.extracted_text}
                 </div>
               </div>
             ) : (
               <p className="text-xs text-center text-gray-500 mb-4">AI is extracting medicine names and dosages automatically.</p>
             )}
             <button onClick={() => setOcrScanning(false)} className="px-6 py-2 bg-gray-200 text-gray-700 font-bold rounded-full text-sm">Close</button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="space-y-4">
        {loading ? (
          <p className="text-center text-gray-500 animate-pulse mt-10">Fetching secure records from backend...</p>
        ) : records.length === 0 ? (
          <div className="text-center text-gray-500 mt-10">
            <FileText size={48} className="mx-auto mb-4 opacity-50" />
            <p>No health records found.</p>
          </div>
        ) : (
          records.map((record, idx) => (
            <div key={idx} className="neo-bg p-5 rounded-3xl shadow-neo-out border border-white/60 flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600">
                <FileText size={24} />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-gray-800 line-clamp-1">{record.medicines}</h3>
                <p className="text-sm text-gray-500">{record.doctor_id} • {new Date(record.timestamp).toLocaleDateString()}</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function PaymentsScreen() {
  return (
    <div className="p-6">
      <h2 className="text-3xl font-black text-gray-800 mb-6">Payments</h2>
      <div className="neo-bg p-6 rounded-3xl shadow-neo-out border border-white/60">
        <p className="text-gray-500 mb-2">Pending Dues</p>
        <p className="text-4xl font-black text-gray-800 mb-6">₹ 150</p>
        <button className="w-full py-4 bg-blue-600 text-white rounded-2xl font-bold shadow-lg">Pay via UPI</button>
      </div>
    </div>
  );
}

function NavBtn({ icon, label, active, onClick }: any) {
  return (
    <button onClick={onClick} className="flex flex-col items-center justify-center gap-1 w-16">
      <div className={`p-3 rounded-2xl transition-all duration-300 ${active ? 'neo-bg shadow-neo-in text-blue-600' : 'text-gray-400'}`}>
        {icon}
      </div>
      <span className={`text-[10px] font-bold ${active ? 'text-blue-600' : 'text-gray-400'}`}>{label}</span>
    </button>
  );
}
