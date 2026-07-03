// Shared response shapes for the Pharmacy Dashboard — mirror the backend
// response models in apps/backend_service/modules/pharmacy_inventory/router.py.

export interface Pharmacy {
  id: number;
  owner_user_id: number;
  name: string;
  address?: string | null;
  lat?: number | null;
  lng?: number | null;
  phone?: string | null;
  is_active: boolean;
}

export interface InventoryItem {
  id: number;
  pharmacy_id: number | null;
  medicine_name: string;
  generic_group?: string | null;
  stock_count: number;
  price: number;
  requires_prescription: boolean;
  expiry_date?: string | null;
  batch_number?: string | null;
  status: 'Optimal' | 'Low' | 'Out of Stock';
}

export interface ExpiringItem extends InventoryItem {
  days_left: number;
}

export interface MedicineItem {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
}

export interface PrescriptionQueueItem {
  id: number;
  patient_id: number;
  medicines: MedicineItem[];
  diagnosis: string | null;
  dosage_instructions: string | null;
  is_fulfilled: boolean;
  created_at: string;
}

export interface OCRResult {
  extracted_text: string;
  medicines_parsed: string[];
  confidence: number;
}
