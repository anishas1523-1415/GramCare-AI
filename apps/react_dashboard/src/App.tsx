import { useState } from 'react'
import './index.css'

function App() {
  const [inventory] = useState([
    { id: 1, name: 'Paracetamol 500mg', stock: 124, status: 'In Stock' },
    { id: 2, name: 'Amoxicillin 250mg', stock: 12, status: 'Low Stock' },
    { id: 3, name: 'Ibuprofen 400mg', stock: 0, status: 'Out of Stock' },
    { id: 4, name: 'Cough Syrup 100ml', stock: 45, status: 'In Stock' },
  ])

  return (
    <div className="neo-glass-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2.5rem', color: '#10b981' }}>Pharmacy Portal</h1>
          <p style={{ margin: '0.5rem 0 0 0', color: '#718096' }}>Live Inventory Network</p>
        </div>
        <button className="neu-button">Update Stock</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '2rem' }}>
        <div className="glass-panel">
          <h2 style={{ marginTop: 0 }}>Current Inventory</h2>
          <table className="inventory-table">
            <thead>
              <tr>
                <th>Medicine Name</th>
                <th>Stock Level</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {inventory.map((item) => (
                <tr key={item.id} className="inventory-row">
                  <td style={{ fontWeight: 'bold' }}>{item.name}</td>
                  <td>{item.stock} Units</td>
                  <td>
                    <span style={{ 
                      color: item.stock > 20 ? '#10b981' : item.stock > 0 ? '#f59e0b' : '#ef4444',
                      fontWeight: 'bold'
                    }}>
                      {item.status}
                    </span>
                  </td>
                  <td>
                    <button className="neu-button" style={{ padding: '0.5rem 1rem', fontSize: '0.8rem' }}>Order</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="neu-panel" style={{ textAlign: 'center' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#718096' }}>Total Prescriptions</h3>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: '#10b981' }}>1,284</div>
            <p style={{ color: '#10b981', fontSize: '0.9rem', margin: '0.5rem 0 0 0' }}>+12% from last week</p>
          </div>
          
          <div className="glass-panel" style={{ background: 'rgba(239, 68, 68, 0.1)', borderColor: 'rgba(239, 68, 68, 0.2)' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#ef4444' }}>Critical Shortages</h3>
            <ul style={{ paddingLeft: '1.2rem', color: '#ef4444', margin: 0 }}>
              <li>Ibuprofen 400mg</li>
              <li>Insulin Glargine</li>
              <li>Azithromycin 500mg</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
