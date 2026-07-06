/**
 * Shared API contract types for the web portal.
 * Mirrors apps/backend_service/schemas.py — keep the two in sync.
 * (Introduced in roadmap Phase 1 to end the pervasive `any` typing.)
 */

export interface User {
  id: number;
  username: string;
  email?: string;
  full_name?: string;
  role: 'PATIENT' | 'DOCTOR' | 'PHARMACIST' | 'HOSPITAL' | 'ADMIN';
}

export interface FamilyProfile {
  id: number;
  user_id: number;
  full_name: string;
  relation: string;
  age: number;
  gender: string;
  blood_group?: string | null;
  allergies?: string | null;
  chronic_conditions?: string | null;
  photo_url?: string | null;
  color_tag?: string | null;
  created_at: string;
}

export interface DoctorPublic {
  id: number;
  full_name: string;
  specialty: string;
  qualifications?: string | null;
  experience_years: number;
  consultation_fee: number;
  languages?: string | null;
  is_available: boolean;
}

export interface Slot {
  id: number;
  start_time: string;
  end_time: string;
  is_booked: boolean;
}

export interface Appointment {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  doctor_id: number;
  scheduled_at: string;
  status: 'PENDING' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED';
  triage_summary?: string | null;
  consultation_notes?: string | null;
  payment_id?: number | null;
  created_at: string;
}

export interface MedicineItem {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
}

export interface Prescription {
  id: number;
  appointment_id?: number | null;
  patient_id: number;
  family_profile_id?: number | null;
  doctor_id: number;
  medicines: MedicineItem[];
  dosage_instructions?: string | null;
  diagnosis?: string | null;
  notes?: string | null;
  is_fulfilled: boolean;
  created_at: string;
}

export interface EHRRecord {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  record_type: 'prescription' | 'lab_report' | 'triage_log' | 'vaccination' | 'scan' | 'note';
  title?: string | null;
  content: string;
  payload?: Record<string, unknown> | null;
  doctor_name?: string | null;
  record_date?: string | null;
  created_at: string;
}

export interface TriageResult {
  severity_score: number;
  predicted_condition: string;
  home_remedies: string;
  doctor_recommendation: string;
  recovery_time: string;
  status: string;
  confidence_score: number;
  explanation: string;
  disclaimer: string;
}

export interface EmergencySOS {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  location_lat?: number | null;
  location_lng?: number | null;
  location_text?: string | null;
  /** Transcribed voice description riding with the alert (Phase 6). */
  voice_note?: string | null;
  severity: string;
  status: 'ACTIVE' | 'RESPONDED' | 'RESOLVED';
  responded_by?: number | null;
  /** Times the alert was reassigned after going unanswered (Phase 6). */
  escalation_level?: number;
  assigned_hospital_id?: number | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface PaymentOrder {
  order_id: string;
  amount: number;
  currency: string;
  is_mock: boolean;
}

/** Mirrors schemas.PaymentResponse — one row of GET /payments/my history or
 * GET /payments/{order_id}/status. */
export interface PaymentRecord {
  id: number;
  order_id: string;
  patient_id: number;
  amount: number;
  currency: string;
  status: 'CREATED' | 'PAID' | 'CONSUMED' | 'REFUNDED' | 'FAILED';
  gateway: 'razorpay' | 'mock';
  created_at: string;
}

export interface NearbyPharmacyResult {
  pharmacy_id: number;
  pharmacy_name: string;
  address?: string | null;
  phone?: string | null;
  distance_km?: number | null;
  available: boolean;
  medicine_name?: string | null;
  price?: number | null;
  substitutes: string[];
  lat?: number | null;
  lng?: number | null;
}
