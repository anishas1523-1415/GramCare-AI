import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Lightweight English/Tamil localization — same map-based approach as
/// apps/mobile_app/lib/services/app_strings.dart (see that file's header
/// comment for why this isn't ARB/gen-l10n). Pharmacists in rural areas are
/// often Tamil-first too, so the same bilingual UI matters here.
class LocaleService extends ChangeNotifier {
  static const _key = 'gramcare_pharmacy_locale';
  String _code = 'en'; // Pharmacist app defaults to English; toggle to Tamil available

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
  'app_title': 'GramCare Pharmacy',
  'tagline': 'Pharmacist Companion',
  'login': 'Login',
  'username_hint': 'Username (e.g., pharmacist1)',
  'password_hint': 'Password',
  'invalid_credentials': 'Invalid credentials. Please try again.',
  'wrong_role': 'This account is not registered as a Pharmacist.',
  'language': 'Language',
  'dashboard': 'Dashboard',
  'pending_orders': 'Pending Orders',
  'expiring_soon': 'Expiring Soon',
  'low_stock': 'Low Stock',
  'order_queue': 'Order Queue',
  'stock_management': 'Stock',
  'expiry_alerts': 'Expiry Alerts',
  'shortage_alerts': 'Shortage Alerts',
  'profile': 'Profile',
  'logout': 'Logout',
  'no_orders': 'No pending orders right now.',
  'fulfill': 'Fulfill',
  'fulfilled': 'Fulfilled',
  'medicines_needed': 'Medicines needed',
  'substitute_suggestion': 'Cheaper alternative available',
  'not_in_stock_warning': 'Not in your stock',
  'confirm_fulfill': 'Mark this prescription as fulfilled? Stock will be decremented automatically.',
  'interaction_warning_title': 'Medicine Interaction Warning',
  'interaction_warning_ack': 'I understand — mark fulfilled',
  'confirm': 'Confirm',
  'cancel': 'Cancel',
  'no_stock_items': 'No medicines in stock yet. Add your first item.',
  'add_item': 'Add Item',
  'medicine_name': 'Medicine name',
  'generic_group': 'Generic group (optional)',
  'price': 'Price',
  'initial_stock': 'Initial stock count',
  'requires_prescription': 'Requires prescription',
  'expiry_date': 'Expiry date',
  'batch_number': 'Batch number (optional)',
  'save': 'Save',
  'capture_invoice_photo': 'Capture invoice photo',
  'invoice_photo_note': 'Photo captured — key in the details below from the invoice.',
  'sale_logged': 'Sale logged',
  'tap_to_sell': 'Tap to sell one',
  'set_count': 'Set end-of-day count',
  'set': 'Set',
  'add_stock': 'Add stock (shipment)',
  'remaining': 'Remaining',
  'status_optimal': 'Optimal',
  'status_low': 'Low',
  'status_out': 'Out of Stock',
  'no_expiring_items': 'Nothing expiring soon.',
  'days_left': 'days left',
  'no_shortages': 'No shortages right now.',
  'pharmacy_name': 'Pharmacy name',
  'address': 'Address',
  'phone': 'Phone',
  'no_profile': 'No pharmacy profile found.',
  'error_generic': 'Something went wrong. Please try again.',
  'offline_note': 'Offline — check your connection and retry.',
  'retry': 'Retry',
};

const Map<String, String> _ta = {
  'app_title': 'கிராம்கேர் மருந்தகம்',
  'tagline': 'மருந்தாளர் துணை',
  'login': 'உள்நுழைக',
  'username_hint': 'பயனர்பெயர் (எ.கா. pharmacist1)',
  'password_hint': 'கடவுச்சொல்',
  'invalid_credentials': 'தவறான விவரங்கள். மீண்டும் முயற்சிக்கவும்.',
  'wrong_role': 'இந்த கணக்கு மருந்தாளராக பதிவு செய்யப்படவில்லை.',
  'language': 'மொழி',
  'dashboard': 'டாஷ்போர்டு',
  'pending_orders': 'நிலுவை ஆர்டர்கள்',
  'expiring_soon': 'விரைவில் காலாவதி',
  'low_stock': 'குறைந்த இருப்பு',
  'order_queue': 'ஆர்டர் வரிசை',
  'stock_management': 'இருப்பு',
  'expiry_alerts': 'காலாவதி எச்சரிக்கைகள்',
  'shortage_alerts': 'பற்றாக்குறை எச்சரிக்கைகள்',
  'profile': 'சுயவிவரம்',
  'logout': 'வெளியேறு',
  'no_orders': 'இப்போது நிலுவை ஆர்டர்கள் இல்லை.',
  'fulfill': 'வழங்கு',
  'fulfilled': 'வழங்கப்பட்டது',
  'medicines_needed': 'தேவையான மருந்துகள்',
  'substitute_suggestion': 'மலிவான மாற்று மருந்து உள்ளது',
  'not_in_stock_warning': 'உங்கள் இருப்பில் இல்லை',
  'confirm_fulfill': 'இந்த மருந்துச்சீட்டை வழங்கியதாக குறிக்கவா? இருப்பு தானாக குறைக்கப்படும்.',
  'interaction_warning_title': 'மருந்து எதிர்வினை எச்சரிக்கை',
  'interaction_warning_ack': 'புரிந்தது — வழங்கியதாக குறி',
  'confirm': 'உறுதிசெய்',
  'cancel': 'ரத்து',
  'no_stock_items': 'இன்னும் மருந்துகள் இல்லை. முதல் பொருளைச் சேர்க்கவும்.',
  'add_item': 'பொருள் சேர்',
  'medicine_name': 'மருந்தின் பெயர்',
  'generic_group': 'ஜெனரிக் குழு (விருப்பம்)',
  'price': 'விலை',
  'initial_stock': 'ஆரம்ப இருப்பு எண்ணிக்கை',
  'requires_prescription': 'மருந்துச்சீட்டு தேவை',
  'expiry_date': 'காலாவதி தேதி',
  'batch_number': 'பேட்ச் எண் (விருப்பம்)',
  'save': 'சேமிக்க',
  'capture_invoice_photo': 'இன்வாய்ஸ் புகைப்படம் எடுக்க',
  'invoice_photo_note': 'புகைப்படம் எடுக்கப்பட்டது — இன்வாய்ஸிலிருந்து விவரங்களை கீழே உள்ளிடவும்.',
  'sale_logged': 'விற்பனை பதிவு செய்யப்பட்டது',
  'tap_to_sell': 'ஒன்று விற்க தட்டவும்',
  'set_count': 'நாள் இறுதி எண்ணிக்கையை அமை',
  'set': 'அமை',
  'add_stock': 'இருப்பு சேர் (சரக்கு)',
  'remaining': 'மீதம்',
  'status_optimal': 'சிறந்தது',
  'status_low': 'குறைவு',
  'status_out': 'இருப்பு இல்லை',
  'no_expiring_items': 'விரைவில் காலாவதியாகும் எதுவும் இல்லை.',
  'days_left': 'நாட்கள் மீதம்',
  'no_shortages': 'இப்போது பற்றாக்குறை இல்லை.',
  'pharmacy_name': 'மருந்தக பெயர்',
  'address': 'முகவரி',
  'phone': 'தொலைபேசி',
  'no_profile': 'மருந்தக சுயவிவரம் இல்லை.',
  'error_generic': 'ஏதோ தவறு நடந்தது. மீண்டும் முயற்சிக்கவும்.',
  'offline_note': 'ஆஃப்லைன் — உங்கள் இணைப்பைச் சரிபார்த்து மீண்டும் முயற்சிக்கவும்.',
  'retry': 'மீண்டும் முயற்சி',
};
