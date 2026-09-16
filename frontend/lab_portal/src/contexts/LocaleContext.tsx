"use client";

// English/Tamil strings for the lab portal — the last surface in the
// product that was English-only. Same shape as the patient portal's
// LocaleContext, the pharmacist portal's, and the mobile apps'
// app_strings.dart: a plain key -> string table per language, reviewable by
// a Tamil speaker in one file without a toolchain.

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

export type LocaleCode = 'en' | 'ta';

// Exported for global-error.tsx, which replaces the root layout and so
// renders outside this provider.
export const LOCALE_STORAGE_KEY = 'gramcare_lab_locale';

const en: Record<string, string> = {
  // Shell
  lab_portal: 'GramCare Lab',
  booking_queue: 'Booking Queue',
  test_catalog: 'Test Catalog',
  profile: 'Profile',
  logout: 'Logout',
  language: 'Language',
  loading_portal: 'Loading GramCare Lab Portal…',

  // Login
  sign_in: 'Sign In',
  register: 'Register',
  email: 'Email',
  lab_contact_name: 'Lab / Contact Name',
  password: 'Password',
  forgot_password: 'Forgot password?',
  reset_link_sent: 'If that email has an account, a password reset link is on its way.',
  lab_accounts_only: 'This portal is for registered Laboratory accounts only.',
  login_blurb: 'Sign in to your laboratory portal.',
  register_blurb: 'Register your diagnostic center.',
  forgot_blurb: "Enter your account email and we'll send a reset link.",
  username_or_email: 'Username or Email',
  username: 'Username',
  please_wait: 'Please wait...',
  create_lab_account: 'Create Lab Account',
  send_reset_link: 'Send Reset Link',
  back_to_sign_in: '← Back to sign in',
  invalid_credentials: 'Invalid username or password.',
  reset_link_failed: 'Could not send the reset link. Please try again.',
  registration_failed: 'Registration failed. Please check your details and try again.',
  saving: 'Saving…',
  save_and_continue: 'Save & Continue',

  // Onboarding
  set_up_your_lab: 'Set Up Your Lab',
  onboarding_blurb: 'One-time setup so patients can find and book tests at your center.',
  lab_name: 'Lab Name',
  address: 'Address',
  phone: 'Phone',
  latitude: 'Latitude',
  longitude: 'Longitude',
  use_my_location: 'Use my current location',
  offers_home_collection: 'We offer home sample collection',
  location_failed: 'Could not access location — enter it manually or skip.',

  // Dashboard
  loading_queue: 'Loading booking queue…',
  refresh: 'Refresh',
  no_bookings: 'No bookings need action right now.',
  enter_report: 'Enter Report',
  cancel_booking: 'Cancel booking',
  queue_load_failed: 'Could not load the booking queue.',
  updated_at: 'Updated',
  patient_hash: 'Patient',
  home_sample_collection: 'Home sample collection',
  in_center_visit: 'In-center visit',
  updating: 'Updating…',
  status_booked: 'Booked',
  status_sample_collected: 'Sample Collected',
  status_processing: 'Processing',
  status_report_ready: 'Report Ready',
  status_completed: 'Completed',
  status_cancelled: 'Cancelled',
  action_mark_collected: 'Mark Sample Collected',
  action_start_processing: 'Start Processing',
  turnaround_suffix: 'h turnaround',

  // Catalog
  catalog_blurb: 'Look up prep instructions for any test.',
  searching: 'Searching…',
  no_matching_tests: 'No matching tests.',
  search_tests_placeholder: 'Search by test name or category…',

  // Report entry
  report_submitted: 'Report Submitted',
  back_to_queue: 'Back to Queue',
  add_parameter: 'Add parameter',
  summary_optional: 'Summary (optional)',
  parameter_placeholder: 'Parameter (e.g. Hemoglobin)',
  value: 'Value',
  unit: 'Unit',
  reference_range: 'Reference range',
  summary_placeholder: 'e.g. All values within normal range.',
  report_submit_failed: 'Could not submit the report. Please try again.',
  report_synced_note: 'result has synced automatically into the patient\u2019s Family Health Wallet, and they have been notified.',
  enter_report_for: 'Enter Report —',
  booking_hash: 'Booking',
  submitting: 'Submitting…',
  submit_report: 'Submit Report',

  // Profile
  loading_profile: 'Loading profile…',
  lab_profile: 'Lab Profile',
  name: 'Name',
  signed_in_as: 'Signed in as',

  // Errors
  something_went_wrong: 'Something went wrong',
  try_again: 'Try again',
  dashboard: 'Dashboard',
  error_page_body: 'This page hit an unexpected error. Your booking and report data is safe — try again.',
  critical_error_title: 'GramCare Lab Portal hit a critical error',
  critical_error_body: 'Please reload the app.',
  reload: 'Reload',
  offers_home_collection_label: 'Offers home sample collection',
  in_center_only: 'In-center only',
  active: 'Active',
  inactive: 'Inactive',
  page_not_found: 'Page not found',
  not_found_body: "The page you're looking for doesn't exist or has moved.",
  back_to_dashboard: 'Back to Dashboard',
};

const ta: Record<string, string> = {
  lab_portal: 'GramCare ஆய்வகம்',
  booking_queue: 'முன்பதிவு வரிசை',
  test_catalog: 'பரிசோதனைப் பட்டியல்',
  profile: 'சுயவிவரம்',
  logout: 'வெளியேறு',
  language: 'மொழி',
  loading_portal: 'GramCare ஆய்வகப் போர்டல் ஏற்றப்படுகிறது…',

  sign_in: 'உள்நுழை',
  register: 'பதிவு செய்',
  email: 'மின்னஞ்சல்',
  lab_contact_name: 'ஆய்வகம் / தொடர்பு பெயர்',
  password: 'கடவுச்சொல்',
  forgot_password: 'கடவுச்சொல் மறந்துவிட்டதா?',
  reset_link_sent:
    'அந்த மின்னஞ்சலுக்குக் கணக்கு இருந்தால், கடவுச்சொல் மீட்டமைப்பு இணைப்பு அனுப்பப்படும்.',
  lab_accounts_only: 'இந்தப் போர்டல் பதிவுசெய்யப்பட்ட ஆய்வகக் கணக்குகளுக்கு மட்டுமே.',
  login_blurb: 'உங்கள் ஆய்வகப் போர்டலில் உள்நுழையவும்.',
  register_blurb: 'உங்கள் நோயறிதல் மையத்தைப் பதிவு செய்யவும்.',
  forgot_blurb: 'உங்கள் கணக்கு மின்னஞ்சலை உள்ளிடவும், மீட்டமைப்பு இணைப்பை அனுப்புகிறோம்.',
  username_or_email: 'பயனர் பெயர் அல்லது மின்னஞ்சல்',
  username: 'பயனர் பெயர்',
  please_wait: 'காத்திருக்கவும்...',
  create_lab_account: 'ஆய்வகக் கணக்கை உருவாக்கு',
  send_reset_link: 'மீட்டமைப்பு இணைப்பை அனுப்பு',
  back_to_sign_in: '← உள்நுழைவுக்குத் திரும்பு',
  invalid_credentials: 'தவறான பயனர் பெயர் அல்லது கடவுச்சொல்.',
  reset_link_failed: 'மீட்டமைப்பு இணைப்பை அனுப்ப முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
  registration_failed: 'பதிவு தோல்வியடைந்தது. உங்கள் விவரங்களைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.',
  saving: 'சேமிக்கிறது…',
  save_and_continue: 'சேமித்துத் தொடர்',

  set_up_your_lab: 'உங்கள் ஆய்வகத்தை அமைக்கவும்',
  onboarding_blurb:
    'ஒரு முறை அமைப்பு — இதன் மூலம் நோயாளிகள் உங்கள் மையத்தைக் கண்டறிந்து பரிசோதனைகளை முன்பதிவு செய்யலாம்.',
  lab_name: 'ஆய்வகப் பெயர்',
  address: 'முகவரி',
  phone: 'தொலைபேசி',
  latitude: 'அட்சரேகை',
  longitude: 'தீர்க்கரேகை',
  use_my_location: 'எனது தற்போதைய இருப்பிடத்தைப் பயன்படுத்து',
  offers_home_collection: 'நாங்கள் வீட்டிலேயே மாதிரி சேகரிப்பு வழங்குகிறோம்',
  location_failed: 'இருப்பிடத்தை அணுக முடியவில்லை — கைமுறையாக உள்ளிடவும் அல்லது தவிர்க்கவும்.',

  loading_queue: 'முன்பதிவு வரிசை ஏற்றப்படுகிறது…',
  refresh: 'புதுப்பி',
  no_bookings: 'இப்போது நடவடிக்கை தேவைப்படும் முன்பதிவுகள் இல்லை.',
  enter_report: 'அறிக்கையை உள்ளிடு',
  cancel_booking: 'முன்பதிவை ரத்து செய்',
  queue_load_failed: 'முன்பதிவு வரிசையை ஏற்ற முடியவில்லை.',
  updated_at: 'புதுப்பிக்கப்பட்டது',
  patient_hash: 'நோயாளி',
  home_sample_collection: 'வீட்டில் மாதிரி சேகரிப்பு',
  in_center_visit: 'மையத்திற்கு வருகை',
  updating: 'புதுப்பிக்கிறது…',
  status_booked: 'முன்பதிவு செய்யப்பட்டது',
  status_sample_collected: 'மாதிரி சேகரிக்கப்பட்டது',
  status_processing: 'பரிசோதனையில்',
  status_report_ready: 'அறிக்கை தயார்',
  status_completed: 'நிறைவடைந்தது',
  status_cancelled: 'ரத்து செய்யப்பட்டது',
  action_mark_collected: 'மாதிரி சேகரிக்கப்பட்டதாகக் குறி',
  action_start_processing: 'பரிசோதனையைத் தொடங்கு',
  turnaround_suffix: 'மணி நேரத்தில் முடிவு',

  catalog_blurb: 'எந்தப் பரிசோதனைக்கும் தயாரிப்பு வழிமுறைகளைத் தேடுங்கள்.',
  searching: 'தேடுகிறது…',
  no_matching_tests: 'பொருந்தும் பரிசோதனைகள் இல்லை.',
  search_tests_placeholder: 'பரிசோதனைப் பெயர் அல்லது வகை மூலம் தேடவும்…',

  report_submitted: 'அறிக்கை சமர்ப்பிக்கப்பட்டது',
  back_to_queue: 'வரிசைக்குத் திரும்பு',
  add_parameter: 'அளவுருவைச் சேர்',
  summary_optional: 'சுருக்கம் (விருப்பத்திற்குரியது)',
  parameter_placeholder: 'அளவுரு (எ.கா. ஹீமோகுளோபின்)',
  value: 'மதிப்பு',
  unit: 'அலகு',
  reference_range: 'குறிப்பு வரம்பு',
  summary_placeholder: 'எ.கா. அனைத்து மதிப்புகளும் இயல்பான வரம்பிற்குள் உள்ளன.',
  report_submit_failed: 'அறிக்கையைச் சமர்ப்பிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
  report_synced_note: 'முடிவு நோயாளியின் குடும்ப சுகாதாரப் பணப்பையில் தானாகவே ஒத்திசைக்கப்பட்டது; அவர்களுக்குத் தெரிவிக்கப்பட்டுள்ளது.',
  enter_report_for: 'அறிக்கையை உள்ளிடு —',
  booking_hash: 'முன்பதிவு',
  submitting: 'சமர்ப்பிக்கிறது…',
  submit_report: 'அறிக்கையைச் சமர்ப்பி',

  loading_profile: 'சுயவிவரம் ஏற்றப்படுகிறது…',
  lab_profile: 'ஆய்வக சுயவிவரம்',
  name: 'பெயர்',
  signed_in_as: 'உள்நுழைந்துள்ளவர்',

  something_went_wrong: 'ஏதோ தவறு நடந்துவிட்டது',
  try_again: 'மீண்டும் முயற்சிக்கவும்',
  dashboard: 'டாஷ்போர்டு',
  error_page_body: 'இந்தப் பக்கத்தில் எதிர்பாராத பிழை ஏற்பட்டது. உங்கள் முன்பதிவு மற்றும் அறிக்கைத் தரவு பாதுகாப்பாக உள்ளது — மீண்டும் முயற்சிக்கவும்.',
  critical_error_title: 'GramCare ஆய்வகப் போர்டலில் கடுமையான பிழை ஏற்பட்டது',
  critical_error_body: 'செயலியை மீண்டும் ஏற்றவும்.',
  reload: 'மீண்டும் ஏற்று',
  offers_home_collection_label: 'வீட்டிலேயே மாதிரி சேகரிப்பு வழங்கப்படுகிறது',
  in_center_only: 'மையத்தில் மட்டும்',
  active: 'செயலில்',
  inactive: 'செயலில் இல்லை',
  page_not_found: 'பக்கம் கிடைக்கவில்லை',
  not_found_body: 'நீங்கள் தேடும் பக்கம் இல்லை அல்லது இடம் மாற்றப்பட்டுள்ளது.',
  back_to_dashboard: 'டாஷ்போர்டுக்குத் திரும்பு',
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
