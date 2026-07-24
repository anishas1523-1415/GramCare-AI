import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Lightweight English/Tamil localization.
///
/// Why not flutter_localizations + ARB codegen: this repo's CI builds run
/// `flutter analyze` on a clean checkout, and gen-l10n output would need to
/// be committed or generated in CI. A plain map keeps localization fully
/// source-controlled, trivially testable, and lets rural-facing strings be
/// reviewed by Tamil speakers in one file. If the string count grows past a
/// few hundred, migrate to ARB (mechanical change — call sites keep the
/// same `S.of(context).key` shape via this provider).
///
/// Planning doc: "ரீஜினல் லாங்குவேஜ் வாய்ஸ் அண்ட் டெக்ஸ்ட் சப்போர்ட்
/// ரொம்பவே முக்கியம்" — Tamil is the launch language alongside English.
class LocaleService extends ChangeNotifier {
  static const _key = 'gramcare_locale';
  String _code = 'ta'; // Tamil-first: the target user is the rural patient

  String get code => _code;
  bool get isTamil => _code == 'ta';

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _code = prefs.getString(_key) ?? 'ta';
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
  'app_title': 'GramCare AI',
  'tagline': 'Offline-First Healthcare Ecosystem',
  'back': 'Back',
  'medicine_recall_alert': 'Medicine Recall Alert',
  'login': 'Login',
  'username_hint': 'Username (e.g., patient1)',
  'password_hint': 'Password',
  'invalid_credentials': 'Invalid credentials. Please try again.',
  'acting_for_self': 'Acting for: Myself',
  'acting_for': 'Acting for',
  'myself': 'Myself',
  'my_own_health': 'My own health',
  'who_is_this_for': 'Who is this for?',
  'add_member': 'Add member',
  'health_wallet': 'Health Wallet',
  'symptom_checker': 'Symptom Checker',
  'scan_prescription': 'Scan Prescription',
  'find_medicine': 'Find Medicine',
  'iot_vitals': 'IoT Vitals',
  'medicine_reminders': 'Medicine Reminders',
  'emergency_sos': 'EMERGENCY SOS',
  'emergency_contacts': 'Emergency Contacts',
  'hold_to_sos': 'Hold the button for 3 seconds to send SOS',
  'hold_to_sos_listening': "Hold and speak — tell us what happened",
  'sos_sent': 'EMERGENCY SOS SENT — help has been alerted',
  'sos_failed': 'SOS FAILED TO SEND. Please call 108 directly.',
  'sos_sms_fallback': 'No internet — opening SMS to alert your contacts',
  'sos_status_active': 'Alert sent — waiting for a hospital to respond.',
  'sos_status_responded': 'Help is on the way. A hospital has responded to your alert.',
  'sos_status_resolved': 'This emergency has been marked resolved.',
  'sos_escalated': 'No response yet — your alert has been forwarded to the next nearest hospital.',
  'sos_status_error': 'Could not check your alert status. Retrying…',
  'describe_symptoms': 'Describe your symptoms in detail:',
  'speak_symptoms': 'Tap the mic and speak',
  'add_symptom_photo': 'Add a photo of the symptom (optional)',
  'listening': 'Listening…',
  'analyze_with_ai': 'Analyze with AI',
  'analyzing': 'Analyzing…',
  'severity_score': 'Severity Score',
  'predicted_condition': 'Possible Condition',
  'doctor_recommendation': 'Doctor Recommendation',
  'home_remedies': 'Home Remedies',
  'first_aid': 'First Aid',
  'possible_causes': 'Possible Causes',
  'treatment_options': 'Treatment Options',
  'untreated_outcome': 'If Left Untreated',
  'specialist': 'Recommended Specialist',
  'recovery_time': 'Recovery Time',
  'side_effects': 'Side Effects to Watch For',
  'why_ai_thinks_this': 'Why does the AI think this?',
  'tap_to_hear': 'Tap to hear',
  'critical_prompt_title': 'This looks serious',
  'critical_prompt_body': 'The AI assessment is CRITICAL. Do you want to send an Emergency SOS now?',
  'send_sos_now': 'SEND SOS NOW',
  'not_now': 'Not now',
  'no_records': 'No records yet. Run a symptom check or scan a prescription.',
  'sync_now': 'Sync now',
  'save_to_wallet': 'Looks right — Save to Wallet',
  'retake_photo': 'Retake photo',
  'saved_to_wallet': 'Saved to Health Wallet — will sync when online',
  'camera': 'Camera',
  'gallery': 'Gallery',
  'search_failed': 'Search failed. Are you online?',
  'offline_estimate_banner': "Offline estimate — not a full AI analysis. This is only a basic keyword-based safety check because we couldn't reach the server. Connect to the internet when possible, and seek care immediately if this feels serious.",
  'offline_no_match': "You appear to be offline, and this couldn't produce even an offline estimate for these symptoms. If you're at all concerned, please seek care or call your local emergency number.",
  'in_stock': 'In stock',
  'not_available': 'Not available here',
  'alternatives': 'Same-effect alternatives',
  'language': 'Language',
  'name': 'Name',
  'phone': 'Phone',
  'relation': 'Relation',
  'save': 'Save',
  'cancel': 'Cancel',
  'delete': 'Delete',
  'add_contact': 'Add contact',
  'no_contacts': 'Add family numbers to alert them during an emergency.',
  'offline_note': 'Offline — data will sync when connected',
};

const Map<String, String> _ta = {
  'app_title': 'கிராம்கேர் AI',
  'tagline': 'ஆஃப்லைன்-முதல் சுகாதார அமைப்பு',
  'back': 'பின் செல்',
  'medicine_recall_alert': 'மருந்து திரும்பப் பெறல் எச்சரிக்கை',
  'login': 'உள்நுழைக',
  'username_hint': 'பயனர்பெயர் (எ.கா. patient1)',
  'password_hint': 'கடவுச்சொல்',
  'invalid_credentials': 'தவறான விவரங்கள். மீண்டும் முயற்சிக்கவும்.',
  'acting_for_self': 'யாருக்காக: நானே',
  'acting_for': 'யாருக்காக',
  'myself': 'நானே',
  'my_own_health': 'என் சொந்த ஆரோக்கியம்',
  'who_is_this_for': 'இது யாருக்காக?',
  'add_member': 'உறுப்பினரைச் சேர்க்க',
  'health_wallet': 'ஹெல்த் வாலட்',
  'symptom_checker': 'அறிகுறி பரிசோதனை',
  'scan_prescription': 'மருந்துச்சீட்டை ஸ்கேன்',
  'find_medicine': 'மருந்து தேடு',
  'iot_vitals': 'உடல்நிலை அளவீடுகள்',
  'medicine_reminders': 'மருந்து நினைவூட்டல்',
  'emergency_sos': 'அவசர உதவி (SOS)',
  'emergency_contacts': 'அவசர தொடர்புகள்',
  'hold_to_sos': 'SOS அனுப்ப பட்டனை 3 வினாடி அழுத்திப் பிடிக்கவும்',
  'hold_to_sos_listening': 'அழுத்திப் பிடித்து என்ன நடந்தது என்று சொல்லுங்கள்',
  'sos_sent': 'அவசர SOS அனுப்பப்பட்டது — உதவி வருகிறது',
  'sos_failed': 'SOS அனுப்ப முடியவில்லை. 108-ஐ நேரடியாக அழைக்கவும்.',
  'sos_sms_fallback': 'இணையம் இல்லை — உங்கள் தொடர்புகளுக்கு SMS அனுப்புகிறோம்',
  'sos_status_active': 'எச்சரிக்கை அனுப்பப்பட்டது — மருத்துவமனையின் பதிலுக்காக காத்திருக்கிறோம்.',
  'sos_status_responded': 'உதவி வருகிறது. உங்கள் எச்சரிக்கைக்கு ஒரு மருத்துவமனை பதிலளித்துள்ளது.',
  'sos_status_resolved': 'இந்த அவசரநிலை தீர்க்கப்பட்டதாகக் குறிக்கப்பட்டுள்ளது.',
  'sos_escalated': 'இன்னும் பதில் இல்லை — உங்கள் எச்சரிக்கை அடுத்த அருகிலுள்ள மருத்துவமனைக்கு அனுப்பப்பட்டுள்ளது.',
  'sos_status_error': 'உங்கள் எச்சரிக்கை நிலையைச் சரிபார்க்க முடியவில்லை. மீண்டும் முயற்சிக்கிறோம்…',
  'describe_symptoms': 'உங்கள் அறிகுறிகளை விவரமாகச் சொல்லுங்கள்:',
  'speak_symptoms': 'மைக்கைத் தட்டி பேசுங்கள்',
  'add_symptom_photo': 'அறிகுறியின் புகைப்படத்தைச் சேர்க்கவும் (விருப்பத்திற்குரியது)',
  'listening': 'கேட்கிறது…',
  'analyze_with_ai': 'AI மூலம் பரிசோதிக்க',
  'analyzing': 'பரிசோதிக்கிறது…',
  'severity_score': 'தீவிர அளவு',
  'predicted_condition': 'சாத்தியமான பிரச்சனை',
  'doctor_recommendation': 'மருத்துவர் பரிந்துரை',
  'home_remedies': 'வீட்டு வைத்தியம்',
  'first_aid': 'முதலுதவி',
  'possible_causes': 'சாத்தியமான காரணங்கள்',
  'treatment_options': 'சிகிச்சை வழிகள்',
  'untreated_outcome': 'கவனிக்காவிட்டால்',
  'specialist': 'பரிந்துரைக்கப்படும் நிபுணர்',
  'recovery_time': 'குணமாகும் காலம்',
  'side_effects': 'கவனிக்க வேண்டிய பக்க விளைவுகள்',
  'why_ai_thinks_this': 'AI ஏன் இப்படி நினைக்கிறது?',
  'tap_to_hear': 'கேட்கத் தட்டவும்',
  'critical_prompt_title': 'இது தீவிரமாகத் தெரிகிறது',
  'critical_prompt_body': 'AI மதிப்பீடு மிக அவசரம் என்கிறது. இப்போதே அவசர SOS அனுப்பவா?',
  'send_sos_now': 'இப்போதே SOS அனுப்பு',
  'not_now': 'இப்போது வேண்டாம்',
  'no_records': 'இன்னும் பதிவுகள் இல்லை. அறிகுறி பரிசோதனை அல்லது ஸ்கேன் செய்யுங்கள்.',
  'sync_now': 'இப்போது ஒத்திசை',
  'save_to_wallet': 'சரியாக உள்ளது — வாலட்டில் சேமிக்க',
  'retake_photo': 'மீண்டும் புகைப்படம் எடு',
  'saved_to_wallet': 'ஹெல்த் வாலட்டில் சேமிக்கப்பட்டது — இணையம் வந்ததும் ஒத்திசையும்',
  'camera': 'கேமரா',
  'gallery': 'கேலரி',
  'search_failed': 'தேடல் தோல்வி. இணையம் உள்ளதா?',
  'offline_estimate_banner': 'ஆஃப்லைன் மதிப்பீடு — முழுமையான AI பகுப்பாய்வு அல்ல. சர்வரை அடைய முடியாததால் இது ஒரு அடிப்படை கீவேர்ட் அடிப்படையிலான பாதுகாப்பு சோதனை மட்டுமே. முடிந்தவுடன் இணையத்துடன் இணையவும், இது தீவிரமாக உணரப்பட்டால் உடனடியாக மருத்துவ உதவியை நாடவும்.',
  'offline_no_match': 'நீங்கள் ஆஃப்லைனில் இருப்பதாகத் தெரிகிறது, மேலும் இந்த அறிகுறிகளுக்கு ஆஃப்லைன் மதிப்பீடு கூட வழங்க முடியவில்லை. கவலையாக இருந்தால், தயவுசெய்து மருத்துவ உதவியை நாடவும் அல்லது உங்கள் உள்ளூர் அவசர எண்ணை அழைக்கவும்.',
  'in_stock': 'இருப்பில் உள்ளது',
  'not_available': 'இங்கு கிடைக்கவில்லை',
  'alternatives': 'அதே பலன் தரும் மாற்று மருந்துகள்',
  'language': 'மொழி',
  'name': 'பெயர்',
  'phone': 'தொலைபேசி',
  'relation': 'உறவு',
  'save': 'சேமிக்க',
  'cancel': 'ரத்து',
  'delete': 'நீக்கு',
  'add_contact': 'தொடர்பைச் சேர்க்க',
  'no_contacts': 'அவசர நேரத்தில் அறிவிக்க குடும்ப எண்களைச் சேர்க்கவும்.',
  'offline_note': 'ஆஃப்லைன் — இணையம் வந்ததும் ஒத்திசையும்',
};
