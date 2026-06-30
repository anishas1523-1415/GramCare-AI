import { useState, useEffect } from 'react'
import { CheckCircle, AlertCircle, ShoppingCart } from 'lucide-react'
import api from './lib/api'
import './index.css'

function App() {
  const [inventory, setInventory] = useState<any[]>([])
  const [prescriptions, setPrescriptions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = async () => {
    try {
      const [invRes, rxRes] = await Promise.all([
        api.get('/pharmacy/inventory'),
        api.get('/pharmacy/queue')
      ]);
      setInventory(invRes.data);
      setPrescriptions(rxRes.data);
    } catch (error) {
      console.error("Failed to fetch pharmacy data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // In a full implementation, we'd add WebSocket listeners here for real-time Rx drops
  }, []);

  const fulfillPrescription = async (id: number) => {
    try {
      await api.put(`/pharmacy/fulfill/${id}`);
      fetchData(); // Refresh data
    } catch (error) {
      alert("Failed to fulfill prescription");
    }
  };

  if (loading) return <div className="neo-glass-container text-center pt-20">Loading Pharmacy Network...</div>;

  return (
    <div className="neo-glass-container p-8">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2.5rem', color: '#10b981' }}>GramCare Pharmacy Portal</h1>
          <p style={{ margin: '0.5rem 0 0 0', color: '#718096' }}>Live Inventory & Prescription Fulfillment Network</p>
        </div>
        <button className="neu-button" onClick={fetchData}>Refresh Data</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        
        {/* Prescriptions Queue */}
        <div className="glass-panel">
          <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShoppingCart className="text-teal-500" /> Pending Prescriptions
          </h2>
          {prescriptions.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#718096' }}>No pending prescriptions.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {prescriptions.map((rx) => (
                <div key={rx.id} className="neu-panel" style={{ padding: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <strong>Rx #{rx.id} (Patient {rx.patient_id})</strong>
                    <span style={{ fontSize: '0.8rem', color: '#718096' }}>{new Date(rx.created_at).toLocaleString()}</span>
                  </div>
                  <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem' }}>
                    <strong>Medicines:</strong><br/>
                    {typeof rx.content === 'string' ? rx.content : JSON.stringify(rx.content)}
                  </p>
                  <button 
                    onClick={() => fulfillPrescription(rx.id)}
                    style={{ background: '#10b981', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
                  >
                    Mark as Fulfilled
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Live Inventory */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          <div className="glass-panel">
            <h2 style={{ marginTop: 0 }}>Current Inventory</h2>
            <table className="inventory-table">
              <thead>
                <tr>
                  <th>Medicine Name</th>
                  <th>Stock Level</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.id} className="inventory-row">
                    <td style={{ fontWeight: 'bold' }}>{item.medicine_name}</td>
                    <td>{item.stock_quantity} Units</td>
                    <td>
                      {item.stock_quantity > 50 ? (
                        <span style={{ color: '#10b981', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <CheckCircle size={16} /> Healthy
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <AlertCircle size={16} /> Low Stock
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="neu-panel" style={{ textAlign: 'center' }}>
             <h3 style={{ margin: '0 0 1rem 0', color: '#718096' }}>Total Fulfilled</h3>
             <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#10b981' }}>1,284</div>
             <p style={{ color: '#10b981', fontSize: '0.9rem', margin: '0.5rem 0 0 0' }}>+12% from last week</p>
          </div>
        </div>

      </div>
    </div>
  )
}

export default App
