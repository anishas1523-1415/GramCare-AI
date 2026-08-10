export interface LabCenter {
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

export interface LabTestInfo {
  name: string;
  category: string;
  prep_instructions: string;
  typical_turnaround_hours: number;
  sample_type: string;
}

export type BookingStatus =
  | 'BOOKED'
  | 'SAMPLE_COLLECTED'
  | 'PROCESSING'
  | 'REPORT_READY'
  | 'COMPLETED'
  | 'CANCELLED';

export interface LabResultValue {
  parameter: string;
  value: string;
  unit?: string | null;
  reference_range?: string | null;
  flag?: 'NORMAL' | 'LOW' | 'HIGH' | null;
}

export interface LabBooking {
  id: number;
  patient_id: number;
  family_profile_id?: number | null;
  lab_center_id: number;
  test_name: string;
  home_collection: boolean;
  scheduled_at?: string | null;
  status: BookingStatus;
  notes?: string | null;
  report_payload?: {
    values: LabResultValue[];
    summary?: string | null;
    file_url?: string | null;
  } | null;
  report_ready_at?: string | null;
  created_at: string;
}
