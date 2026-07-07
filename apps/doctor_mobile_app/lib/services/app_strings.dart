import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Lightweight English/Tamil localization — same approach as
/// apps/mobile_app's LocaleService (plain map instead of ARB codegen, so
/// `flutter analyze` stays clean on a fresh checkout with no generation
/// step). Doctors default to English (professional/clinical tool used
/// alongside the web portal), but many doctors in Tamil Nadu will prefer
/// Tamil, so the toggle is first-class exactly like the patient app.
class LocaleService extends ChangeNotifier {
  static const _key = 'gramcare_doctor_locale';
  String _code = 'en';

  String get code => _code;
  bool get isTamil => _code == 'ta';

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _code = prefs.getString(_key) ?? 'en';
    notifyListeners();
  }

  Future<void> setCode(String code) async {
    _code = code;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, code);
    notifyListeners();
  }

  String t(String key) {
    final table = _code == 'ta' ? _ta : _en;
    return table[key] ?? _en[key] ?? key;
  }
}

const Map<String, String> _en = {
  'app_title': 'GramCare Doctor',
  'tagline': 'Consult, prescribe and review on the move',
  'login': 'Login',
  'username_hint': 'Username (e.g., doctor1)',
  'password_hint': 'Password',
  'invalid_credentials': 'Invalid credentials. Please try again.',
  'not_a_doctor_account': 'This account is not registered as a Doctor.',
  'login_failed': 'Login failed. Please check your connection and try again.',
  'dashboard': 'Dashboard',
  'appointment_queue': 'Appointment Queue',
  'no_appointments': 'No appointments in your queue right now.',
  'pull_to_refresh': 'Pull down to refresh',
  'status_pending': 'PENDING',
  'status_confirmed': 'CONFIRMED',
  'status_completed': 'COMPLETED',
  'status_cancelled': 'CANCELLED',
  'patient_detail': 'Patient Detail',
  'ai_pre_consult_summary': 'AI Pre-Consult Summary',
  'risk_flag': 'Risk',
  'active_medicines': 'Active Medicines',
  'recent_conditions': 'Recent AI Assessments',
  'latest_vitals': 'Latest Vitals',
  'medical_history': 'Medical History',
  'triage_summary': 'Triage Summary',
  'mark_confirmed': 'Mark Confirmed',
  'mark_completed': 'Mark Completed',
  'cancel_appointment': 'Cancel Appointment',
  'add_notes': 'Add Consultation Notes',
  'consultation_notes': 'Consultation Notes',
  'write_prescription': 'Write Prescription',
  'save_notes': 'Save Notes',
  'notes_saved': 'Consultation notes saved.',
  'no_history': 'No medical history records found.',
  'prescription_writer': 'Prescription Writer',
  'diagnosis': 'Diagnosis',
  'dosage_instructions': 'Dosage Instructions',
  'notes': 'Notes',
  'medicine_name': 'Medicine name',
  'dosage': 'Dosage',
  'frequency': 'Frequency',
  'duration': 'Duration',
  'add_medicine': 'Add medicine',
  'remove': 'Remove',
  'issue_prescription': 'Issue Prescription',
  'prescription_success': 'Prescription issued and synced to the patient\'s Health Wallet and pharmacy queue.',
  'prescription_failed': 'Failed to issue prescription. Please try again.',
  'at_least_one_medicine': 'Add at least one medicine before submitting.',
  'interaction_warning_title': 'Medicine Interaction Warning',
  'my_schedule': 'My Schedule',
  'availability_slots': 'Availability Slots',
  'add_slot': 'Add Slot',
  'start_time': 'Start time',
  'end_time': 'End time',
  'no_slots': 'No upcoming slots published yet.',
  'slot_booked': 'Booked',
  'slot_open': 'Open',
  'delete_slot_confirm': 'Delete this slot?',
  'available_for_consultation': 'Available for consultation',
  'critical_alerts': 'Critical Alerts',
  'no_active_alerts': 'No active emergency alerts right now.',
  'sos_severity': 'Severity',
  'sos_location': 'Location',
  'sos_status': 'Status',
  'refreshing': 'Refreshing…',
  'profile': 'Profile',
  'specialty': 'Specialty',
  'qualifications': 'Qualifications',
  'experience_years': 'Experience (years)',
  'consultation_fee': 'Consultation Fee',
  'languages': 'Languages',
  'logout': 'Logout',
  'language': 'Language',
  'save': 'Save',
  'cancel': 'Cancel',
  'delete': 'Delete',
  'edit_profile': 'Edit Profile',
  'profile_updated': 'Profile updated.',
  'loading': 'Loading…',
  'error_generic': 'Something went wrong. Please try again.',
  'retry': 'Retry',
  'confirm': 'Confirm',
  'view_history': 'View Medical History',
};

const Map<String, String> _ta = {
  'app_title': 'கிராம்கேர் டாக்டர்',
  'tagline': 'நகரும்போதே ஆலோசனை, மருந்துச்சீட்டு, பரிசோதனை',
  'login': 'உள்நுழைக',
  'username_hint': 'பயனர்பெயர் (எ.கா. doctor1)',
  'password_hint': 'கடவுச்சொல்',
  'invalid_credentials': 'தவறான விவரங்கள். மீண்டும் முயற்சிக்கவும்.',
  'not_a_doctor_account': 'இந்தக் கணக்கு டாக்டர் கணக்காக பதிவு செய்யப்படவில்லை.',
  'login_failed': 'உள்நுழைவு தோல்வி. இணைப்பைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.',
  'dashboard': 'டாஷ்போர்டு',
  'appointment_queue': 'அப்பாயின்ட்மென்ட் வரிசை',
  'no_appointments': 'தற்போது உங்கள் வரிசையில் அப்பாயின்ட்மென்ட் இல்லை.',
  'pull_to_refresh': 'புதுப்பிக்க கீழே இழுக்கவும்',
  'status_pending': 'நிலுவையில்',
  'status_confirmed': 'உறுதி செய்யப்பட்டது',
  'status_completed': 'முடிந்தது',
  'status_cancelled': 'ரத்து செய்யப்பட்டது',
  'patient_detail': 'நோயாளி விவரம்',
  'ai_pre_consult_summary': 'AI முன்-ஆலோசனை சுருக்கம்',
  'risk_flag': 'ஆபத்து நிலை',
  'active_medicines': 'தற்போதைய மருந்துகள்',
  'recent_conditions': 'சமீபத்திய AI மதிப்பீடுகள்',
  'latest_vitals': 'சமீபத்திய உடல்நிலை அளவீடுகள்',
  'medical_history': 'மருத்துவ வரலாறு',
  'triage_summary': 'ட்ரையாஜ் சுருக்கம்',
  'mark_confirmed': 'உறுதி செய்யப்பட்டதாகக் குறிக்க',
  'mark_completed': 'முடிந்ததாகக் குறிக்க',
  'cancel_appointment': 'அப்பாயின்ட்மென்ட்டை ரத்து செய்',
  'add_notes': 'ஆலோசனை குறிப்புகளைச் சேர்க்க',
  'consultation_notes': 'ஆலோசனை குறிப்புகள்',
  'write_prescription': 'மருந்துச்சீட்டு எழுத',
  'save_notes': 'குறிப்புகளைச் சேமிக்க',
  'notes_saved': 'ஆலோசனை குறிப்புகள் சேமிக்கப்பட்டன.',
  'no_history': 'மருத்துவ வரலாறு பதிவுகள் இல்லை.',
  'prescription_writer': 'மருந்துச்சீட்டு எழுதுபவர்',
  'diagnosis': 'நோய் கண்டறிதல்',
  'dosage_instructions': 'மருந்து அளவு அறிவுறுத்தல்கள்',
  'notes': 'குறிப்புகள்',
  'medicine_name': 'மருந்தின் பெயர்',
  'dosage': 'அளவு',
  'frequency': 'எத்தனை முறை',
  'duration': 'கால அளவு',
  'add_medicine': 'மருந்து சேர்க்க',
  'remove': 'நீக்கு',
  'issue_prescription': 'மருந்துச்சீட்டு வழங்க',
  'prescription_success': 'மருந்துச்சீட்டு வழங்கப்பட்டு நோயாளியின் ஹெல்த் வாலட் மற்றும் மருந்தகக் வரிசையுடன் ஒத்திசைக்கப்பட்டது.',
  'prescription_failed': 'மருந்துச்சீட்டு வழங்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
  'at_least_one_medicine': 'சமர்ப்பிக்கும் முன் குறைந்தது ஒரு மருந்தையாவது சேர்க்கவும்.',
  'interaction_warning_title': 'மருந்து எதிர்வினை எச்சரிக்கை',
  'my_schedule': 'எனது அட்டவணை',
  'availability_slots': 'கிடைக்கும் நேரங்கள்',
  'add_slot': 'நேரத்தைச் சேர்க்க',
  'start_time': 'தொடக்க நேரம்',
  'end_time': 'முடிவு நேரம்',
  'no_slots': 'இன்னும் நேரங்கள் வெளியிடப்படவில்லை.',
  'slot_booked': 'பதிவு செய்யப்பட்டது',
  'slot_open': 'திறந்துள்ளது',
  'delete_slot_confirm': 'இந்த நேரத்தை நீக்கவா?',
  'available_for_consultation': 'ஆலோசனைக்கு கிடைக்கிறேன்',
  'critical_alerts': 'அவசர எச்சரிக்கைகள்',
  'no_active_alerts': 'தற்போது செயலில் உள்ள அவசர எச்சரிக்கைகள் இல்லை.',
  'sos_severity': 'தீவிரம்',
  'sos_location': 'இடம்',
  'sos_status': 'நிலை',
  'refreshing': 'புதுப்பிக்கிறது…',
  'profile': 'சுயவிவரம்',
  'specialty': 'சிறப்பு பிரிவு',
  'qualifications': 'தகுதிகள்',
  'experience_years': 'அனுபவம் (ஆண்டுகள்)',
  'consultation_fee': 'ஆலோசனைக் கட்டணம்',
  'languages': 'மொழிகள்',
  'logout': 'வெளியேறு',
  'language': 'மொழி',
  'save': 'சேமிக்க',
  'cancel': 'ரத்து',
  'delete': 'நீக்கு',
  'edit_profile': 'சுயவிவரத்தைத் திருத்த',
  'profile_updated': 'சுயவிவரம் புதுப்பிக்கப்பட்டது.',
  'loading': 'ஏற்றுகிறது…',
  'error_generic': 'ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும்.',
  'retry': 'மீண்டும் முயற்சி',
  'confirm': 'உறுதிப்படுத்து',
  'view_history': 'மருத்துவ வரலாற்றைப் பார்க்க',
};
