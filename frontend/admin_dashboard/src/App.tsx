import { useState, useEffect, useCallback } from 'react'
import { CheckCircle, AlertCircle, XCircle, ShoppingCart, LogOut, Store, Plus, Minus, Camera, CalendarClock, TriangleAlert, PackageSearch, Info, X } from 'lucide-react'
import api from './lib/api'
import LoginScreen from './components/LoginScreen'
import AdminAnalytics from './components/AdminAnalytics'
import { useLocale } from './contexts/LocaleContext'
import type { InventoryItem, PrescriptionQueueItem, Pharmacy, ExpiringItem, OCRResult, BatchRecall, MedicinePreorder, InteractionWarning, MedicineInfo } from './types'
import './index.css'

function StatusBadge({ status }: { status: InventoryItem['status'] }) {
  const { t } = useLocale();
  if (status === 'Out of Stock') {
    return (
      <span style={{ color: '#ef4444', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
        <XCircle size={16} /> {t('out_of_stock')}
      </span>
    );
  }
  if (status === 'Low') {
    return (
      <span style={{ color: '#f59e0b', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
        <AlertCircle size={16} /> {t('low_stock')}
      </span>
    );
  }
  return (
    <span style={{ color: '#10b981', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
      <CheckCircle size={16} /> {t('stock_optimal')}
    </span>
  );
}

/** One-time pharmacy registration (name + location) — required before the
 * shop appears in patients' nearby-medicine search. */
function RegisterPharmacy({ onRegistered }: { onRegistered: (p: Pharmacy) => void }) {
  const { t } = useLocale();
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [isJanAushadhi, setIsJanAushadhi] = useState(false);
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

      const res = await api.post<Pharmacy>('/pharmacy/register', {
        name, address, phone, lat, lng, is_jan_aushadhi: isJanAushadhi,
      });
      onRegistered(res.data);
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : t('registration_failed_generic'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="neo-glass-container p-8" style={{ maxWidth: 560, margin: '4rem auto' }}>
      <h1 style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Store /> {t('register_your_pharmacy')}
      </h1>
      <p style={{ color: '#718096' }}>
        {t('register_pharmacy_blurb')}
      </p>
      {error && <div role="alert" style={{ background: '#fee2e2', color: '#991b1b', padding: '0.75rem', borderRadius: 8, margin: '1rem 0' }}>{error}</div>}
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        <input required minLength={2} placeholder={t('register_pharmacy_name')} value={name} onChange={(e) => setName(e.target.value)} className="neu-input" style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <input placeholder={t('register_address')} value={address} onChange={(e) => setAddress(e.target.value)} style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <input placeholder={t('register_phone')} value={phone} onChange={(e) => setPhone(e.target.value)} style={{ padding: '0.9rem', borderRadius: 10, border: '1px solid #cbd5e1' }} />
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '0.6rem 0.2rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={isJanAushadhi} onChange={(e) => setIsJanAushadhi(e.target.checked)} />
          <span>{t('jan_aushadhi_note')}</span>
        </label>
        <button disabled={busy} className="neu-button" style={{ background: '#10b981', color: 'white', padding: '0.9rem', borderRadius: 10, fontWeight: 'bold' }}>
          {busy ? t('registering') : t('register_with_location')}
        </button>
      </form>
    </div>
  );
}

/** Invoice/stock photo entry: OCR the invoice, confirm, add items.
 * Backs the planning doc's "இன்வாய்ஸை ஸ்கேன் பண்ணுவாங்க" stock-entry mode. */
function InvoiceScan({ onAdded }: { onAdded: () => void }) {
  const { t } = useLocale();
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
      if (res.data.medicines_parsed.length === 0) setError(t('no_medicines_recognized'));
    } catch {
      setError(t('invoice_read_failed'));
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
      setError(t('some_items_failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="neu-panel" style={{ padding: '1rem', marginTop: '1rem' }}>
      <h3 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Camera size={18} /> {t('add_stock_from_invoice')}
      </h3>
      <input type="file" accept="image/*" onChange={pickFile} disabled={busy} />
      {error && <p style={{ color: '#991b1b', fontSize: '0.85rem' }}>{error}</p>}
      {parsed.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <p style={{ fontSize: '0.9rem' }}>{t('ai_found')} {parsed.join('; ')}</p>
          <button onClick={confirmAdd} disabled={busy} style={{ background: '#10b981', color: 'white', padding: '0.5rem 1rem', border: 'none', borderRadius: 8, fontWeight: 'bold', cursor: 'pointer' }}>
            {t('confirm_add_ten_each')}
          </button>
        </div>
      )}
    </div>
  );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const { t, code, setCode } = useLocale();
  const [pharmacy, setPharmacy] = useState<Pharmacy | null>(null);
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [expiring, setExpiring] = useState<ExpiringItem[]>([]);
  const [prescriptions, setPrescriptions] = useState<PrescriptionQueueItem[]>([]);
  const [recalls, setRecalls] = useState<BatchRecall[]>([]);
  const [preorders, setPreorders] = useState<MedicinePreorder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [lastInteractionWarnings, setLastInteractionWarnings] = useState<InteractionWarning[]>([]);
  const [newMedName, setNewMedName] = useState('');
  const [newMedCount, setNewMedCount] = useState('');
  const [medicineInfoName, setMedicineInfoName] = useState<string | null>(null);
  const [medicineInfo, setMedicineInfo] = useState<MedicineInfo | null>(null);
  const [medicineInfoLoading, setMedicineInfoLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'pharmacy' | 'analytics'>('pharmacy');
  
  const userRole = localStorage.getItem('pharmacy_user_role');

  const openMedicineInfo = async (name: string) => {
    setMedicineInfoName(name);
    setMedicineInfoLoading(true);
    setMedicineInfo(null);
    try {
      const res = await api.get<MedicineInfo>('/pharmacy/medicine-info', { params: { medicine: name } });
      setMedicineInfo(res.data);
    } catch {
      setActionError(t('medicine_info_failed'));
      setMedicineInfoName(null);
    } finally {
      setMedicineInfoLoading(false);
    }
  };

  const fetchData = useCallback(async () => {
    setError('');
    try {
      const me = await api.get<Pharmacy>('/pharmacy/me');
      setPharmacy(me.data);
      setNeedsRegistration(false);
      const [invRes, rxRes, expRes, recallRes, preorderRes] = await Promise.all([
        api.get<InventoryItem[]>('/pharmacy/stock'),
        api.get<PrescriptionQueueItem[]>('/pharmacy/queue'),
        api.get<ExpiringItem[]>('/pharmacy/expiring', { params: { days: 90 } }),
        api.get<BatchRecall[]>('/pharmacy/recalls/mine'),
        api.get<MedicinePreorder[]>('/pharmacy/preorders'),
      ]);
      setInventory(invRes.data);
      setPrescriptions(rxRes.data);
      setExpiring(expRes.data);
      setRecalls(recallRes.data);
      setPreorders(preorderRes.data);
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 409) {
        setNeedsRegistration(true); // no pharmacy registered yet
      } else {
        console.error('Failed to fetch pharmacy data:', err);
        setError(t('pharmacy_data_failed'));
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
      setActionError(typeof message === 'string' ? message : t('action_failed'));
    }
  };

  const sellOne = (id: number) => act(() => api.post(`/pharmacy/decrement/${id}`));
  const addTen = (id: number) => act(() => api.post(`/pharmacy/update_stock/${id}?quantity_added=10`));
  const setCount = (id: number) => {
    const value = window.prompt(t('enter_counted_stock'));
    if (value === null) return;
    const n = parseInt(value, 10);
    if (Number.isNaN(n) || n < 0) { setActionError(t('invalid_stock_number')); return; }
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
  const fulfillPrescription = async (id: number) => {
    setActionError('');
    try {
      const res = await api.put<{ interaction_warnings: InteractionWarning[] }>(`/pharmacy/fulfill/${id}`);
      setLastInteractionWarnings(res.data.interaction_warnings || []);
      await fetchData();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setActionError(typeof message === 'string' ? message : t('action_failed'));
    }
  };
  const fulfillPreorder = (id: number) => act(() => api.put(`/pharmacy/preorders/${id}/fulfill`));

  if (loading) return <div className="neo-glass-container text-center pt-20">{t('loading_network')}</div>;
  if (needsRegistration) {
    return <RegisterPharmacy onRegistered={() => { setLoading(true); fetchData(); }} />;
  }

  const lowStockCount = inventory.filter((i) => i.status === 'Low' || i.status === 'Out of Stock').length;

  return (
    <div className={activeTab === 'analytics' ? '' : "neo-glass-container p-8"}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '2.2rem', color: '#10b981' }}>
            {pharmacy?.name || t('portal_title')}
          </h1>
          <p style={{ margin: '0.5rem 0 0 0', color: '#718096' }}>
            {pharmacy?.address ? `${pharmacy.address} · ` : ''}{t('live_inventory_subtitle')}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {userRole === 'ADMIN' && (
            <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: 8, padding: '0.2rem' }}>
              <button 
                onClick={() => setActiveTab('pharmacy')} 
                style={{ padding: '0.5rem 1rem', border: 'none', background: activeTab === 'pharmacy' ? 'white' : 'transparent', borderRadius: 6, cursor: 'pointer', fontWeight: activeTab === 'pharmacy' ? 'bold' : 'normal', boxShadow: activeTab === 'pharmacy' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none' }}>
                {t('tab_pharmacy')}
              </button>
              <button 
                onClick={() => setActiveTab('analytics')} 
                style={{ padding: '0.5rem 1rem', border: 'none', background: activeTab === 'analytics' ? 'white' : 'transparent', borderRadius: 6, cursor: 'pointer', fontWeight: activeTab === 'analytics' ? 'bold' : 'normal', boxShadow: activeTab === 'analytics' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none' }}>
                {t('tab_analytics')}
              </button>
            </div>
          )}
          <button
            className="neu-button"
            onClick={() => setCode(code === 'en' ? 'ta' : 'en')}
            aria-label={t('language')}
          >
            {code === 'en' ? 'தமிழ்' : 'English'}
          </button>
          <button className="neu-button" onClick={fetchData}>{t('refresh')}</button>
          <button className="neu-button" onClick={onLogout} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <LogOut size={16} /> {t('sign_out')}
          </button>
        </div>
      </header>

      {error && <div role="alert" style={{ background: '#fee2e2', color: '#991b1b', padding: '1rem', borderRadius: 8, marginBottom: '1.5rem' }}>{error}</div>}
      {actionError && <div role="alert" style={{ background: '#fef3c7', color: '#92400e', padding: '0.75rem', borderRadius: 8, marginBottom: '1rem' }}>{actionError}</div>}

      {lastInteractionWarnings.length > 0 && (
        <div role="alert" style={{ background: '#fee2e2', border: '2px solid #ef4444', color: '#991b1b', padding: '1rem', borderRadius: 8, marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <strong style={{ display: 'flex', alignItems: 'center', gap: 8 }}><TriangleAlert size={18} /> {t('interaction_warning')}</strong>
            <button onClick={() => setLastInteractionWarnings([])} style={{ background: 'none', border: 'none', color: '#991b1b', cursor: 'pointer', fontWeight: 'bold' }}>{t('dismiss')}</button>
          </div>
          {lastInteractionWarnings.map((w, idx) => (
            <div key={idx} style={{ margin: '0.5rem 0' }}>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                <strong>{w.drug_a} + {w.drug_b}</strong> ({w.severity}): {w.description}
              </p>
              {w.explanation && (
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', opacity: 0.85 }}>{w.explanation}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {activeTab === 'analytics' ? (
        <AdminAnalytics />
      ) : (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>

        {/* LEFT column: Prescriptions + expiry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-panel">
            <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShoppingCart className="text-teal-500" /> {t('pending_prescriptions')}
            </h2>
            {prescriptions.length === 0 ? (
              <div style={{ padding: '2rem', textAlign: 'center', color: '#718096' }}>{t('no_pending_prescriptions')}</div>
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
                        <strong>{t('diagnosis_label')}</strong> {rx.diagnosis}
                      </p>
                    )}
                    <p style={{ margin: '0 0 1rem 0', fontSize: '0.9rem' }}>
                      <strong>{t('medicines_label')}</strong><br />
                      {rx.medicines.length === 0
                        ? t('no_medicines_listed')
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
                      {t('fulfill_auto_deduct')}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Expiry alerts — orange-coded per the planning discussion */}
          <div className="glass-panel">
            <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: 10, color: '#f59e0b' }}>
              <CalendarClock /> {t('expiry_alerts')}
            </h2>
            {expiring.length === 0 ? (
              <p style={{ color: '#718096' }}>{t('nothing_expiring')} 🎉</p>
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

          {/* Batch Recall Alerts — matched against this pharmacy's own
              stock batch numbers (planning doc: government recalls must
              reach pharmacists immediately). */}
          <div className="glass-panel">
            <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: 10, color: '#ef4444' }}>
              <TriangleAlert /> {t('batch_recall_alerts')}
            </h2>
            {recalls.length === 0 ? (
              <p style={{ color: '#718096' }}>{t('no_recalls')}</p>
            ) : (
              recalls.map((r) => (
                <div key={r.id} style={{ padding: '0.6rem 0.8rem', background: '#fee2e2', border: '1px solid #ef4444', borderRadius: 8, marginBottom: '0.5rem' }}>
                  <strong>{r.medicine_name}</strong> · batch {r.batch_number}
                  <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: '#991b1b' }}>{r.reason}</p>
                </div>
              ))
            )}
          </div>

          {/* Medicine Pre-orders — patients reserving out-of-stock items to
              be notified/fulfilled once restocked. */}
          <div className="glass-panel">
            <h2 style={{ marginTop: 0, display: 'flex', alignItems: 'center', gap: 10, color: '#6366f1' }}>
              <PackageSearch /> {t('preorders')}
            </h2>
            {preorders.length === 0 ? (
              <p style={{ color: '#718096' }}>{t('no_preorders')}</p>
            ) : (
              preorders.map((p) => (
                <div key={p.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.6rem 0.8rem', background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 8, marginBottom: '0.5rem' }}>
                  <span><strong>{p.medicine_name}</strong> × {p.quantity} — Patient #{p.patient_id}</span>
                  <button onClick={() => fulfillPreorder(p.id)} style={{ background: '#6366f1', color: 'white', border: 'none', borderRadius: 6, padding: '0.35rem 0.7rem', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' }}>
                    {t('mark_ready')}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        {/* RIGHT column: Inventory management */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-panel">
            <h2 style={{ marginTop: 0 }}>{t('inventory')}</h2>

            {/* Rural-friendly quick entry: name + count */}
            <form onSubmit={addMedicine} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <input
                aria-label={t('new_medicine_name')}
                placeholder={t('add_medicine_placeholder')}
                value={newMedName}
                onChange={(e) => setNewMedName(e.target.value)}
                style={{ flex: 2, padding: '0.6rem', borderRadius: 8, border: '1px solid #cbd5e1' }}
              />
              <input
                aria-label={t('starting_stock_count')}
                placeholder={t('count')}
                type="number"
                min={0}
                value={newMedCount}
                onChange={(e) => setNewMedCount(e.target.value)}
                style={{ flex: 1, padding: '0.6rem', borderRadius: 8, border: '1px solid #cbd5e1' }}
              />
              <button type="submit" aria-label={t('add_medicine')} style={{ background: '#10b981', color: 'white', border: 'none', borderRadius: 8, padding: '0 1rem', cursor: 'pointer' }}>
                <Plus size={18} />
              </button>
            </form>

            <table className="inventory-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>{t('medicine')}</th>
                  <th>{t('stock')}</th>
                  <th>{t('status')}</th>
                  <th>{t('actions')}</th>
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
                        <button title={t('sold_one')} aria-label={`Record one sale of ${item.medicine_name}`} onClick={() => sellOne(item.id)}
                          style={{ border: '1px solid #ef4444', color: '#ef4444', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem' }}>
                          <Minus size={14} />
                        </button>
                        <button title={t('shipment_plus_ten')} aria-label={`Add 10 units of ${item.medicine_name} from a shipment`} onClick={() => addTen(item.id)}
                          style={{ border: '1px solid #10b981', color: '#10b981', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem' }}>
                          <Plus size={14} />
                        </button>
                        <button title={t('set_counted_stock')} aria-label={`Set counted stock for ${item.medicine_name}`} onClick={() => setCount(item.id)}
                          style={{ border: '1px solid #6366f1', color: '#6366f1', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem', fontSize: '0.7rem', fontWeight: 'bold' }}>
                          SET
                        </button>
                        <button title={t('medicine_information')} aria-label={`View information about ${item.medicine_name}`} onClick={() => openMedicineInfo(item.medicine_name)}
                          style={{ border: '1px solid #718096', color: '#718096', background: 'none', borderRadius: 6, cursor: 'pointer', padding: '0.25rem 0.4rem' }}>
                          <Info size={14} />
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
            <h3 style={{ margin: '0 0 1rem 0', color: '#718096' }}>{t('low_stock_alerts')}</h3>
            <div style={{ fontSize: '3rem', fontWeight: 'bold', color: lowStockCount > 0 ? '#ef4444' : '#10b981' }}>
              {lowStockCount}
            </div>
            <p style={{ color: '#718096', fontSize: '0.9rem', margin: '0.5rem 0 0 0' }}>
              medicine{lowStockCount === 1 ? '' : 's'} low or out of stock
            </p>
          </div>
        </div>
      </div>
      )}

      {/* Medicine Information Assistant modal */}
      {medicineInfoName && (
        <div
          onClick={() => setMedicineInfoName(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="neo-glass-container"
            style={{ maxWidth: 480, width: '90%', padding: '1.5rem', maxHeight: '80vh', overflowY: 'auto' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Info className="text-teal-500" /> {medicineInfoName}
              </h2>
              <button onClick={() => setMedicineInfoName(null)} aria-label={t('close_medicine_info')} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            {medicineInfoLoading ? (
              <p style={{ color: '#718096', textAlign: 'center', padding: '2rem 0' }}>{t('loading_ellipsis')}</p>
            ) : medicineInfo ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <strong style={{ color: '#3b82f6' }}>{t('what_its_for')}</strong>
                  <p style={{ margin: '0.25rem 0 0 0' }}>{medicineInfo.purpose}</p>
                </div>
                <div>
                  <strong style={{ color: '#10b981' }}>{t('dosage_guidance')}</strong>
                  <p style={{ margin: '0.25rem 0 0 0' }}>{medicineInfo.dosage_guidance}</p>
                </div>
                <div>
                  <strong style={{ color: '#ea580c' }}>{t('side_effects')}</strong>
                  <p style={{ margin: '0.25rem 0 0 0' }}>{medicineInfo.side_effects}</p>
                </div>
                {medicineInfo.precautions && (
                  <div>
                    <strong style={{ color: '#6366f1' }}>{t('precautions')}</strong>
                    <p style={{ margin: '0.25rem 0 0 0' }}>{medicineInfo.precautions}</p>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  const [authenticated, setAuthenticated] = useState(
    () => !!localStorage.getItem('pharmacy_access_token')
  );

  const handleLogout = () => {
    localStorage.removeItem('pharmacy_access_token');
    localStorage.removeItem('pharmacy_refresh_token');
    localStorage.removeItem('pharmacy_user_role');
    setAuthenticated(false);
  };

  if (!authenticated) {
    return <LoginScreen onLoginSuccess={() => setAuthenticated(true)} />;
  }

  return <Dashboard onLogout={handleLogout} />;
}

export default App
