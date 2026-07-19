"use client";

// Patient-facing lab test booking. The backend (modules/lab/router.py) has
// fully supported this since it was built — catalog search with prep
// instructions, nearby lab centers, booking with optional home sample
// collection, and a report-ready lifecycle that auto-saves into the
// Health Wallet — but no frontend anywhere (web or mobile) ever called any
// of it. This was the one clear "built backend, invisible feature" gap
// found in a full nav/route audit.

import { motion } from "framer-motion";
import {
  FlaskConical, MapPin, Home as HomeIcon, Search, CheckCircle, Clock,
  FileText, ArrowLeft, Phone, ChevronRight,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useProfile } from "../../contexts/ProfileContext";
import ThemedLoader from "../../components/ThemedLoader";
import api from "../../lib/api";
import type { LabTestInfo, LabCenterResponse, LabBookingResponse } from "../../types";

type Tab = "book" | "mine";
type Step = "test" | "center" | "confirm" | "done";

const STATUS_STYLE: Record<LabBookingResponse["status"], string> = {
  BOOKED: "bg-indigo-500/15 text-indigo-500 border-indigo-500/30",
  SAMPLE_COLLECTED: "bg-amber-500/15 text-amber-500 border-amber-500/30",
  PROCESSING: "bg-amber-500/15 text-amber-500 border-amber-500/30",
  REPORT_READY: "bg-teal-500/15 text-teal-500 border-teal-500/30",
  COMPLETED: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
  CANCELLED: "bg-red-500/15 text-red-500 border-red-500/30",
};

const STATUS_LABEL: Record<LabBookingResponse["status"], string> = {
  BOOKED: "Booked",
  SAMPLE_COLLECTED: "Sample Collected",
  PROCESSING: "Processing",
  REPORT_READY: "Report Ready",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export default function LabTestsPage() {
  const { user } = useAuth();
  const { profiles, activeProfile } = useProfile();

  const [tab, setTab] = useState<Tab>("book");

  // Book flow
  const [step, setStep] = useState<Step>("test");
  const [query, setQuery] = useState("");
  const [tests, setTests] = useState<LabTestInfo[]>([]);
  const [selectedTest, setSelectedTest] = useState<LabTestInfo | null>(null);
  const [centers, setCenters] = useState<LabCenterResponse[]>([]);
  const [selectedCenter, setSelectedCenter] = useState<LabCenterResponse | null>(null);
  const [homeCollection, setHomeCollection] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [notes, setNotes] = useState("");
  const [forProfileId, setForProfileId] = useState<number | "">(activeProfile?.id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [booking, setBooking] = useState(false);

  // My bookings
  const [bookings, setBookings] = useState<LabBookingResponse[]>([]);
  const [centerNames, setCenterNames] = useState<Record<number, string>>({});
  const [bookingsLoading, setBookingsLoading] = useState(false);

  const loadTests = async (q?: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<LabTestInfo[]>("/lab/tests", { params: q ? { query: q } : {} });
      setTests(res.data);
    } catch {
      setError("Could not load the test catalog.");
    } finally {
      setLoading(false);
    }
  };

  const loadCenters = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.get<LabCenterResponse[]>("/lab/centers");
      setCenters(res.data);
    } catch {
      setError("Could not load nearby lab centers.");
    } finally {
      setLoading(false);
    }
  };

  const loadBookings = async () => {
    setBookingsLoading(true);
    try {
      const [bookingsRes, centersRes] = await Promise.all([
        api.get<LabBookingResponse[]>("/lab/bookings/mine"),
        api.get<LabCenterResponse[]>("/lab/centers"),
      ]);
      setBookings(bookingsRes.data);
      setCenterNames(Object.fromEntries(centersRes.data.map((c) => [c.id, c.name])));
    } catch {
      setError("Could not load your bookings.");
    } finally {
      setBookingsLoading(false);
    }
  };

  useEffect(() => {
    if (!user) return;
    if (tab === "book" && step === "test" && tests.length === 0) loadTests();
    if (tab === "mine") loadBookings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, tab]);

  const chooseTest = (t: LabTestInfo) => {
    setSelectedTest(t);
    setStep("center");
    if (centers.length === 0) loadCenters();
  };

  const chooseCenter = (c: LabCenterResponse) => {
    setSelectedCenter(c);
    setHomeCollection(false);
    setStep("confirm");
  };

  const submitBooking = async () => {
    if (!selectedTest || !selectedCenter) return;
    setBooking(true);
    setError("");
    try {
      await api.post("/lab/bookings", {
        lab_center_id: selectedCenter.id,
        test_name: selectedTest.name,
        family_profile_id: forProfileId === "" ? null : forProfileId,
        home_collection: homeCollection,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
        notes: notes || null,
      });
      setStep("done");
    } catch (err) {
      const message = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof message === "string" ? message : "Could not book this test. Please try again.");
    } finally {
      setBooking(false);
    }
  };

  const resetBooking = () => {
    setStep("test");
    setSelectedTest(null);
    setSelectedCenter(null);
    setHomeCollection(false);
    setScheduledAt("");
    setNotes("");
  };

  const markViewed = async (id: number) => {
    try {
      await api.put(`/lab/bookings/${id}/complete`);
      loadBookings();
    } catch {
      setError("Could not update this booking.");
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-xl text-gray-500">Please log in to book a lab test.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-6 lg:p-16 flex items-start justify-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-panel max-w-3xl w-full p-8 relative overflow-hidden"
      >
        <div className="absolute inset-0 bg-gradient-to-br from-violet-500/5 to-teal-400/5 z-0" />
        <div className="relative z-10">
          <h1 className="text-3xl font-extrabold mb-1 flex items-center gap-3">
            <FlaskConical className="text-violet-500" /> Lab Tests
          </h1>
          <p className="text-gray-500 mb-6">
            Book a diagnostic test at a nearby lab, with or without home sample collection.
          </p>

          <div className="flex gap-2 mb-8">
            <button
              type="button"
              onClick={() => setTab("book")}
              className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-colors ${tab === "book" ? "bg-violet-500 text-white" : "neu-button"}`}
            >
              Book a Test
            </button>
            <button
              type="button"
              onClick={() => setTab("mine")}
              className={`flex-1 py-2.5 rounded-xl font-bold text-sm transition-colors ${tab === "mine" ? "bg-violet-500 text-white" : "neu-button"}`}
            >
              My Bookings
            </button>
          </div>

          {error && <p role="alert" className="text-red-500 font-semibold mb-6">{error}</p>}

          {tab === "book" && (
            <>
              {step === "test" && (
                loading ? (
                  <ThemedLoader variant="lab" label="Loading the test catalog…" />
                ) : (
                  <div>
                    <div className="relative mb-4">
                      <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search tests (e.g. blood sugar, thyroid, X-ray)…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") loadTests(query); }}
                        className="w-full pl-10 pr-4 py-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-violet-400"
                      />
                    </div>
                    <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                      {tests.map((t) => (
                        <button
                          key={t.name}
                          type="button"
                          onClick={() => chooseTest(t)}
                          className="w-full text-left neu-panel p-4 flex items-center justify-between hover:ring-2 hover:ring-violet-400/50 transition-shadow"
                        >
                          <div>
                            <p className="font-bold">{t.name}</p>
                            <p className="text-xs text-gray-500">{t.category} · {t.sample_type} sample</p>
                            <p className="text-xs text-gray-400 mt-1">{t.prep_instructions}</p>
                          </div>
                          <ChevronRight size={18} className="text-gray-400 shrink-0 ml-3" />
                        </button>
                      ))}
                      {tests.length === 0 && (
                        <p className="text-center text-gray-400 py-8">No tests match your search.</p>
                      )}
                    </div>
                  </div>
                )
              )}

              {step === "center" && selectedTest && (
                <div>
                  <button
                    type="button"
                    onClick={() => setStep("test")}
                    className="flex items-center gap-1.5 text-sm font-semibold text-gray-500 hover:text-violet-500 mb-4"
                  >
                    <ArrowLeft size={15} /> Back to tests
                  </button>
                  <div className="mb-4 p-3 rounded-xl bg-violet-500/10 border border-violet-500/20">
                    <p className="font-bold">{selectedTest.name}</p>
                    <p className="text-xs text-gray-500">{selectedTest.prep_instructions}</p>
                  </div>
                  {loading ? (
                    <ThemedLoader variant="lab" label="Finding nearby lab centers…" />
                  ) : (
                    <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                      {centers.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => chooseCenter(c)}
                          className="w-full text-left neu-panel p-4 flex items-center justify-between hover:ring-2 hover:ring-violet-400/50 transition-shadow"
                        >
                          <div>
                            <p className="font-bold flex items-center gap-2">
                              {c.name}
                              {c.offers_home_collection && (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-500/15 text-teal-500 border border-teal-500/30 flex items-center gap-1">
                                  <HomeIcon size={10} /> Home collection
                                </span>
                              )}
                            </p>
                            {c.address && (
                              <p className="text-xs text-gray-500 flex items-center gap-1 mt-1">
                                <MapPin size={12} /> {c.address}
                              </p>
                            )}
                            {c.phone && (
                              <p className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
                                <Phone size={12} /> {c.phone}
                              </p>
                            )}
                          </div>
                          <ChevronRight size={18} className="text-gray-400 shrink-0 ml-3" />
                        </button>
                      ))}
                      {centers.length === 0 && (
                        <p className="text-center text-gray-400 py-8">No active lab centers found yet.</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {step === "confirm" && selectedTest && selectedCenter && (
                <div>
                  <button
                    type="button"
                    onClick={() => setStep("center")}
                    className="flex items-center gap-1.5 text-sm font-semibold text-gray-500 hover:text-violet-500 mb-4"
                  >
                    <ArrowLeft size={15} /> Back to lab centers
                  </button>

                  <div className="neu-panel p-4 mb-4">
                    <p className="font-bold">{selectedTest.name}</p>
                    <p className="text-sm text-gray-500">at {selectedCenter.name}</p>
                  </div>

                  {profiles.length > 0 && (
                    <div className="mb-4">
                      <label className="text-sm font-semibold block mb-1.5">Who is this test for?</label>
                      <select
                        value={forProfileId}
                        onChange={(e) => setForProfileId(e.target.value === "" ? "" : Number(e.target.value))}
                        className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-violet-400"
                      >
                        <option value="">Myself</option>
                        {profiles.map((p) => (
                          <option key={p.id} value={p.id}>{p.full_name} ({p.relation})</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {selectedCenter.offers_home_collection && (
                    <label className="flex items-center gap-2.5 mb-4 p-3 rounded-xl bg-teal-500/5 border border-teal-500/20 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={homeCollection}
                        onChange={(e) => setHomeCollection(e.target.checked)}
                        className="w-4 h-4 accent-teal-500"
                      />
                      <span className="text-sm font-semibold flex items-center gap-1.5">
                        <HomeIcon size={15} className="text-teal-500" /> Collect the sample at home instead of visiting the lab
                      </span>
                    </label>
                  )}

                  <div className="mb-4">
                    <label className="text-sm font-semibold block mb-1.5">Preferred date &amp; time (optional)</label>
                    <input
                      type="datetime-local"
                      value={scheduledAt}
                      onChange={(e) => setScheduledAt(e.target.value)}
                      className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-violet-400"
                    />
                  </div>

                  <div className="mb-6">
                    <label className="text-sm font-semibold block mb-1.5">Notes (optional)</label>
                    <textarea
                      rows={2}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="Anything the lab should know…"
                      className="w-full p-3 rounded-xl bg-white/50 dark:bg-black/20 border border-white/30 focus:outline-none focus:ring-2 focus:ring-violet-400 resize-none"
                    />
                  </div>

                  <button
                    type="button"
                    onClick={submitBooking}
                    disabled={booking}
                    className="neu-button w-full py-3 bg-violet-500 text-white font-bold rounded-xl disabled:opacity-50"
                  >
                    {booking ? "Booking…" : "Confirm Booking"}
                  </button>
                </div>
              )}

              {step === "done" && (
                <div className="text-center py-10">
                  <CheckCircle size={48} className="text-emerald-500 mx-auto mb-4" />
                  <h2 className="text-xl font-bold mb-2">Test booked!</h2>
                  <p className="text-gray-500 mb-6">The lab will update the status as your sample moves through the process.</p>
                  <div className="flex gap-3 justify-center">
                    <button type="button" onClick={resetBooking} className="neu-button px-5 py-2.5 font-bold rounded-xl">
                      Book another
                    </button>
                    <button
                      type="button"
                      onClick={() => { setTab("mine"); resetBooking(); }}
                      className="neu-button px-5 py-2.5 bg-violet-500 text-white font-bold rounded-xl"
                    >
                      View My Bookings
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {tab === "mine" && (
            bookingsLoading ? (
              <ThemedLoader variant="lab" label="Loading your bookings…" />
            ) : bookings.length === 0 ? (
              <p className="text-center text-gray-400 py-12">No lab tests booked yet.</p>
            ) : (
              <div className="space-y-4">
                {bookings.map((b) => (
                  <div key={b.id} className="neu-panel p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div>
                        <p className="font-bold">{b.test_name}</p>
                        <p className="text-xs text-gray-500">{centerNames[b.lab_center_id] || `Lab #${b.lab_center_id}`}</p>
                      </div>
                      <span className={`shrink-0 px-2.5 py-1 rounded-full text-xs font-bold border ${STATUS_STYLE[b.status]}`}>
                        {STATUS_LABEL[b.status]}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-gray-400">
                      {b.home_collection && (
                        <span className="flex items-center gap-1"><HomeIcon size={12} /> Home collection</span>
                      )}
                      {b.scheduled_at && (
                        <span className="flex items-center gap-1"><Clock size={12} /> {new Date(b.scheduled_at).toLocaleString()}</span>
                      )}
                    </div>

                    {(b.status === "REPORT_READY" || b.status === "COMPLETED") && b.report_payload && (
                      <div className="mt-3 pt-3 border-t border-white/10">
                        <p className="text-sm font-bold flex items-center gap-1.5 mb-2">
                          <FileText size={14} className="text-teal-500" /> Report
                        </p>
                        {b.report_payload.summary && (
                          <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">{b.report_payload.summary}</p>
                        )}
                        {b.report_payload.values && b.report_payload.values.length > 0 && (
                          <ul className="text-xs text-gray-500 space-y-1 mb-2">
                            {b.report_payload.values.map((v, i) => (
                              <li key={i}>
                                {v.parameter}: <span className="font-semibold">{v.value}{v.unit ? ` ${v.unit}` : ""}</span>
                                {v.reference_range ? ` (ref: ${v.reference_range})` : ""}
                                {v.flag && v.flag !== "NORMAL" ? ` — ${v.flag}` : ""}
                              </li>
                            ))}
                          </ul>
                        )}
                        {b.report_payload.file_url && (
                          <a href={b.report_payload.file_url} target="_blank" rel="noreferrer" className="text-xs font-bold text-violet-500 hover:underline">
                            View full report file
                          </a>
                        )}
                        {b.status === "REPORT_READY" && (
                          <button
                            type="button"
                            onClick={() => markViewed(b.id)}
                            className="mt-3 w-full neu-button py-2 text-sm font-bold rounded-lg"
                          >
                            Mark as viewed
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </motion.div>
    </div>
  );
}
