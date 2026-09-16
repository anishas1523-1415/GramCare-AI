// English/Tamil strings for the pharmacist portal.
//
// The patient portal and all three mobile apps have been bilingual for a
// while; this portal never was, which left the people running village
// pharmacies — the users least likely to prefer English — on the only
// English-only surface in the product.
//
// Same deliberate shape as frontend/patient_web_portal's LocaleContext and
// the mobile apps' app_strings.dart: a plain key -> string table per
// language, so a Tamil speaker can review every string in one file without
// a toolchain.

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

export type LocaleCode = 'en' | 'ta';

// Shared with ErrorBoundary, which is a class component and cannot use the
// hook — it reads this key directly.
export const LOCALE_STORAGE_KEY = 'gramcare_pharmacy_locale';

const en: Record<string, string> = {
  // Login / register / recovery
  portal_title: 'GramCare Pharmacy Portal',
  create_pharmacist_account: 'Create a Pharmacist Account',
  reset_your_password: 'Reset Your Password',
  sign_in_subtitle: 'Sign in with your pharmacist account.',
  register_subtitle: 'Register your pharmacy to manage stock and prescriptions.',
  forgot_subtitle: "Enter your account email and we'll send a reset link.",
  full_name: 'Full name',
  username: 'Username',
  username_or_email: 'Username or Email',
  email: 'Email',
  phone_optional: 'Phone (optional)',
  password: 'Password',
  min_8_chars: 'At least 8 characters.',
  sign_in: 'Sign In',
  signing_in: 'Signing in...',
  create_account: 'Create Account',
  creating_account: 'Creating account...',
  send_reset_link: 'Send Reset Link',
  sending: 'Sending...',
  create_an_account: 'Create an account',
  forgot_password: 'Forgot password?',
  back_to_sign_in: '← Back to sign in',
  not_a_pharmacist_account: 'This account is not a pharmacist account.',
  account_created_pending_role:
    'Account created. You can sign in once a pharmacist role is assigned.',
  reset_link_sent: 'If that email has an account, a password reset link is on its way.',
  login_failed: 'Login failed',
  registration_failed: 'Registration failed',
  reset_link_failed: 'Could not send the reset link',

  // Pharmacy registration
  register_pharmacy_name: 'Pharmacy name (e.g. Grama Medicals)',
  register_address: 'Address / village',
  register_phone: 'Phone',
  registering: 'Registering…',
  register_with_location: 'Register (uses your current location)',
  jan_aushadhi_note: 'This is a Jan Aushadhi Kendra (government low-cost pharmacy)',
  register_your_pharmacy: 'Register your pharmacy',
  register_pharmacy_blurb:
    'Patients nearby will see your shop and live medicine availability once registered.',
  add_stock_from_invoice: 'Add stock from invoice photo',
  ai_found: 'AI found:',
  confirm_add_ten_each: 'Confirm — add each with 10 units (adjust after)',
  registration_failed_generic: 'Registration failed.',

  // Dashboard chrome
  loading_network: 'Loading Pharmacy Network...',
  live_inventory_subtitle: 'Live Inventory & Prescription Fulfillment',
  tab_pharmacy: 'Pharmacy',
  tab_analytics: 'Analytics',
  refresh: 'Refresh',
  sign_out: 'Sign Out',
  language: 'Language',

  // Prescriptions
  pending_prescriptions: 'Pending Prescriptions',
  no_pending_prescriptions: 'No pending prescriptions.',
  diagnosis_label: 'Diagnosis:',
  medicines_label: 'Medicines:',
  no_medicines_listed: 'No medicines listed',
  interaction_warning: 'Medicine Interaction Warning',
  dismiss: 'Dismiss',

  // Alerts
  expiry_alerts: 'Expiry Alerts (next 90 days)',
  nothing_expiring: 'Nothing expiring soon.',
  batch_recall_alerts: 'Batch Recall Alerts',
  no_recalls: 'No recalls affecting your stock.',
  preorders: 'Pre-orders',
  no_preorders: 'No pending pre-orders.',
  mark_ready: 'Mark Ready',
  low_stock_alerts: 'Low Stock Alerts',

  // Inventory
  inventory: 'Inventory',
  medicine: 'Medicine',
  stock: 'Stock',
  status: 'Status',
  actions: 'Actions',
  out_of_stock: 'Out of Stock',
  low_stock: 'Low Stock',
  stock_optimal: 'Optimal',
  new_medicine_name: 'New medicine name',
  add_medicine_placeholder: 'Add medicine (e.g. Dolo 650)',
  starting_stock_count: 'Starting stock count',
  count: 'Count',
  add_medicine: 'Add medicine',
  sold_one: 'Sold 1 (tap-to-decrement)',
  shipment_plus_ten: 'Shipment +10',
  set_counted_stock: 'Set counted stock',
  enter_counted_stock: 'Enter the counted stock (end-of-day count):',
  invalid_stock_number: 'Enter a valid non-negative number.',
  action_failed: 'Action failed',

  // Medicine info
  medicine_information: 'Medicine information',
  close_medicine_info: 'Close medicine info',
  loading_ellipsis: 'Loading…',
  what_its_for: "What it's for",
  dosage_guidance: 'Dosage guidance',
  side_effects: 'Side effects to watch for',
  precautions: 'Precautions',
  medicine_info_failed: 'Could not load medicine information.',

  // Invoice scan
  no_medicines_recognized: 'No medicines recognized on this invoice.',
  invoice_read_failed: 'Could not read the invoice image.',
  some_items_failed: 'Failed to add some items — check the inventory list.',

  // Data loading
  pharmacy_data_failed: 'Could not load pharmacy data. Check your connection and try again.',

  fulfill_auto_deduct: 'Fulfill (auto-deducts stock)',

  // Analytics
  loading_community_intelligence: 'Loading Community Intelligence...',
  triage_assessments_7d: 'Triage Assessments (7d)',
  active_sos_alerts: 'Active SOS Alerts',
  pending_prescriptions_stat: 'Pending Prescriptions',
  registered_pharmacies: 'Registered Pharmacies',
  no_outbreak_clusters: 'No outbreak clusters detected recently.',
  no_resource_shortages: 'No resource shortages predicted at this time.',
  analytics_failed: 'Failed to load community health intelligence data.',
  community_health_intelligence: 'Community Health Intelligence',
  outbreak_heatmap: 'Localized Outbreak Heatmap',
  outbreak_heatmap_blurb: 'AI-detected symptom clusters mapping potential outbreaks.',
  avg_severity: 'Avg Severity:',
  resource_forecast: 'Resource Allocation Forecast',
  resource_forecast_blurb: 'Predictive analytics for medicines and emergency services.',

  // Crash fallback
  something_went_wrong: 'Something went wrong',
  crash_body: 'This dashboard hit an unexpected error. Your inventory data is safe — reload to try again.',
  reload: 'Reload',
};

const ta: Record<string, string> = {
  portal_title: 'GramCare மருந்தகப் போர்டல்',
  create_pharmacist_account: 'மருந்தாளுநர் கணக்கை உருவாக்கவும்',
  reset_your_password: 'உங்கள் கடவுச்சொல்லை மீட்டமைக்கவும்',
  sign_in_subtitle: 'உங்கள் மருந்தாளுநர் கணக்கில் உள்நுழையவும்.',
  register_subtitle:
    'இருப்பு மற்றும் மருந்துச் சீட்டுகளை நிர்வகிக்க உங்கள் மருந்தகத்தைப் பதிவு செய்யவும்.',
  forgot_subtitle:
    'உங்கள் கணக்கு மின்னஞ்சலை உள்ளிடவும், மீட்டமைப்பு இணைப்பை அனுப்புகிறோம்.',
  full_name: 'முழுப் பெயர்',
  username: 'பயனர் பெயர்',
  username_or_email: 'பயனர் பெயர் அல்லது மின்னஞ்சல்',
  email: 'மின்னஞ்சல்',
  phone_optional: 'தொலைபேசி (விருப்பத்திற்குரியது)',
  password: 'கடவுச்சொல்',
  min_8_chars: 'குறைந்தது 8 எழுத்துகள்.',
  sign_in: 'உள்நுழை',
  signing_in: 'உள்நுழைகிறது...',
  create_account: 'கணக்கை உருவாக்கு',
  creating_account: 'கணக்கை உருவாக்குகிறது...',
  send_reset_link: 'மீட்டமைப்பு இணைப்பை அனுப்பு',
  sending: 'அனுப்புகிறது...',
  create_an_account: 'கணக்கை உருவாக்கவும்',
  forgot_password: 'கடவுச்சொல் மறந்துவிட்டதா?',
  back_to_sign_in: '← உள்நுழைவுக்குத் திரும்பு',
  not_a_pharmacist_account: 'இந்தக் கணக்கு மருந்தாளுநர் கணக்கு அல்ல.',
  account_created_pending_role:
    'கணக்கு உருவாக்கப்பட்டது. மருந்தாளுநர் பங்கு வழங்கப்பட்டவுடன் உள்நுழையலாம்.',
  reset_link_sent:
    'அந்த மின்னஞ்சலுக்குக் கணக்கு இருந்தால், கடவுச்சொல் மீட்டமைப்பு இணைப்பு அனுப்பப்படும்.',
  login_failed: 'உள்நுழைவு தோல்வியடைந்தது',
  registration_failed: 'பதிவு தோல்வியடைந்தது',
  reset_link_failed: 'மீட்டமைப்பு இணைப்பை அனுப்ப முடியவில்லை',

  register_pharmacy_name: 'மருந்தகப் பெயர் (எ.கா. கிராம மெடிக்கல்ஸ்)',
  register_address: 'முகவரி / கிராமம்',
  register_phone: 'தொலைபேசி',
  registering: 'பதிவு செய்கிறது…',
  register_with_location: 'பதிவு செய் (உங்கள் தற்போதைய இருப்பிடம் பயன்படுத்தப்படும்)',
  jan_aushadhi_note: 'இது ஜன் ஔஷதி கேந்திரா (அரசு குறைந்த விலை மருந்தகம்)',
  register_your_pharmacy: 'உங்கள் மருந்தகத்தைப் பதிவு செய்யுங்கள்',
  register_pharmacy_blurb:
    'பதிவு செய்தவுடன், அருகிலுள்ள நோயாளிகள் உங்கள் கடையையும் நேரடி மருந்து கிடைப்பையும் பார்க்க முடியும்.',
  add_stock_from_invoice: 'விலைப்பட்டியல் படத்திலிருந்து இருப்பைச் சேர்',
  ai_found: 'AI கண்டறிந்தவை:',
  confirm_add_ten_each: 'உறுதிப்படுத்து — ஒவ்வொன்றையும் 10 அலகுகளுடன் சேர் (பின்னர் மாற்றலாம்)',
  registration_failed_generic: 'பதிவு தோல்வியடைந்தது.',

  loading_network: 'மருந்தக வலையமைப்பு ஏற்றப்படுகிறது...',
  live_inventory_subtitle: 'நேரடி இருப்பு மற்றும் மருந்துச் சீட்டு நிறைவேற்றம்',
  tab_pharmacy: 'மருந்தகம்',
  tab_analytics: 'பகுப்பாய்வு',
  refresh: 'புதுப்பி',
  sign_out: 'வெளியேறு',
  language: 'மொழி',

  pending_prescriptions: 'நிலுவையில் உள்ள மருந்துச் சீட்டுகள்',
  no_pending_prescriptions: 'நிலுவையில் மருந்துச் சீட்டுகள் இல்லை.',
  diagnosis_label: 'நோய் கண்டறிதல்:',
  medicines_label: 'மருந்துகள்:',
  no_medicines_listed: 'மருந்துகள் பட்டியலிடப்படவில்லை',
  interaction_warning: 'மருந்து இடைவினை எச்சரிக்கை',
  dismiss: 'நிராகரி',

  expiry_alerts: 'காலாவதி எச்சரிக்கைகள் (அடுத்த 90 நாட்கள்)',
  nothing_expiring: 'விரைவில் காலாவதியாகும் மருந்துகள் இல்லை.',
  batch_recall_alerts: 'தொகுதி திரும்பப்பெறல் எச்சரிக்கைகள்',
  no_recalls: 'உங்கள் இருப்பைப் பாதிக்கும் திரும்பப்பெறல்கள் இல்லை.',
  preorders: 'முன்பதிவுகள்',
  no_preorders: 'நிலுவையில் முன்பதிவுகள் இல்லை.',
  mark_ready: 'தயார் எனக் குறி',
  low_stock_alerts: 'குறைந்த இருப்பு எச்சரிக்கைகள்',

  inventory: 'இருப்பு',
  medicine: 'மருந்து',
  stock: 'இருப்பு',
  status: 'நிலை',
  actions: 'செயல்கள்',
  out_of_stock: 'இருப்பில் இல்லை',
  low_stock: 'குறைந்த இருப்பு',
  stock_optimal: 'போதுமானது',
  new_medicine_name: 'புதிய மருந்தின் பெயர்',
  add_medicine_placeholder: 'மருந்தைச் சேர் (எ.கா. டோலோ 650)',
  starting_stock_count: 'தொடக்க இருப்பு எண்ணிக்கை',
  count: 'எண்ணிக்கை',
  add_medicine: 'மருந்தைச் சேர்',
  sold_one: '1 விற்பனை (தட்டினால் குறையும்)',
  shipment_plus_ten: 'சரக்கு +10',
  set_counted_stock: 'எண்ணப்பட்ட இருப்பை அமை',
  enter_counted_stock: 'எண்ணப்பட்ட இருப்பை உள்ளிடவும் (நாள் இறுதி எண்ணிக்கை):',
  invalid_stock_number: 'சரியான எதிர்மறையற்ற எண்ணை உள்ளிடவும்.',
  action_failed: 'செயல் தோல்வியடைந்தது',
  fulfill_auto_deduct: 'நிறைவேற்று (இருப்பு தானாகக் குறையும்)',

  medicine_information: 'மருந்து தகவல்',
  close_medicine_info: 'மருந்து தகவலை மூடு',
  loading_ellipsis: 'ஏற்றுகிறது…',
  what_its_for: 'எதற்காகப் பயன்படுகிறது',
  dosage_guidance: 'அளவு வழிகாட்டுதல்',
  side_effects: 'கவனிக்க வேண்டிய பக்க விளைவுகள்',
  precautions: 'முன்னெச்சரிக்கைகள்',
  medicine_info_failed: 'மருந்து தகவலை ஏற்ற முடியவில்லை.',

  no_medicines_recognized: 'இந்த விலைப்பட்டியலில் மருந்துகள் அடையாளம் காணப்படவில்லை.',
  invoice_read_failed: 'விலைப்பட்டியல் படத்தைப் படிக்க முடியவில்லை.',
  some_items_failed: 'சில பொருட்களைச் சேர்க்க முடியவில்லை — இருப்புப் பட்டியலைச் சரிபார்க்கவும்.',

  pharmacy_data_failed:
    'மருந்தகத் தரவை ஏற்ற முடியவில்லை. உங்கள் இணைப்பைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.',

  loading_community_intelligence: 'சமூக நுண்ணறிவு ஏற்றப்படுகிறது...',
  triage_assessments_7d: 'முதன்மை மதிப்பீடுகள் (7 நாட்கள்)',
  active_sos_alerts: 'செயலில் உள்ள SOS எச்சரிக்கைகள்',
  pending_prescriptions_stat: 'நிலுவையில் உள்ள மருந்துச் சீட்டுகள்',
  registered_pharmacies: 'பதிவுசெய்யப்பட்ட மருந்தகங்கள்',
  no_outbreak_clusters: 'சமீபத்தில் நோய்ப் பரவல் கொத்துகள் கண்டறியப்படவில்லை.',
  no_resource_shortages: 'இந்த நேரத்தில் வளப் பற்றாக்குறை எதுவும் கணிக்கப்படவில்லை.',
  analytics_failed: 'சமூக சுகாதார நுண்ணறிவுத் தரவை ஏற்ற முடியவில்லை.',
  community_health_intelligence: 'சமூக சுகாதார நுண்ணறிவு',
  outbreak_heatmap: 'பகுதிவாரி நோய்ப் பரவல் வரைபடம்',
  outbreak_heatmap_blurb: 'AI கண்டறிந்த அறிகுறி கொத்துகள், ஏற்படக்கூடிய நோய்ப் பரவலைக் காட்டுகின்றன.',
  avg_severity: 'சராசரி தீவிரம்:',
  resource_forecast: 'வள ஒதுக்கீட்டு முன்னறிவிப்பு',
  resource_forecast_blurb: 'மருந்துகள் மற்றும் அவசர சேவைகளுக்கான கணிப்பு பகுப்பாய்வு.',

  something_went_wrong: 'ஏதோ தவறு நடந்துவிட்டது',
  crash_body: 'இந்த டாஷ்போர்டில் எதிர்பாராத பிழை ஏற்பட்டது. உங்கள் இருப்புத் தரவு பாதுகாப்பாக உள்ளது — மீண்டும் ஏற்றி முயற்சிக்கவும்.',
  reload: 'மீண்டும் ஏற்று',
};

const TABLES: Record<LocaleCode, Record<string, string>> = { en, ta };

interface LocaleContextType {
  code: LocaleCode;
  setCode: (code: LocaleCode) => void;
  t: (key: string) => string;
}

const LocaleContext = createContext<LocaleContextType>({
  code: 'en',
  setCode: () => {},
  t: (key: string) => key,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [code, setCodeState] = useState<LocaleCode>('en');

  useEffect(() => {
    try {
      const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
      if (stored === 'en' || stored === 'ta') setCodeState(stored);
    } catch {
      // Private-window storage throws; English is the safe default.
    }
  }, []);

  const setCode = useCallback((next: LocaleCode) => {
    setCodeState(next);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // Not persisting is survivable; the session still switches.
    }
  }, []);

  // Falling back through English means a key added to `en` but not yet
  // translated shows English rather than the raw key.
  const t = useCallback((key: string) => TABLES[code][key] ?? en[key] ?? key, [code]);

  return <LocaleContext.Provider value={{ code, setCode, t }}>{children}</LocaleContext.Provider>;
}

export const useLocale = () => useContext(LocaleContext);
