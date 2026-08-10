import { useState, useEffect } from 'react';
import { Activity, MapPin, TrendingUp, Truck, PackageSearch } from 'lucide-react';
import api from '../lib/api';

interface HealthCluster {
  condition: string;
  location: string;
  case_count: number;
  avg_severity: number;
  max_severity: number;
  first_seen: string;
  last_seen: string;
  alert: boolean;
}

interface ResourceForecast {
  resource_type: string;
  recommended_location: string;
  urgency: string;
  reason: string;
}

interface OverviewStats {
  window_days: number;
  total_assessments: number;
  critical_assessments: number;
  active_sos: number;
  unfulfilled_prescriptions: number;
  registered_pharmacies: number;
}

export default function AdminAnalytics() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [clusters, setClusters] = useState<HealthCluster[]>([]);
  const [forecasts, setForecasts] = useState<ResourceForecast[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, clustersRes, forecastsRes] = await Promise.all([
          api.get<OverviewStats>('/analytics/overview?days=7'),
          api.get<HealthCluster[]>('/analytics/health-clusters?days=14&min_cases=3'),
          api.get<ResourceForecast[]>('/analytics/resource-forecasting')
        ]);
        setStats(statsRes.data);
        setClusters(clustersRes.data);
        setForecasts(forecastsRes.data);
      } catch (err) {
        console.error('Failed to load analytics', err);
        setError('Failed to load community health intelligence data.');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, []);

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>Loading Community Intelligence...</div>;
  }

  if (error) {
    return <div style={{ padding: '2rem', color: 'red' }}>{error}</div>;
  }

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem' }}>
      <h1 style={{ color: '#4f46e5', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Activity size={32} /> Community Health Intelligence
      </h1>
      
      {/* Overview Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#3b82f6' }}>{stats?.total_assessments}</div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>Triage Assessments (7d)</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#ef4444' }}>{stats?.active_sos}</div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>Active SOS Alerts</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#f59e0b' }}>{stats?.unfulfilled_prescriptions}</div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>Pending Prescriptions</div>
        </div>
        <div className="glass-panel" style={{ padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#10b981' }}>{stats?.registered_pharmacies}</div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>Registered Pharmacies</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Heatmaps / Clusters */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#b91c1c', marginTop: 0 }}>
            <MapPin size={24} /> Localized Outbreak Heatmap
          </h2>
          <p style={{ color: '#4b5563', marginBottom: '1rem', fontSize: '0.9rem' }}>
            AI-detected symptom clusters mapping potential outbreaks.
          </p>
          
          {clusters.length === 0 ? (
            <div style={{ color: '#9ca3af' }}>No outbreak clusters detected recently.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {clusters.map((c, i) => (
                <div key={i} style={{ borderLeft: c.alert ? '4px solid #ef4444' : '4px solid #f59e0b', padding: '1rem', background: '#f9fafb', borderRadius: '0 8px 8px 0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '1.1rem', color: '#111827' }}>{c.condition}</strong>
                    <span style={{ background: c.alert ? '#fee2e2' : '#fef3c7', color: c.alert ? '#991b1b' : '#92400e', padding: '0.2rem 0.6rem', borderRadius: 999, fontSize: '0.8rem', fontWeight: 'bold' }}>
                      {c.case_count} Cases
                    </span>
                  </div>
                  <div style={{ color: '#4b5563', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <MapPin size={14} /> {c.location}
                  </div>
                  <div style={{ color: '#6b7280', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                    Avg Severity: <span style={{ color: c.avg_severity > 60 ? '#ef4444' : 'inherit' }}>{c.avg_severity}</span> 
                    {' '} | First seen: {new Date(c.first_seen).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Resource Allocation Forecast */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#0369a1', marginTop: 0 }}>
            <TrendingUp size={24} /> Resource Allocation Forecast
          </h2>
          <p style={{ color: '#4b5563', marginBottom: '1rem', fontSize: '0.9rem' }}>
            Predictive analytics for medicines and emergency services.
          </p>
          
          {forecasts.length === 0 ? (
            <div style={{ color: '#9ca3af' }}>No resource shortages predicted at this time.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {forecasts.map((f, i) => (
                <div key={i} style={{ padding: '1rem', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.5rem' }}>
                    {f.resource_type === 'ambulance' ? <Truck size={18} color="#0284c7" /> : <PackageSearch size={18} color="#0284c7" />}
                    <strong style={{ color: '#0c4a6e', textTransform: 'capitalize' }}>
                      Dispatch {f.resource_type}
                    </strong>
                    <span style={{ marginLeft: 'auto', background: f.urgency === 'HIGH' ? '#ef4444' : '#f59e0b', color: 'white', padding: '0.2rem 0.6rem', borderRadius: 4, fontSize: '0.75rem', fontWeight: 'bold' }}>
                      {f.urgency}
                    </span>
                  </div>
                  <div style={{ fontWeight: 500, color: '#0f172a', marginBottom: '0.25rem' }}>
                    Target: {f.recommended_location}
                  </div>
                  <div style={{ color: '#334155', fontSize: '0.9rem' }}>
                    {f.reason}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
