"use client";

// Lightweight English/Tamil localization, mirroring the pattern already
// proven out in apps/mobile_app/lib/services/app_strings.dart (and
// doctor_mobile_app/pharmacy_mobile_app): a plain key->string table per
// language rather than a full i18n library + codegen pipeline, so strings
// stay fully source-controlled and reviewable by a Tamil speaker in one
// file. web_portal had zero localization despite Tamil being the planning
// doc's launch-language requirement — this was the actual gap, not the
// mobile apps (which already have it).
//
// Scope: infrastructure + the login/register page, the first screen every
// user sees and where "we said we support this" mattered most. Extending
// `t()` calls to more pages is a mechanical, page-by-page continuation of
// this same pattern.

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

export type LocaleCode = 'en' | 'ta';

interface LocaleContextType {
  code: LocaleCode;
  setCode: (code: LocaleCode) => void;
  t: (key: string) => string;
}

const STORAGE_KEY = 'gramcare_locale';

const en: Record<string, string> = {
  app_title: 'GramCare AI',
  sign_in_tagline: 'Sign in to continue your care journey.',
  create_account_tagline: 'Create your account.',
  sign_in: 'Sign In',
  register: 'Register',
  username: 'Username',
  full_name: 'Full Name',
  email: 'Email',
  password: 'Password',
  min_8_chars: 'Minimum 8 characters.',
  i_am_a: 'I am a...',
  patient: 'Patient',
  doctor: 'Doctor',
  hospital: 'Hospital',
  pharmacists_labs_note: 'Pharmacists and Labs have separate portals.',
  phone_number_optional: 'Phone Number (Optional)',
  phone_reminder_note: "So we can text you a reminder before appointments. You can skip this and add it later.",
  create_account: 'Create Account',
  please_wait: 'Please wait...',
  government_official_prompt: 'Government & health-authority official?',
  portal_access: 'Portal access',
  language: 'Language',
  // Header nav — renders on every page, so this is the highest-leverage
  // place to extend coverage beyond the login screen (see the note at the
  // top of this file: extending t() elsewhere is a mechanical, page-by-
  // page continuation, not a re-architecture).
  nav_book_consultation: 'Book Consultation',
  nav_family_profiles: 'Family Profiles',
  nav_my_prescriptions: 'My Prescriptions',
  nav_find_medicine: 'Find Medicine',
  nav_health_passport: 'Health Passport',
  nav_doctor_dashboard: 'Doctor Dashboard',
  nav_my_profile: 'My Profile',
  nav_emergency_desk: 'Emergency Desk',
  nav_health_intelligence: 'Health Intelligence',
  nav_hospital_profile: 'Hospital Profile',
  nav_my_devices: 'My Devices',
  sign_out: 'Sign Out',
  role_patient: 'Patient',
  role_doctor: 'Doctor',
  role_hospital: 'Hospital',
  role_pharmacist: 'Pharmacist',
  role_lab: 'Lab',
  role_admin: 'Government',
  // Homepage hero + AI Symptom Checker — the first content-bearing view a
  // signed-in patient lands on, right after the login screen.
  home_tagline: 'The ultimate hybrid healthcare ecosystem.',
  home_live: 'Live',
  home_offline: 'Offline',
  symptom_checker_title: 'AI Symptom Checker',
  symptom_checker_placeholder: 'Describe your symptoms (e.g. fever, headache, cough)...',
  add_symptom_photo: 'Add a photo of the symptom (optional)',
  analyze_with_ai: 'Analyze with AI',
  ai_thinking: 'AI is thinking…',
};

const ta: Record<string, string> = {
  app_title: 'கிராம்கேர் AI',
  sign_in_tagline: 'உங்கள் சிகிச்சைப் பயணத்தைத் தொடர உள்நுழையவும்.',
  create_account_tagline: 'உங்கள் கணக்கை உருவாக்கவும்.',
  sign_in: 'உள்நுழைக',
  register: 'பதிவு செய்க',
  username: 'பயனர்பெயர்',
  full_name: 'முழுப் பெயர்',
  email: 'மின்னஞ்சல்',
  password: 'கடவுச்சொல்',
  min_8_chars: 'குறைந்தது 8 எழுத்துகள்.',
  i_am_a: 'நான் ஒரு...',
  patient: 'நோயாளி',
  doctor: 'மருத்துவர்',
  hospital: 'மருத்துவமனை',
  pharmacists_labs_note: 'மருந்தகங்கள் மற்றும் ஆய்வகங்களுக்கு தனி போர்ட்டல் உள்ளது.',
  phone_number_optional: 'தொலைபேசி எண் (விருப்பத்திற்குரியது)',
  phone_reminder_note: 'அப்பாயின்ட்மென்ட்டுக்கு முன் உங்களுக்கு நினைவூட்டல் SMS அனுப்ப. இதைத் தவிர்த்து பின்னர் சேர்க்கலாம்.',
  create_account: 'கணக்கை உருவாக்கு',
  please_wait: 'தயவுசெய்து காத்திருக்கவும்...',
  government_official_prompt: 'அரசு அல்லது சுகாதார அதிகாரியா?',
  portal_access: 'போர்ட்டல் அணுகல்',
  language: 'மொழி',
  nav_book_consultation: 'ஆலோசனை பதிவு',
  nav_family_profiles: 'குடும்ப சுயவிவரங்கள்',
  nav_my_prescriptions: 'எனது மருந்துச் சீட்டுகள்',
  nav_find_medicine: 'மருந்து தேடு',
  nav_health_passport: 'சுகாதார பாஸ்போர்ட்',
  nav_doctor_dashboard: 'மருத்துவர் டாஷ்போர்டு',
  nav_my_profile: 'எனது சுயவிவரம்',
  nav_emergency_desk: 'அவசர உதவி மையம்',
  nav_health_intelligence: 'சுகாதார நுண்ணறிவு',
  nav_hospital_profile: 'மருத்துவமனை சுயவிவரம்',
  nav_my_devices: 'எனது சாதனங்கள்',
  sign_out: 'வெளியேறு',
  role_patient: 'நோயாளி',
  role_doctor: 'மருத்துவர்',
  role_hospital: 'மருத்துவமனை',
  role_pharmacist: 'மருந்தாளர்',
  role_lab: 'ஆய்வகம்',
  role_admin: 'அரசு',
  home_tagline: 'இறுதி கலப்பின சுகாதார சூழல் அமைப்பு.',
  home_live: 'நேரடி',
  home_offline: 'இணைப்பு இல்லை',
  symptom_checker_title: 'AI அறிகுறி சரிபார்ப்பு',
  symptom_checker_placeholder: 'உங்கள் அறிகுறிகளை விவரிக்கவும் (எ.கா. காய்ச்சல், தலைவலி, இருமல்)...',
  add_symptom_photo: 'அறிகுறியின் புகைப்படத்தைச் சேர்க்கவும் (விருப்பத்திற்குரியது)',
  analyze_with_ai: 'AI மூலம் பகுப்பாய்வு செய்யவும்',
  ai_thinking: 'AI யோசித்துக் கொண்டிருக்கிறது…',
};

const TABLES: Record<LocaleCode, Record<string, string>> = { en, ta };

const LocaleContext = createContext<LocaleContextType>({
  code: 'en',
  setCode: () => {},
  t: (key: string) => key,
});

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [code, setCodeState] = useState<LocaleCode>('en');

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'ta') setCodeState(stored);
  }, []);

  const setCode = useCallback((next: LocaleCode) => {
    setCodeState(next);
    localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const t = useCallback(
    (key: string) => TABLES[code][key] ?? en[key] ?? key,
    [code]
  );

  return (
    <LocaleContext.Provider value={{ code, setCode, t }}>
      {children}
    </LocaleContext.Provider>
  );
}

export const useLocale = () => useContext(LocaleContext);
