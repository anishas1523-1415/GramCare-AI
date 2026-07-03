import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, AlertCircle, XCircle, ShoppingCart, LogOut, Store, Plus, Minus, Camera, CalendarClock } from 'lucide-react'
import api from './lib/api'
import LoginScreen from './components/LoginScreen'
import type { InventoryItem, PrescriptionQueueItem, Pharmacy, ExpiringItem, OCRResult } from './types'
import './index.css'

function StatusBadge({ status }: { status: InventoryItem['status'] }) {
  if (status === 'Out of Stock') {
    return (
      <span style={{ color: '#ef4444', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
        <XCircle size={16} /> Out of Stock
      </span>
    );
  }
  if (status === 'Low') {
    return (
      <span style={{ color: '#f59e0b', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
        <AlertCircle size={16} /> Low Stock
      </span>
    );
  }
  return (
    <span style={{ color: '#10b981', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
      <CheckCircle size={16} /> Optimal
    </span>
  );
}

/** One-time pharmacy registration (name + location) — required before the
 * shop appears in patients' nearby-medicine search. */
function RegisterPharmacy({ onRegistered }: { onRegistered: (p: Pharmacy) => void }) {
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      // Browser geolocation puts the shop on the patients' map; declining
      // still registers the shop (it just won't be distance-ranked).
      let lat: number | null = null, lng: number | null = null;
      try {
        const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
          navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 8000 }));
        lat = pos.coords.latitude;
        lng = pos.coords.longitude;
      } catch { /* location denied — proceed without */ }

      const res = await api.post<Pharmacy>('/pharmacy/register', { name, address, phone, lat, lng });
      onRegistered(res.data);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Registration failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="neo-glass-container p-8" style={{ maxWidth: 560, margin: '4rem auto' }}>
      <h1 style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Store /> Register your pharmacy
      </h1>
      <p style={{ color: '#718096' }}>
        Patients nearby will see your shop and live medicine availability once registered.
      </p>
      {error && <div role="alert" style={{ background: '#fee2e2', color: '#991b1b', padding: '0.75rem', borderRadius: 8, margin: '1rem 0' }}>{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        <input required minLength={2} placeholder="Pharmacy name (e.g. Grama Medicals)" value={name} onChange={(e) => setName(e.target.value)} className="neu-input" style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <input placeholder="Address / village" value={address} onChange={(e) => setAddress(e.target.value)} style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <input placeholder="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <button disabled={busy} className="neu-button" style={{ background: '#10b981', color: 'white', padding: '0.9rem', borderRadius: 10, fontWeight: 'bold' }}>
          {busy ? 'Registering…' : 'Register (uses your current location)'}
        </button>
      </form>
    </div>
  );
}

/** Invoice/stock photo entry: OCR the invoice, confirm, add items.
 * Backs the planning doc's "இன்வாய்ஸை ஸ்கேன் பண்ணுவாங்க" stock-entry mode. */
function InvoiceScan({ onAdded }: { onAdded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [parsed, setParsed] = useState<string[]>([]);
  const [error, setError] = useState('');

  const pickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError('');
    setParsed([]);
    try {
      const b64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve((reader.result as string).split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const res = await api.post<OCRResult>('/triage/ocr', { image_base64: b64 });
      setParsed(res.data.medicines_parsed);
      if (res.data.medicines_parsed.length === 0) setError('No medicines recognized on this invoice.');
    } catch {
      setError('Could not read the invoice image.');
    } finally {
      setBusy(false);
    }
  };

  const confirmAdd = async () => {
    setBusy(true);
    try {
      for (const line of parsed) {
        // "Paracetamol 500mg (1-0-1)" -> name part before any parenthesis
        const name = line.split('(')[0].trim();
        if (name) {
          await api.post('/pharmacy/items', { medicine_name: name, stock_count: 10 });
        }
      }
      setParsed([]);
      onAdded();
    } catch {
      setError('Failed to add some items — check the inventory list.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="neu-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Camera size={18} /> Add stock from invoice photo
      </h3>
      <input type="file" accept="image/*" onChange={pickFile} disabled={busy} />
      {error && <p style={{ color: '#991b1b', fontSize: '0.85rem' }}>{error}</p>}
      {parsed.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <p style={{ fontSize: '0.9rem' }}>AI found: {parsed.join('; ')}</p>
          <button onClick={confirmAdd} disabled={busy} style={{ background: '#10b981', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: 8, fontWeight: 'bold', cursor: 'pointer' }}>
            Confirm — add each with 10 units (adjust after)
          </button>
        </div>
      )}
    </div>
  );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [pharmacy, setPharmacy] = useState<Pharmacy | null>(null);
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [expiring, setExpiring] = useState<ExpiringItem[]>([]);
  const [prescriptions, setPrescriptions] = useState<PrescriptionQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [newMedName, setNewMedName] = useState('');
  const [newMedCount, setNewMedCount] = useState('');

  const fetchData = useCallback(async () => {
    setError('');
    try {
      const me = await api.get<Pharmacy>('/pharmacy/me');
      setPharmacy(me.data);
      setNeedsRegistration(false);
      const [invRes, rxRes, expRes] = await Promise.all([
        api.get<InventoryItem[]>('/pharmacy/stock'),
        api.get<PrescriptionQueueItem[]>('/pharmacy/queue'),
        api.get<ExpiringItem[]>('/pharmacy/expiring', { params: { days: 90 } }),
      ]);
      setInventory(invRes.data);
      setPrescriptions(rxRes.data);
      setExpiring(expRes.data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setNeedsRegistration(true); // no pharmacy registered yet
      } else {
        console.error('Failed to fetch pharmacy data:', err);
        setError('Could not load pharmacy data. Check your connection and try again.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const act = async (fn: () => Promise<unknown>) => {
    setActionError('');
    try {
      await fn();
      await fetchData();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActionError(typeof message === 'string' ? message : 'Action failed');
    }
  };

  const sellOne = (id: number) => act(() => api.post(`/pharmacy/decrement/${id}`));
  const addTen = (id: number) => act(() => api.post(`/pharmacy/update_stock/${id}?quantity_added=10`));
  const setCount = (id: number) => {
    const value = window.prompt('Enter the counted stock (end-of-day count):');
    if (value === null) return;
    const n = parseInt(value, 10);
    if (Number.isNaN(n) || n < 0) { setActionError('Enter a valid non-negative number.'); return; }
    act(() => api.post(`/pharmacy/set_stock/${id}?count=${n}`));
  };
  const addMedicine = (e: React.FormEvent) => {
    e.preventDefault();
    const count = parseInt(newMedCount || '0', 10);
    if (!newMedName.trim()) return;
    act(async () => {
      await api.post('/pharmacy/items', {
        medicine_name: newMedName.trim(),
        stock_count: Number.isNaN(count) ? 0 : count,
      });
      setNewMedName('');
      setNewMedCount('');
    });
  };
  const fulfillPrescription = (id: number) => act(() => api.put(`/pharmacy/fulfill/${id}`));

  if (loading) return <div className="neo-glass-container text-center pt-20">Loading Pharmacy Network...</div>;
  if (needsRegistration) {
    return <RegisterPharmacy onRegistered={() => { setLoading(true); fetchData(); }} />;
  }

  const lowStockCount = inventory.filter((i) => i.status === 'Low' || i.status === 'Out of Stock').length;

  return (
    <div className="neo-glass-container p-8">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2.2rem', color: '#10b981' }}>
            {pharmacy?.name || 'GramCare Pharmacy Portal'}
          </h1>
          <p style={{ margin: '0.5rem 0 0 0', color: '#718096' }}>
            {pharmacy?.address ? `${pharmacy.address} · ` : ''}Live Inventory & Prescription Fulfillment
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="neu-button" onClick={fetchData}>Refresh</button>
          <button className="neu-button" onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <LogOut size={16} /> Sign Out
          </button>
        </div>
      </div>

      {error && <div role="alert" style={{ background: '#fee2e2', color: '#991b1b', padding: '1rem', borderRadius: 8, marginBottom: '1.5rem' }}>{error}</div>}
      {actionError && <div role="alert" style={{ background: '#fef3c7', color: '#92400e', padding: '0.75rem', borderRadius: 8, marginBottom: '1rem' }}>{actionError}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>

        {/* LEFT column: Prescriptions + expiry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                      <strong>Rx #{rx.id} (Patient {rx.patient_id})</strong>
                      <span style={{ fontSize: '0.8rem', color: '#718096' }}>{new Date(rx.created_at).toLocaleString()}</span>
                    </div>
                    {rx.diagnosis && (
                      <p style={{ margin: '0 0 0.5rem 0', fontSize: '0.85rem', color: '#718096' }}>
                        <strong>Diagnosis:</strong> {rx.diagnosis}
                      </p>
                    )}
                    <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem' }}>
                      <strong>Medicines:</strong><br />
                      {rx.medicines.length === 0
                        ? 'No medicines listed'
                        : rx.medicines.map((m, idx) => (
                          <span key={idx}>
                            {m.name} — {m.dosage}, {m.frequency}, {m.duration}
                            {idx < rx.medicines.length - 1 ? '; ' : ''}
                          </span>
                        ))}
                    </p>
                    <button
                      onClick={() => fulfillPrescription(rx.id)}
                      style={{ background: '#10b981', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 'bold' }}
                    >
                      Fulfill (auto-deducts stock)
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Expiry alerts — orange-coded per the planning discussion */}
          <div className="glass-panel">
            <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: 10, color: '#f59e0b' }}>
              <CalendarClock /> Expiry Alerts (next 90 days)
            </h2>
            {expiring.length === 0 ? (
              <p style={{ color: '#718096' }}>Nothing expiring soon. 🎉</p>
            ) : (
              expiring.map((item) => (
                <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: 8, marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 'bold' }}>{item.medicine_name}</span>
                  <span style={{ color: '#92400e' }}>
                    {item.stock_count} units · expires in {item.days_left} day{item.days_left === 1 ? '' : 's'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RIGHT column: Inventory management */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-panel">
            <h2 style={{ marginTop: 0 }}>Inventory</h2>

            {/* Rural-friendly quick entry: name + count */}
            <form onSubmit={addMedicine} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input
                placeholder="Add medicine (e.g. Dolo 650)"
                value={newMedName}
                onChange={(e) => setNewMedName(e.target.value)}
                style={{ flex: 2, padding: '0.6rem', borderRadius: 8, border: '1px solid #cbd5e1' }}
              />
              <input
                placeholder="Count"
                type="number"
                min={0}
                value={newMedCount}
                onChange={(e) => setNewMedCount(e.target.value)}
                style={{ flex: 1, padding: '0.6rem', borderRadius: 8, border: '1px solid #cbd5e1' }}
              />
              <button type="submit" style={{ background: '#10b981', color: 'white', border: 'none', borderRadius: 8, padding: '0 1rem', cursor: 'pointer' }}>
                <Plus size={18} />
              </button>
            </form>

            <table className="inventory-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Medicine</th>
                  <th>Stock</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {inventory.map((item) => (
                  <tr key={item.id} className="inventory-row">
                    <td style={{ fontWeight: 'bold' }}>
                      {item.medicine_name}
                      {item.expiry_date && (
                        <div style={{ fontSize: '0.7rem', color: '#718096' }}>exp {item.expiry_date}</div>
                      )}
                    </td>
                    <td style={{ textAlign: 'center' }}>{item.stock_count}</td>
                    <td><StatusBadge status={item.status} /></td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.3rem', justifyContent: 'center' }}>
                        <button title="Sold 1 (tap-to-decrement)" onClick={() => sellOne(item.id)}
                          style={{ border: '1px solid #ef4444', color: '#ef4444', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem' }}>
                          <Minus size={14} />
                        </button>
                        <button title="Shipment +10" onClick={() => addTen(item.id)}
                          style={{ border: '1px solid #10b981', color: '#10b981', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem' }}>
                          <Plus size={14} />
                        </button>
                        <button title="Set counted stock" onClick={() => setCount(item.id)}
                          style={{ border: '1px solid #6366f1', color: '#6366f1', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem', fontSize: '0.7rem', fontWeight: 'bold' }}>
                          SET
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <InvoiceScan onAdded={fetchData} />
          </div>

          <div className="neu-panel" style={{ textAlign: 'center' }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#718096' }}>Low Stock Alerts</h3>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: lowStockCount > 0 ? '#ef4444' : '#10b981' }}>
              {lowStockCount}
            </div>
            <p style={{ color: '#718096', fontSize: '0.9rem', margin: '0.5rem 0 0 0' }}>
              medicine{lowStockCount === 1 ? '' : 's'} low or out of stock
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [authenticated, setAuthenticated] = useState(
    () => !!localStorage.getItem('pharmacy_access_token')
  );

  const handleLogout = () => {
    localStorage.removeItem('pharmacy_access_token');
    localStorage.removeItem('pharmacy_user_role');
    setAuthenticated(false);
  };

  if (!authenticated) {
    return <LoginScreen onLoginSuccess={() => setAuthenticated(true)} />;
  }

  return <Dashboard onLogout={handleLogout} />;
}

export default App
