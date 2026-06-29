import React from 'react';
import { Pill, Package, FileText, AlertCircle, Search, Settings, Truck } from 'lucide-react';

export default function PharmacyDashboard() {
  return (
    <div className="flex h-screen bg-[#f2fcf5] text-gray-800 font-sans">
      
      {/* Sidebar - Pharmacy Green Glassmorphism */}
      <aside className="w-64 bg-green-50/60 backdrop-blur-xl border-r border-green-200/50 p-6 flex flex-col gap-8 shadow-[4px_0_24px_rgba(34,197,94,0.03)]">
        <div className="flex items-center gap-3 text-green-600">
          <Pill size={32} strokeWidth={2.5} />
          <h1 className="text-2xl font-bold tracking-tight">GramPharma</h1>
        </div>
        
        <nav className="flex flex-col gap-2">
          <NavItem icon={<Package />} label="Inventory" active />
          <NavItem icon={<FileText />} label="Prescription Orders" />
          <NavItem icon={<Truck />} label="Deliveries" />
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        
        {/* Top Navbar */}
        <header className="h-20 bg-white/60 backdrop-blur-md border-b border-green-100/50 flex items-center justify-between px-8">
          <div className="relative w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-green-400" size={20} />
            <input 
              type="text" 
              placeholder="Search medicines, batches..." 
              className="w-full bg-white/70 border border-green-200/60 rounded-full py-2 pl-10 pr-4 outline-none focus:ring-2 focus:ring-green-400 transition-all shadow-[inset_0_2px_4px_rgba(0,0,0,0.02)]"
            />
          </div>
          <div className="flex items-center gap-4">
            <button className="p-3 bg-white/60 rounded-full shadow-sm hover:bg-white transition-colors relative text-green-600">
              <Settings size={20} />
            </button>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-sm font-bold text-gray-800">Admin</p>
                <p className="text-xs text-green-600">Main Branch</p>
              </div>
              <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600 font-bold border-2 border-white shadow-sm">
                A
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="flex-1 overflow-y-auto p-8">
          <h2 className="text-3xl font-bold text-gray-800 mb-8">Pharmacy Overview</h2>
          
          {/* Stats Grid */}
          <div className="grid grid-cols-3 gap-6 mb-8">
            <StatCard title="Total Medicines in Stock" value="12,450" icon={<Package />} trend="Optimal" color="text-green-500" />
            <StatCard title="Pending Digital Prescriptions" value="45" icon={<FileText />} trend="+12 today" color="text-blue-500" />
            <StatCard title="Low Stock Alerts" value="8" icon={<AlertCircle />} trend="Requires Action" color="text-orange-500" alert />
          </div>

          <div className="grid grid-cols-2 gap-8">
            {/* Incoming Orders Feed */}
            <div className="bg-white/70 backdrop-blur-xl border border-green-100/50 rounded-3xl p-6 shadow-[0_8px_32px_rgba(34,197,94,0.04)]">
              <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                <FileText className="text-blue-500" /> Incoming Doctor Orders
              </h3>
              <div className="space-y-4">
                <OrderRow patient="Ramesh K." doctor="Dr. Sarah J." items="3 Medicines" time="Just now" status="Pending" />
                <OrderRow patient="Lakshmi S." doctor="Dr. Ram" items="1 Medicine" time="10 mins ago" status="Packing" />
                <OrderRow patient="Velu M." doctor="Dr. Sarah J." items="2 Medicines" time="1 hour ago" status="Ready" />
              </div>
            </div>

            {/* Low Stock Inventory Alerts */}
            <div className="bg-white/70 backdrop-blur-xl border border-orange-100/50 rounded-3xl p-6 shadow-[0_8px_32px_rgba(249,115,22,0.04)]">
              <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
                <AlertCircle className="text-orange-500" /> Inventory Shortage Alerts
              </h3>
              <div className="space-y-4">
                <InventoryRow medicine="Paracetamol 500mg" stock="45 Tablets" minimum="100" status="Low" />
                <InventoryRow medicine="Amoxicillin 250mg" stock="12 Strips" minimum="50" status="Low" />
                <InventoryRow medicine="Insulin Glargine" stock="0 Vials" minimum="20" status="Out of Stock" />
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
}

function NavItem({ icon, label, active = false }: { icon: React.ReactNode, label: string, active?: boolean }) {
  return (
    <button className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all ${active ? 'bg-green-600 text-white shadow-[0_8px_16px_rgba(34,197,94,0.2)]' : 'text-gray-500 hover:bg-green-50/50 hover:text-green-800'}`}>
      {React.cloneElement(icon as React.ReactElement, { size: 20 })}
      <span className="font-semibold">{label}</span>
    </button>
  );
}

function StatCard({ title, value, icon, trend, color, alert = false }: any) {
  return (
    <div className={`bg-white/70 backdrop-blur-xl border border-white/50 rounded-3xl p-6 shadow-[0_8px_32px_rgba(0,0,0,0.02)] relative overflow-hidden`}>
      {alert && <div className="absolute inset-0 bg-orange-500/5 animate-pulse pointer-events-none" />}
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-2xl bg-white shadow-sm ${color}`}>
          {React.cloneElement(icon as React.ReactElement, { size: 24 })}
        </div>
        <span className={`text-sm font-bold ${alert ? 'text-orange-500' : 'text-green-500'}`}>{trend}</span>
      </div>
      <h4 className="text-gray-500 font-medium">{title}</h4>
      <p className="text-4xl font-bold text-gray-800 mt-1">{value}</p>
    </div>
  );
}

function OrderRow({ patient, doctor, items, time, status }: any) {
  const getStatusColor = () => {
    if (status === 'Pending') return 'bg-orange-100 text-orange-600 border-orange-200';
    if (status === 'Packing') return 'bg-blue-100 text-blue-600 border-blue-200';
    return 'bg-green-100 text-green-600 border-green-200';
  };

  return (
    <div className="flex items-center justify-between p-4 bg-white/50 rounded-2xl border border-white/60 hover:shadow-sm transition-shadow">
      <div>
        <p className="font-bold text-gray-800">{patient}</p>
        <p className="text-sm text-gray-500">From: {doctor} • {items}</p>
      </div>
      <div className="flex items-center gap-4">
        <p className="text-xs text-gray-400">{time}</p>
        <div className={`px-4 py-1.5 rounded-full border text-xs font-bold ${getStatusColor()}`}>
          {status}
        </div>
      </div>
    </div>
  );
}

function InventoryRow({ medicine, stock, minimum, status }: any) {
  const isCritical = status === 'Out of Stock';
  return (
    <div className="flex items-center justify-between p-4 bg-white/50 rounded-2xl border border-white/60 hover:shadow-sm transition-shadow">
      <div>
        <p className="font-bold text-gray-800">{medicine}</p>
        <p className="text-sm text-gray-500">Min. Required: {minimum}</p>
      </div>
      <div className="flex flex-col items-end">
        <p className={`font-bold text-lg ${isCritical ? 'text-red-600' : 'text-orange-500'}`}>{stock}</p>
        <p className={`text-xs font-bold ${isCritical ? 'text-red-500' : 'text-orange-400'}`}>{status}</p>
      </div>
    </div>
  );
}
