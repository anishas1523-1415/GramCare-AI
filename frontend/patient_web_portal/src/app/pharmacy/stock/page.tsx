"use client";

// Stock management — mirrors mobile/pharmacy_app's stock_screen.dart +
// add_item_screen.dart, plus folds expiry_alerts_screen.dart and
// shortage_alerts_screen.dart in as filter tabs on the same table (both are
// just client-side filters over the same GET /pharmacy/stock data, per the
// mobile app's own shortage_alerts_screen.dart comment — no reason to split
// them into separate pages here).

import React, { useEffect, useState, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Plus, Search, Package, AlertTriangle, X } from 'lucide-react';
import { useAuth } from '../../../contexts/AuthContext';
import api from '../../../lib/api';
import type { PharmacyStockItem } from '../../../types';
import { SkeletonList } from '../../../components/Skeleton';

const STATUS_STYLE: Record<PharmacyStockItem['status'], string> = {
  Optimal: 'bg-emerald-500/15 text-emerald-600',
  Low: 'bg-amber-500/15 text-amber-600',
  'Out of Stock': 'bg-red-500/15 text-red-600',
};

function AddItemForm({ onAdded, onClose }: { onAdded: () => void; onClose: () => void }) {
  const [name, setName] = useState('');
  const [genericGroup, setGenericGroup] = useState('');
  const [stockCount, setStockCount] = useState('');
  const [price, setPrice] = useState('');
  const [requiresRx, setRequiresRx] = useState(false);
  const [expiryDate, setExpiryDate] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !stockCount || !price) {
      setError('Medicine name, stock count, and price are required.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.post('/pharmacy/items', {
        medicine_name: name.trim(),
        generic_group: genericGroup.trim() || undefined,
        stock_count: Number(stockCount),
        price: Number(price),
        requires_prescription: requiresRx,
        expiry_date: expiryDate || undefined,
        batch_number: batchNumber.trim() || undefined,
      });
      onAdded();
      onClose();
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === 'string' ? message : 'Could not add this item.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-6" role="dialog" aria-modal="true">
      <form onSubmit={submit} className="glass-panel p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-xl font-bold flex items-center gap-2"><Package className="text-emerald-500" /> Add Item</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600"><X /></button>
        </div>
        <div className="space-y-3">
          <input className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" placeholder="Medicine name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" placeholder="Generic group (optional)" value={genericGroup} onChange={(e) => setGenericGroup(e.target.value)} />
          <div className="grid grid-cols-2 gap-3">
            <input type="number" min={0} className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" placeholder="Initial stock count" value={stockCount} onChange={(e) => setStockCount(e.target.value)} />
            <input type="number" min={0} step="0.01" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" placeholder="Price (₹)" value={price} onChange={(e) => setPrice(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input type="date" className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
            <input className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/20" placeholder="Batch number (optional)" value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} />
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" checked={requiresRx} onChange={(e) => setRequiresRx(e.target.checked)} /> Requires prescription
          </label>
        </div>
        {error && <p role="alert" className="text-red-500 text-sm font-semibold mt-3">{error}</p>}
        <button disabled={busy} className="w-full mt-5 py-3 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl disabled:opacity-50">
          {busy ? 'Saving…' : 'Save Item'}
        </button>
      </form>
    </div>
  );
}

function StockPageInner() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialFilter = searchParams.get('filter');

  const [items, setItems] = useState<PharmacyStockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'all' | 'shortages' | 'expiring'>(initialFilter === 'shortages' || initialFilter === 'expiring' ? initialFilter : 'all');
  const [showAdd, setShowAdd] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<PharmacyStockItem[]>('/pharmacy/stock');
      setItems(res.data);
    } catch {
      // Handled by the empty/error state below.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role !== 'PHARMACIST') { router.push('/'); return; }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [user, authLoading, router, load]);

  const restock = async (id: number, delta: number) => {
    setBusyId(id);
    try {
      await api.post(`/pharmacy/update_stock/${id}`, null, { params: { quantity_added: delta } });
      await load();
    } catch {
      alert('Could not update stock.');
    } finally {
      setBusyId(null);
    }
  };

  const filtered = items
    .filter((i) => (tab === 'shortages' ? i.status !== 'Optimal' : tab === 'expiring' ? !!i.expiry_date : true))
    .filter((i) => i.medicine_name.toLowerCase().includes(search.toLowerCase()));

  if (authLoading || loading) {
    return <div className="min-h-screen p-8 lg:p-24"><div className="glass-panel p-6"><SkeletonList count={5} /></div></div>;
  }

  return (
    <div className="min-h-screen p-8 lg:p-24">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <h1 className="text-4xl font-extrabold flex items-center gap-3">
          <Package className="text-emerald-500" size={36} /> Stock
        </h1>
        <button
          onClick={() => setShowAdd(true)}
          className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white font-bold rounded-xl flex items-center gap-2"
        >
          <Plus size={18} /> Add Item
        </button>
      </div>

      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex gap-2">
          {(['all', 'shortages', 'expiring'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${tab === t ? 'bg-emerald-500 text-white' : 'bg-white/40 dark:bg-black/20'}`}
            >
              {t === 'all' ? 'All' : t === 'shortages' ? 'Low / Out' : 'Has expiry date'}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search medicine…"
            className="w-full pl-9 p-2.5 rounded-lg bg-white/50 dark:bg-black/20 border border-white/20 text-sm"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="glass-panel p-10 text-center text-gray-500">
          {items.length === 0 ? 'No medicines in stock yet. Add your first item.' : 'Nothing matches this view.'}
        </div>
      ) : (
        <div className="glass-panel overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b border-white/10">
                <th className="p-4">Medicine</th>
                <th className="p-4">Stock</th>
                <th className="p-4">Price</th>
                <th className="p-4">Expiry</th>
                <th className="p-4">Status</th>
                <th className="p-4">Restock</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id} className="border-b border-white/5 last:border-0">
                  <td className="p-4 font-semibold">
                    {item.medicine_name}
                    {item.requires_prescription && <span className="ml-2 text-xs font-bold text-indigo-500">Rx</span>}
                  </td>
                  <td className="p-4 font-mono">{item.stock_count}</td>
                  <td className="p-4 font-mono">₹{item.price.toFixed(2)}</td>
                  <td className="p-4">
                    {item.expiry_date ? (
                      <span className={item.days_left != null && item.days_left <= 30 ? 'text-amber-500 font-semibold flex items-center gap-1' : ''}>
                        {item.days_left != null && item.days_left <= 30 && <AlertTriangle size={14} />}
                        {item.expiry_date}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="p-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-bold ${STATUS_STYLE[item.status]}`}>{item.status}</span>
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <button
                        disabled={busyId === item.id}
                        onClick={() => restock(item.id, 10)}
                        className="px-2.5 py-1 bg-emerald-500/15 text-emerald-600 rounded-lg text-xs font-bold disabled:opacity-40"
                        title="Add 10 (shipment received)"
                      >
                        +10
                      </button>
                      <button
                        disabled={busyId === item.id || item.stock_count <= 0}
                        onClick={() => restock(item.id, -1)}
                        className="px-2.5 py-1 bg-red-500/15 text-red-600 rounded-lg text-xs font-bold disabled:opacity-40"
                        title="Log one sale"
                      >
                        −1
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && <AddItemForm onAdded={load} onClose={() => setShowAdd(false)} />}
    </div>
  );
}

export default function StockPage() {
  return (
    <Suspense fallback={<div className="min-h-screen p-8 lg:p-24"><div className="glass-panel p-6"><SkeletonList count={5} /></div></div>}>
      <StockPageInner />
    </Suspense>
  );
}
