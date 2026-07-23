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
  triage_severity_score?: number | null;
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

/** Mirrors schemas.InteractionWarningSchema — one row of
 * interaction_warnings (POST /ehr/issue_prescription, PUT
 * /pharmacy/fulfill/{id}, POST /pharmacy/interactions/check). `explanation`
 * is the Explainable AI "why" field, added alongside the original
 * drug_a/drug_b/severity/description fields. */
export interface InteractionWarning {
  drug_a: string;
  drug_b: string;
  severity: 'HIGH' | 'MODERATE';
  description: string;
  explanation: string;
}

/** Mirrors modules/cds/router.py's CdsAlertResponse — one row of
 * POST /cds/check's `alerts` array. Combines the drug-interaction check
 * with the three new Clinical Decision Support heuristics (allergy
 * cross-check, duplicate-therapy, dosage-sanity) into one explained list. */
export interface CdsAlert {
  category: 'INTERACTION' | 'ALLERGY' | 'DUPLICATE_THERAPY' | 'DOSAGE_CHANGE';
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  explanation: string;
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
  /** Populated only by POST /ehr/issue_prescription's response — other read
   * paths omit it. */
  interaction_warnings?: InteractionWarning[] | null;
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

export interface EmergencyContact {
  id: number;
  user_id: number;
  name: string;
  phone: string;
  relation?: string | null;
}

export interface LabTestInfo {
  name: string;
  category: string;
  prep_instructions: string;
  typical_turnaround_hours: number;
  sample_type: string;
}

export interface LabCenterResponse {
  id: number;
  owner_user_id: number;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  phone?: string | null;
  offers_home_collection: boolean;
  is_active: boolean;
}

export interface LabResultValue {
  parameter: string;
  value: string;
  unit?: string | null;
  reference_range?: string | null;
  flag?: string | null;
}

export interface LabBookingResponse {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  lab_center_id: number;
  test_name: string;
  home_collection: boolean;
  scheduled_at?: string | null;
  status: 'BOOKED' | 'SAMPLE_COLLECTED' | 'PROCESSING' | 'REPORT_READY' | 'COMPLETED' | 'CANCELLED';
  notes?: string | null;
  report_payload?: {
    values?: LabResultValue[];
    summary?: string | null;
    file_url?: string | null;
  } | null;
  report_ready_at?: string | null;
  created_at: string;
}

/** Mirrors schemas.PreventiveReminder — one rule-based screening/
 * vaccination reminder from GET /preventive/reminders. Rule-based (a
 * deterministic ruleset), NOT a machine-learning prediction. */
export interface PreventiveReminder {
  key: string;
  title: string;
  category: 'screening' | 'vaccination';
  reason: string;
  due: boolean;
  last_done_date?: string | null;
  suggested_action: 'lab_test' | 'consultation';
}

/** Mirrors schemas.NavigatorItem — one ranked "what to do next" entry from
 * GET /navigator/next-steps, carrying its own explainability (`reason`) and
 * a suggested action the client can render as a button/link. */
export interface NavigatorItem {
  category: string;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  reason: string;
  cta_label?: string | null;
  cta_route?: string | null;
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
  is_jan_aushadhi: boolean;
}

/** Mirrors schemas.ReferralResponse (modules/referrals/router.py). A doctor's
 * referral of a patient to a specific colleague (referred_to_doctor_id set)
 * or open to any doctor of `specialty` (referred_to_doctor_id null). */
export interface Referral {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  referring_doctor_id: number;
  referred_to_doctor_id?: number | null;
  specialty: string;
  reason: string;
  notes?: string | null;
  status: 'PENDING' | 'ACCEPTED' | 'DECLINED' | 'COMPLETED';
  created_at: string;
  resolved_at?: string | null;
}
