"use client";
import React, { useState, useEffect } from 'react';
import { Activity, Users, Calendar, AlertTriangle, Search, Bell, FileText, Plus, Video, PhoneCall } from 'lucide-react';
import ConsultationRoom from '../ConsultationRoom';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [inVideoCall, setInVideoCall] = useState(false);

  if (inVideoCall) {
    return (
      <div className="w-full h-screen bg-gray-50 flex flex-col font-sans">
        <header className="h-16 bg-white border-b border-gray-200 flex justify-between items-center px-6">
          <div className="flex items-center gap-2">
            <Video className="text-red-500" />
            <h1 className="text-xl font-black text-gray-800 tracking-tight">Active Emergency Consultation</h1>
          </div>
        </header>
        <div className="flex-1 overflow-hidden">
           <ConsultationRoom onEndCall={() => setInVideoCall(false)} patientName="Mrs. Lakshmi" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#f0f4f8] text-gray-800 font-sans">
      
      {/* Sidebar - Glassmorphism */}
      <aside className="w-64 bg-white/40 backdrop-blur-xl border-r border-white/50 p-6 flex flex-col gap-8 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
        <div className="flex items-center gap-3 text-blue-600">
          <Activity size={32} strokeWidth={2.5} />
          <h1 className="text-2xl font-bold tracking-tight">GramCare</h1>
        </div>
        
        <nav className="flex flex-col gap-2">
          <NavItem icon={<Activity />} label="Dashboard" active={activeTab === "Dashboard"} onClick={() => setActiveTab("Dashboard")} />
          <NavItem icon={<Calendar />} label="Appointments" active={activeTab === "Appointments"} onClick={() => setActiveTab("Appointments")} />
          <NavItem icon={<Users />} label="Patient History" active={activeTab === "Patient History"} onClick={() => setActiveTab("Patient History")} />
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        
        {/* Top Navbar */}
        <header className="h-20 bg-white/40 backdrop-blur-md border-b border-white/50 flex items-center justify-between px-8">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input 
              type="text" 
              placeholder="Search patients, IDs..." 
              className="w-full bg-white/50 border border-white/60 rounded-full py-2 pl-10 pr-4 outline-none focus:ring-2 focus:ring-blue-400 transition-all shadow-[inset_0_2px_4px_rgba(0,0,0,0.02)]"
            />
          </div>
          <div className="flex items-center gap-4">
            <button className="p-3 bg-white/50 rounded-full shadow-sm hover:bg-white transition-colors relative">
              <Bell size={20} className="text-gray-600" />
              <span className="absolute top-2 right-2 w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
            </button>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-sm font-bold text-gray-800">Dr. Sarah Jenkins</p>
                <p className="text-xs text-gray-500">Chief Medical Officer</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold border-2 border-white shadow-sm">
                SJ
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="flex-1 overflow-y-auto p-8">
          {activeTab === "Dashboard" && <DashboardView onAcceptCall={() => setInVideoCall(true)} />}
          {activeTab === "Patient History" && <PatientHistoryView />}
        </div>
      </main>
    </div>
  );
}

// -----------------------------------------------------
// DASHBOARD VIEW
// -----------------------------------------------------
function DashboardView({ onAcceptCall }: { onAcceptCall: () => void }) {
  return (
    <>
      <h2 className="text-3xl font-bold text-gray-800 mb-8">Clinic Overview</h2>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <StatCard title="Total Patients Today" value="142" icon={<Users />} trend="+12%" color="text-blue-500" />
        <StatCard title="Pending Appointments" value="28" icon={<Calendar />} trend="-5%" color="text-orange-500" />
        <StatCard title="Critical Triage Alerts" value="4" icon={<AlertTriangle />} trend="Urgent" color="text-red-500" alert />
      </div>

      {/* AI Triage Feed */}
      <div className="bg-white/60 backdrop-blur-xl border border-white/50 rounded-3xl p-6 shadow-[0_8px_32px_rgba(0,0,0,0.04)]">
        <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
          <Activity className="text-red-500" /> Live AI Triage Feed
        </h3>
        <div className="space-y-4">
          <TriageRow patient="Ramesh K." symptom="Severe Chest Pain" severity="92%" time="2 mins ago" status="Critical" onAcceptCall={onAcceptCall} />
          <TriageRow patient="Lakshmi S." symptom="High Fever (103F)" severity="75%" time="15 mins ago" status="Warning" onAcceptCall={onAcceptCall} />
          <TriageRow patient="Velu M." symptom="Skin Rash" severity="30%" time="1 hour ago" status="Normal" onAcceptCall={onAcceptCall} />
        </div>
      </div>
    </>
  );
}

// -----------------------------------------------------
// PATIENT HISTORY VIEW (API WIRED)
// -----------------------------------------------------
function PatientHistoryView() {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Form State
  const [medicines, setMedicines] = useState("");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchRecords = () => {
    setLoading(true);
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    fetch(`${API_URL}/api/v1/ehr/patient/P1`)
      .then(res => res.json())
      .then(data => {
        setRecords(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchRecords();
  }, []);

  const handleIssuePrescription = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!medicines) return;
    
    setIsSubmitting(true);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${API_URL}/api/v1/ehr/issue_prescription`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: "P1",
          doctor_id: "Dr. Sarah Jenkins",
          medicines: medicines,
          notes: notes
        })
      });
      
      if (res.ok) {
        setMedicines("");
        setNotes("");
        fetchRecords(); // Refresh the list
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="grid grid-cols-2 gap-8 h-full">
      {/* Left Column: Form */}
      <div className="bg-white/60 backdrop-blur-xl border border-white/50 rounded-3xl p-6 shadow-sm h-fit">
        <h3 className="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2">
          <Plus className="text-blue-500" /> Issue Prescription (P1)
        </h3>
        
        <form onSubmit={handleIssuePrescription} className="space-y-4">
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-1">Medicines</label>
            <input 
              required
              type="text" 
              value={medicines}
              onChange={(e) => setMedicines(e.target.value)}
              placeholder="e.g. Paracetamol 500mg (1-0-1)" 
              className="w-full bg-white/50 border border-white/60 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-blue-400 transition-all"
            />
          </div>
          <div>
            <label className="block text-sm font-bold text-gray-700 mb-1">Doctor's Notes</label>
            <textarea 
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Take after meals..." 
              rows={4}
              className="w-full bg-white/50 border border-white/60 rounded-xl py-3 px-4 outline-none focus:ring-2 focus:ring-blue-400 transition-all"
            />
          </div>
          <button 
            type="submit" 
            disabled={isSubmitting}
            className="w-full py-4 bg-blue-600 text-white rounded-xl font-bold shadow-[0_8px_16px_rgba(37,99,235,0.2)] hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isSubmitting ? 'Syncing securely...' : 'Issue Prescription'}
          </button>
        </form>
      </div>

      {/* Right Column: History */}
      <div className="bg-white/60 backdrop-blur-xl border border-white/50 rounded-3xl p-6 shadow-sm overflow-y-auto h-full max-h-[70vh]">
        <h3 className="text-xl font-bold text-gray-800 mb-6 flex items-center gap-2">
          <FileText className="text-blue-500" /> Patient EHR Timeline (P1)
        </h3>
        
        {loading ? (
          <p className="text-center text-gray-500 animate-pulse mt-10">Fetching secure records...</p>
        ) : records.length === 0 ? (
          <p className="text-center text-gray-500 mt-10">No records found.</p>
        ) : (
          <div className="space-y-4">
            {records.slice().reverse().map((record, idx) => (
              <div key={idx} className="bg-white/50 border border-white/60 p-4 rounded-2xl shadow-sm">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-bold text-gray-800">Prescription Issued</span>
                  <span className="text-xs text-gray-500 font-medium bg-gray-100 px-2 py-1 rounded-md">
                    {new Date(record.timestamp).toLocaleString()}
                  </span>
                </div>
                <p className="text-sm font-semibold text-blue-600 mb-1">{record.medicines}</p>
                {record.notes && <p className="text-sm text-gray-600 italic">"{record.notes}"</p>}
                <p className="text-xs text-gray-400 mt-3 text-right">Signed: {record.doctor_id}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// -----------------------------------------------------
// REUSABLE COMPONENTS
// -----------------------------------------------------
function NavItem({ icon, label, active = false, onClick }: { icon: React.ReactNode, label: string, active?: boolean, onClick?: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={`flex w-full items-center gap-3 px-4 py-3 rounded-2xl transition-all ${active ? 'bg-blue-600 text-white shadow-[0_8px_16px_rgba(37,99,235,0.2)]' : 'text-gray-500 hover:bg-white/50 hover:text-gray-800'}`}
    >
      {React.cloneElement(icon as React.ReactElement, { size: 20 })}
      <span className="font-semibold">{label}</span>
    </button>
  );
}

function StatCard({ title, value, icon, trend, color, alert = false }: any) {
  return (
    <div className={`bg-white/60 backdrop-blur-xl border border-white/50 rounded-3xl p-6 shadow-[0_8px_32px_rgba(0,0,0,0.04)] relative overflow-hidden`}>
      {alert && <div className="absolute inset-0 bg-red-500/5 animate-pulse pointer-events-none" />}
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-2xl bg-white shadow-sm ${color}`}>
          {React.cloneElement(icon as React.ReactElement, { size: 24 })}
        </div>
        <span className={`text-sm font-bold ${alert ? 'text-red-500' : 'text-green-500'}`}>{trend}</span>
      </div>
      <h4 className="text-gray-500 font-medium">{title}</h4>
      <p className="text-4xl font-bold text-gray-800 mt-1">{value}</p>
    </div>
  );
}

function TriageRow({ patient, symptom, severity, time, status, onAcceptCall }: any) {
  const getStatusColor = () => {
    if (status === 'Critical') return 'bg-red-100 text-red-600 border-red-200';
    if (status === 'Warning') return 'bg-orange-100 text-orange-600 border-orange-200';
    return 'bg-green-100 text-green-600 border-green-200';
  };

  return (
    <div className="flex items-center justify-between p-4 bg-white/50 rounded-2xl border border-white/60 hover:shadow-md transition-shadow">
      <div>
        <p className="font-bold text-gray-800">{patient}</p>
        <p className="text-sm text-gray-500">{symptom} • {time}</p>
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right hidden md:block">
          <p className="text-xs text-gray-400">Severity</p>
          <p className="font-bold text-gray-800">{severity}</p>
        </div>
        <div className={`px-4 py-1.5 rounded-full border text-sm font-bold ${getStatusColor()}`}>
          {status}
        </div>
        <button onClick={onAcceptCall} className="p-2 bg-blue-600 text-white rounded-xl shadow-md hover:bg-blue-700 transition-colors">
          <PhoneCall size={18} />
        </button>
      </div>
    </div>
  );
}
