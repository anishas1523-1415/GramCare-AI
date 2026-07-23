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
  waking_server_note: 'Still working — the server may be waking up after being idle. This can take up to a minute on the first try.',
  network_error: "Couldn't reach the server. Check your connection and try again in a moment.",
  government_official_prompt: 'Government & health-authority official?',
  portal_access: 'Portal access',
  language: 'Language',
  // Header nav — renders on every page, so this is the highest-leverage
  // place to extend coverage beyond the login screen (see the note at the
  // top of this file: extending t() elsewhere is a mechanical, page-by-
  // page continuation, not a re-architecture).
  nav_sos: 'Emergency SOS',
  nav_my_care: 'My Care',
  nav_book_consultation: 'Book Consultation',
  nav_my_appointments: 'My Appointments',
  nav_family_profiles: 'Family Profiles',
  nav_my_prescriptions: 'My Prescriptions',
  nav_find_medicine: 'Find Medicine',
  nav_lab_tests: 'Lab Tests',
  nav_preventive_care: 'Preventive Care',
  nav_referrals: 'Referrals',
  nav_patient_directory: 'Patient Directory',
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
  nav_symptom_checker: 'AI Symptom Check',
  symptom_checker_page_subtitle: "Describe what you're feeling — our AI gives an instant severity assessment and points you to the right specialist.",
  back_to_home: 'Back to Home',
  // Homepage redesign: the landing view is now a branding/feature showcase
  // rather than the AI Symptom Checker + Doctor Portal Feed (that checker
  // moved to its own /symptom-checker page; the doctor feed was a duplicate
  // of the live feed already on the doctor dashboard).
  home_hero_cta_primary_guest: 'Get Started',
  home_hero_cta_primary_user: 'Book a Consultation',
  home_hero_cta_secondary: 'Try AI Symptom Check',
  home_badge_secure: 'End-to-end Secure',
  home_badge_offline: 'Built for Low Bandwidth',
  home_badge_bilingual: 'English / தமிழ்',
  home_badge_triage: '24/7 AI Triage',
  home_features_eyebrow: 'What makes GramCare AI different',
  home_features_heading: 'One app for every step of care',
  home_features_subheading: 'From the first symptom to the pharmacy counter — built for real villages, real clinics, real emergencies.',
  home_feat_triage_title: 'AI Symptom Triage',
  home_feat_triage_desc: 'Describe symptoms in your own words, or attach a photo, and get an instant AI severity assessment in English or Tamil.',
  home_feat_passport_title: 'Digital Health Passport',
  home_feat_passport_desc: 'One QR code carries blood group, allergies, and medicines to any hospital — no login, works even offline.',
  home_feat_family_title: 'Family Health Profiles',
  home_feat_family_desc: 'Manage records for your whole family — parents, children, elders — from a single account.',
  home_feat_doctor_title: 'Verified Doctor Network',
  home_feat_doctor_desc: 'Book real doctors, video-consult, and get prescriptions synced instantly to nearby pharmacies.',
  home_feat_sos_title: 'One-Tap SOS Escalation',
  home_feat_sos_desc: 'Alerts the nearest hospital and your emergency contacts instantly with your location and health passport.',
  home_feat_sms_title: 'SMS Reminders, No App Needed',
  home_feat_sms_desc: 'Appointment reminders reach any phone by SMS — no smartphone or data connection required.',
  home_feat_lang_title: 'Built for Bharat',
  home_feat_lang_desc: 'Multilingual from day one — English and Tamil now, more languages on the way.',
  home_feat_free_title: 'Free While We Build',
  home_feat_free_desc: "Every feature is free during testing with real village clinics — we won't lock out care to upgrade later.",
  home_mission_heading: 'Our mission',
  home_mission_body: 'GramCare AI exists to put hospital-grade triage, records, and care coordination into the hands of every village — not just the cities.',
  home_carousel_prev: 'Previous feature',
  home_carousel_next: 'Next feature',
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
  waking_server_note: 'இன்னும் முயற்சி நடக்கிறது — சேவையகம் சற்று நேரம் செயலற்று இருந்திருக்கலாம். முதல் முயற்சிக்கு ஒரு நிமிடம் வரை ஆகலாம்.',
  network_error: 'சேவையகத்தை அணுக முடியவில்லை. உங்கள் இணைப்பைச் சரிபார்த்து சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும்.',
  government_official_prompt: 'அரசு அல்லது சுகாதார அதிகாரியா?',
  portal_access: 'போர்ட்டல் அணுகல்',
  language: 'மொழி',
  nav_sos: 'அவசர SOS',
  nav_my_care: 'என் பராமரிப்பு',
  nav_book_consultation: 'ஆலோசனை பதிவு',
  nav_my_appointments: 'எனது அப்பாயின்ட்மென்ட்கள்',
  nav_family_profiles: 'குடும்ப சுயவிவரங்கள்',
  nav_my_prescriptions: 'எனது மருந்துச் சீட்டுகள்',
  nav_find_medicine: 'மருந்து தேடு',
  nav_lab_tests: 'ஆய்வக பரிசோதனைகள்',
  nav_preventive_care: 'முன்னெச்சரிக்கை பராமரிப்பு',
  nav_referrals: 'பரிந்துரைகள்',
  nav_patient_directory: 'நோயாளர் அடைவு',
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
  nav_symptom_checker: 'AI அறிகுறி பரிசோதனை',
  symptom_checker_page_subtitle: 'நீங்கள் உணர்வதை விவரிக்கவும் — எங்கள் AI உடனடி தீவிரத்தன்மை மதிப்பீட்டை வழங்கி சரியான நிபுணரிடம் வழிநடத்தும்.',
  back_to_home: 'முகப்புக்குத் திரும்பு',
  home_hero_cta_primary_guest: 'தொடங்குங்கள்',
  home_hero_cta_primary_user: 'ஆலோசனை பதிவு செய்க',
  home_hero_cta_secondary: 'AI அறிகுறி பரிசோதனையை முயற்சிக்கவும்',
  home_badge_secure: 'இறுதி முதல் இறுதி வரை பாதுகாப்பு',
  home_badge_offline: 'குறைந்த இணைய வேகத்திற்கு ஏற்றது',
  home_badge_bilingual: 'English / தமிழ்',
  home_badge_triage: '24/7 AI பரிசோதனை',
  home_features_eyebrow: 'GramCare AI ஐ வேறுபடுத்துவது என்ன',
  home_features_heading: 'சிகிச்சையின் ஒவ்வொரு கட்டத்திற்கும் ஒரே செயலி',
  home_features_subheading: 'முதல் அறிகுறியிலிருந்து மருந்தகக் கவுண்டர் வரை — உண்மையான கிராமங்களுக்காக, உண்மையான மருத்துவமனைகளுக்காக, உண்மையான அவசரநிலைகளுக்காக வடிவமைக்கப்பட்டது.',
  home_feat_triage_title: 'AI அறிகுறி பரிசோதனை',
  home_feat_triage_desc: 'உங்கள் சொந்த வார்த்தைகளில் அறிகுறிகளை விவரிக்கவும், அல்லது புகைப்படம் இணைக்கவும் — உடனடி AI தீவிரத்தன்மை மதிப்பீடு தமிழிலும் ஆங்கிலத்திலும் கிடைக்கும்.',
  home_feat_passport_title: 'டிஜிட்டல் சுகாதார பாஸ்போர்ட்',
  home_feat_passport_desc: 'ஒரே QR குறியீடு இரத்த வகை, ஒவ்வாமைகள், மருந்துகளை எந்த மருத்துவமனைக்கும் கொண்டு செல்கிறது — உள்நுழைவு தேவையில்லை, இணைப்பு இல்லாமலும் வேலை செய்யும்.',
  home_feat_family_title: 'குடும்ப சுகாதார சுயவிவரங்கள்',
  home_feat_family_desc: 'பெற்றோர், குழந்தைகள், முதியோர் — உங்கள் முழு குடும்பத்தின் பதிவுகளையும் ஒரே கணக்கில் நிர்வகிக்கவும்.',
  home_feat_doctor_title: 'சரிபார்க்கப்பட்ட மருத்துவர் வலையமைப்பு',
  home_feat_doctor_desc: 'உண்மையான மருத்துவர்களை பதிவு செய்யவும், வீடியோ ஆலோசனை பெறவும், மருந்துச் சீட்டுகள் அருகிலுள்ள மருந்தகங்களுக்கு உடனடியாக அனுப்பப்படும்.',
  home_feat_sos_title: 'ஒரே தட்டலில் SOS அவசரநிலை',
  home_feat_sos_desc: 'உங்கள் இருப்பிடம் மற்றும் சுகாதார பாஸ்போர்ட்டுடன் அருகிலுள்ள மருத்துவமனை மற்றும் அவசர தொடர்புகளுக்கு உடனடியாக எச்சரிக்கை அனுப்பும்.',
  home_feat_sms_title: 'SMS நினைவூட்டல்கள், செயலி தேவையில்லை',
  home_feat_sms_desc: 'ஸ்மார்ட்போன் அல்லது இணையம் இல்லாமலே எந்த மொபைலுக்கும் SMS மூலம் அப்பாயின்ட்மென்ட் நினைவூட்டல்கள் வரும்.',
  home_feat_lang_title: 'பாரதத்திற்காக வடிவமைக்கப்பட்டது',
  home_feat_lang_desc: 'தொடக்கத்திலிருந்தே பன்மொழி ஆதரவு — இப்போது ஆங்கிலம் மற்றும் தமிழ், மேலும் மொழிகள் விரைவில்.',
  home_feat_free_title: 'நாங்கள் உருவாக்கும் வரை இலவசம்',
  home_feat_free_desc: 'உண்மையான கிராம மருத்துவமனைகளுடன் சோதனை செய்யும் போது அனைத்து அம்சங்களும் இலவசம் — பராமரிப்பை நாங்கள் தடுக்க மாட்டோம்.',
  home_mission_heading: 'எங்கள் நோக்கம்',
  home_mission_body: 'மருத்துவமனை தரமான பரிசோதனை, பதிவுகள் மற்றும் பராமரிப்பு ஒருங்கிணைப்பை நகரங்களுக்கு மட்டுமல்ல, ஒவ்வொரு கிராமத்திற்கும் கொண்டு செல்வதே GramCare AI இன் நோக்கம்.',
  home_carousel_prev: 'முந்தைய அம்சம்',
  home_carousel_next: 'அடுத்த அம்சம்',
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
