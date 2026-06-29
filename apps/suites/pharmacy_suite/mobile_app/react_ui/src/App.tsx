import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Search, Bell, Package, Plus, Camera, RefreshCw, Archive, ScanLine } from 'lucide-react';
import './index.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('inventory');
  
  return (
    <div className="w-full h-screen bg-[#E8F0F2] overflow-hidden flex flex-col font-sans relative text-gray-800">
      
      {/* Top Header */}
      <header className="pt-12 pb-4 px-6 bg-[#E8F0F2] shadow-[0_4px_24px_rgba(0,0,0,0.02)] flex justify-between items-center z-10 relative">
        <div>
          <h1 className="text-2xl font-black text-emerald-700 tracking-tight flex items-center gap-2">
            GramCare <span className="text-gray-800">Pharma</span>
          </h1>
          <p className="text-gray-500 font-medium text-sm">Local Chemist App</p>
        </div>
        <div className="flex gap-3">
          <div className="w-12 h-12 rounded-full neo-bg flex items-center justify-center shadow-neo-out border border-white/60">
            <Bell size={20} className="text-gray-600" />
            <span className="absolute top-12 right-7 w-3 h-3 bg-red-500 rounded-full border-2 border-[#E8F0F2]"></span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto pb-24 relative z-0 p-6">
        <AnimatePresence mode="wait">
          {activeTab === 'inventory' && (
            <motion.div key="inventory" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <InventoryScreen />
            </motion.div>
          )}
          {activeTab === 'scanner' && (
            <motion.div key="scanner" initial={{opacity: 0, x: -20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0, x: 20}} className="h-full">
              <ScannerScreen onScanComplete={() => setActiveTab('inventory')} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bottom Navigation */}
      <nav className="absolute bottom-0 w-full h-24 bg-[#E8F0F2] px-6 flex justify-around items-center z-20 pb-4 shadow-[0_-8px_32px_rgba(0,0,0,0.04)]">
        <NavBtn icon={<Package />} label="Stock" active={activeTab === 'inventory'} onClick={() => setActiveTab('inventory')} />
        <div className="-mt-8 relative z-30">
          <button 
            onClick={() => setActiveTab('scanner')} 
            className="w-16 h-16 rounded-full bg-emerald-500 text-white flex items-center justify-center shadow-[0_8px_24px_rgba(16,185,129,0.4)] active:scale-95 transition-transform"
          >
            <ScanLine size={32} />
          </button>
        </div>
        <NavBtn icon={<Archive />} label="Orders" active={activeTab === 'orders'} onClick={() => setActiveTab('orders')} />
      </nav>
    </div>
  );
}

function InventoryScreen() {
  const [stock, setStock] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/pharmacy/stock')
      .then(res => res.json())
      .then(data => {
        setStock(data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch stock", err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="h-full flex flex-col">
      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
        <input 
          type="text" 
          placeholder="Search inventory..." 
          className="w-full neo-bg rounded-2xl py-4 pl-12 pr-4 shadow-neo-in outline-none text-gray-700 font-medium placeholder-gray-400"
        />
      </div>

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-gray-800">Current Stock</h2>
        <button className="text-emerald-600 p-2"><RefreshCw size={20} /></button>
      </div>

      <div className="space-y-4 pb-10">
        {loading ? (
          <p className="text-center text-gray-500 animate-pulse mt-10">Syncing with GramCare Cloud...</p>
        ) : stock.length === 0 ? (
          <p className="text-center text-gray-500 mt-10">No stock found.</p>
        ) : (
          stock.map((item) => (
            <div key={item.id} className="neo-bg p-5 rounded-3xl shadow-neo-out border border-white/40 flex justify-between items-center">
              <div>
                <h3 className="font-bold text-lg text-gray-800">{item.medicine_name}</h3>
                <p className="text-sm text-gray-500 flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${item.quantity < 50 ? 'bg-orange-500' : 'bg-emerald-500'}`}></span>
                  Batch: {item.batch_number}
                </p>
              </div>
              <div className="text-right">
                <p className="text-2xl font-black text-emerald-700">{item.quantity}</p>
                <p className="text-xs text-gray-400 font-bold uppercase">Units</p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function ScannerScreen({ onScanComplete }: { onScanComplete: () => void }) {
  const [scanning, setScanning] = useState(false);

  const handleSimulateScan = () => {
    setScanning(true);
    setTimeout(() => {
      // Automatically post new stock
      fetch('http://localhost:8000/api/v1/pharmacy/stock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pharmacy_id: "PHARM-1",
          medicine_name: "Azithromycin 500mg",
          batch_number: "BATCH-882",
          quantity: 100,
          expiry_date: "2027-10-01"
        })
      }).then(() => {
        setScanning(false);
        onScanComplete();
      });
    }, 2000);
  };

  return (
    <div className="h-full flex flex-col items-center justify-center -mt-10">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">Scan Barcode</h2>
      <p className="text-gray-500 text-center mb-8">Scan incoming medicine stock to instantly update GramCare cloud inventory.</p>

      <div className="relative w-64 h-64 neo-bg rounded-[40px] shadow-neo-in flex items-center justify-center overflow-hidden mb-8">
        {scanning ? (
          <>
            <div className="absolute top-0 w-full h-1 bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,1)] animate-[scan_1.5s_ease-in-out_infinite]" />
            <ScanLine size={64} className="text-emerald-400 opacity-50" />
          </>
        ) : (
          <ScanLine size={64} className="text-gray-300" />
        )}
        
        {/* Mock camera corners */}
        <div className="absolute top-4 left-4 w-8 h-8 border-t-4 border-l-4 border-emerald-500 rounded-tl-xl"></div>
        <div className="absolute top-4 right-4 w-8 h-8 border-t-4 border-r-4 border-emerald-500 rounded-tr-xl"></div>
        <div className="absolute bottom-4 left-4 w-8 h-8 border-b-4 border-l-4 border-emerald-500 rounded-bl-xl"></div>
        <div className="absolute bottom-4 right-4 w-8 h-8 border-b-4 border-r-4 border-emerald-500 rounded-br-xl"></div>
      </div>

      <button 
        onClick={handleSimulateScan}
        disabled={scanning}
        className="px-10 py-4 bg-emerald-600 text-white rounded-full font-bold shadow-[0_8px_24px_rgba(16,185,129,0.3)] active:scale-95 transition-transform disabled:opacity-50"
      >
        {scanning ? 'Updating Cloud...' : 'Simulate Scan'}
      </button>
    </div>
  );
}

function NavBtn({ icon, label, active, onClick }: any) {
  return (
    <button onClick={onClick} className="flex flex-col items-center justify-center gap-1 w-16">
      <div className={`p-3 rounded-2xl transition-all duration-300 ${active ? 'neo-bg shadow-neo-in text-emerald-600' : 'text-gray-400'}`}>
        {icon}
      </div>
      <span className={`text-[10px] font-bold ${active ? 'text-emerald-600' : 'text-gray-400'}`}>{label}</span>
    </button>
  );
}
