/// Offline-first rule-based triage FALLBACK.
///
/// This is deliberately NOT an on-device AI model — training, quantizing, or
/// bundling a real neural network for client-side symptom triage is out of
/// proportion for this app and would need infrastructure this repo doesn't
/// have. Instead this is a small curated keyword-matching heuristic used
/// ONLY as a safety net when the real AI triage network call (POST
/// /triage/analyze, see ../screens/triage_screen.dart) fails because the
/// device has no connectivity.
///
/// Safety posture: this table is intentionally biased toward *over*-caution,
/// never under-caution. When multiple entries match the input text,
/// [offlineTriageEstimate] always returns the HIGHEST-severity match, never
/// the lowest — a false "you're fine" produced offline is far more
/// dangerous than an unnecessary nudge to seek care. If nothing recognizable
/// matches, it returns `null` rather than silently defaulting to LOW, so the
/// caller can tell the user it couldn't even produce an offline estimate.
///
/// Kept in sync (same keyword table, same severities) with the TypeScript
/// original at apps/web_portal/src/lib/offlineTriage.ts so the web and
/// mobile apps don't give wildly different offline answers for the same
/// symptoms text.
library;

enum OfflineSeverity { critical, high, moderate, low }

extension OfflineSeverityX on OfflineSeverity {
  String get label {
    switch (this) {
      case OfflineSeverity.critical:
        return 'CRITICAL';
      case OfflineSeverity.high:
        return 'HIGH';
      case OfflineSeverity.moderate:
        return 'MODERATE';
      case OfflineSeverity.low:
        return 'LOW';
    }
  }

  /// Higher = more severe. Used to pick the worst match, never the mildest.
  int get rank {
    switch (this) {
      case OfflineSeverity.low:
        return 0;
      case OfflineSeverity.moderate:
        return 1;
      case OfflineSeverity.high:
        return 2;
      case OfflineSeverity.critical:
        return 3;
    }
  }
}

class OfflineTriageEntry {
  final List<String> keywords;
  final OfflineSeverity severity;
  final String department;
  final String recommendation;

  const OfflineTriageEntry({
    required this.keywords,
    required this.severity,
    required this.department,
    required this.recommendation,
  });
}

class OfflineTriageResult {
  final OfflineSeverity severity;
  final String department;
  final String recommendation;
  final String matchedKeyword;

  const OfflineTriageResult({
    required this.severity,
    required this.department,
    required this.recommendation,
    required this.matchedKeyword,
  });
}

// ~15-20 curated, real-world entries — English coverage is solid; a handful
// of common Tamil transliterations (Tanglish) are included where they're
// likely to actually be spoken/typed by a Tamil-speaking user, not an
// exhaustive translation of every entry. Mirrors OFFLINE_TRIAGE_TABLE in
// apps/web_portal/src/lib/offlineTriage.ts entry-for-entry.
const List<OfflineTriageEntry> offlineTriageTable = [
  OfflineTriageEntry(
    keywords: ['chest pain', 'chest pressure', 'chest tightness', 'pain in chest', 'pressure in chest', 'nenju vali', 'nenjil vali'],
    severity: OfflineSeverity.critical,
    department: 'Cardiology',
    recommendation: 'This can be a sign of a heart attack or another life-threatening cardiac event. Call 108 (or your local emergency number) or go to the nearest emergency room immediately — do not wait to see if it passes.',
  ),
  OfflineTriageEntry(
    keywords: ['difficulty breathing', 'breathless', 'shortness of breath', "can't breathe", 'cannot breathe', 'trouble breathing', 'gasping for air', 'moochu vidamudiyala', 'moochu thinaral'],
    severity: OfflineSeverity.critical,
    department: 'Pulmonology',
    recommendation: 'Severe breathing difficulty can become life-threatening within minutes. Call emergency services (108) or get to the nearest emergency room right away.',
  ),
  OfflineTriageEntry(
    keywords: ['severe bleeding', 'heavy bleeding', 'bleeding heavily', "won't stop bleeding", 'excessive bleeding', 'blood loss', 'rathakkasivu adhigam'],
    severity: OfflineSeverity.critical,
    department: 'Emergency Medicine',
    recommendation: 'Uncontrolled bleeding needs immediate emergency care. Apply firm, direct pressure to the wound and call 108 or go to the nearest emergency room now.',
  ),
  OfflineTriageEntry(
    keywords: ['unconscious', 'unresponsive', 'not waking up', 'passed out', 'fainted and not responding', 'mayangi kidakiraru'],
    severity: OfflineSeverity.critical,
    department: 'Emergency Medicine',
    recommendation: 'This is a medical emergency. Call 108 immediately, keep the person on their side if they are breathing, and do not leave them alone.',
  ),
  OfflineTriageEntry(
    keywords: ['stiff neck', 'neck stiffness', 'kazhuthu vali kaduppu'],
    severity: OfflineSeverity.critical,
    department: 'Emergency Medicine',
    recommendation: 'A stiff neck — especially together with a high fever — can be a warning sign of meningitis, a medical emergency. Seek emergency care immediately rather than waiting it out at home.',
  ),
  OfflineTriageEntry(
    keywords: ['seizure', 'convulsion', 'fits', 'fitting'],
    severity: OfflineSeverity.critical,
    department: 'Neurology',
    recommendation: 'A seizure needs urgent medical evaluation. Call 108 if it lasts more than 5 minutes, repeats, or the person does not regain consciousness afterward.',
  ),
  OfflineTriageEntry(
    keywords: ['poisoning', 'swallowed poison', 'drug overdose', 'ate something poisonous'],
    severity: OfflineSeverity.critical,
    department: 'Emergency Medicine',
    recommendation: 'Suspected poisoning is a medical emergency. Call 108 or a poison-control helpline immediately; do not induce vomiting unless a professional tells you to.',
  ),
  OfflineTriageEntry(
    keywords: ['snake bite', 'snakebite', 'animal bite', 'dog bite'],
    severity: OfflineSeverity.critical,
    department: 'Emergency Medicine',
    recommendation: 'Keep the person calm and still, immobilize the bitten limb below heart level, and get to the nearest hospital immediately. Do not cut the wound, try to suck out venom, or apply a tight tourniquet.',
  ),
  OfflineTriageEntry(
    keywords: ['burn', 'burned skin', 'scald', 'fire injury'],
    severity: OfflineSeverity.high,
    department: 'Emergency Medicine',
    recommendation: 'Cool the burn under running water for about 20 minutes and cover loosely with a clean cloth. Seek urgent care for large, deep, or facial/hand burns, or if the skin is charred or blistering badly.',
  ),
  OfflineTriageEntry(
    keywords: ['fever', 'high temperature', 'running a temperature', 'jwaram', 'kaachal'],
    severity: OfflineSeverity.moderate,
    department: 'General Medicine',
    recommendation: 'Monitor your temperature, stay hydrated, and rest. See a doctor if the fever is above 103°F/39.4°C, lasts more than 2-3 days, or comes with other severe symptoms.',
  ),
  OfflineTriageEntry(
    keywords: ['stomach pain', 'abdominal pain', 'belly pain', 'tummy pain', 'vayitru vali'],
    severity: OfflineSeverity.moderate,
    department: 'Gastroenterology',
    recommendation: 'Mild stomach pain often settles on its own. See a doctor soon if the pain is severe, persistent, localized to one side, or comes with fever or vomiting.',
  ),
  OfflineTriageEntry(
    keywords: ['vomiting', 'diarrhea', 'loose motion', 'throwing up', 'vaandhi'],
    severity: OfflineSeverity.moderate,
    department: 'General Medicine',
    recommendation: 'Stay hydrated with an oral rehydration solution. See a doctor if it lasts more than 2 days, contains blood, or comes with high fever or signs of dehydration.',
  ),
  OfflineTriageEntry(
    keywords: ['cough', 'cold', 'sore throat', 'runny nose', 'sneezing', 'irumal', 'jaladhosham'],
    severity: OfflineSeverity.low,
    department: 'General Medicine',
    recommendation: 'These are usually mild and self-limiting. Rest, fluids, and warm salt-water gargles can help. See a doctor if symptoms worsen or last more than a week.',
  ),
  OfflineTriageEntry(
    keywords: ['headache', 'head pain', 'migraine', 'thalai vali'],
    severity: OfflineSeverity.low,
    department: 'General Medicine',
    recommendation: 'Rest in a quiet, dark room and stay hydrated. See a doctor if the headache is sudden and severe, the worst of your life, or comes with vision changes, confusion, or fever.',
  ),
  OfflineTriageEntry(
    keywords: ['rash', 'skin rash', 'itchy skin', 'skin allergy', 'hives'],
    severity: OfflineSeverity.low,
    department: 'Dermatology',
    recommendation: 'Most rashes are mild. Avoid scratching and any known irritants. See a doctor if the rash spreads rapidly, blisters, or comes with fever or difficulty breathing.',
  ),
  OfflineTriageEntry(
    keywords: ['ear pain', 'earache', 'ear ache', 'kaadhu vali'],
    severity: OfflineSeverity.low,
    department: 'General Medicine',
    recommendation: 'Mild ear pain often resolves with rest and over-the-counter pain relief. See a doctor if the pain is severe, there is discharge from the ear, or you notice hearing loss.',
  ),
  OfflineTriageEntry(
    keywords: ['toothache', 'tooth pain', 'dental pain', 'pal vali'],
    severity: OfflineSeverity.low,
    department: 'Dentistry',
    recommendation: 'Rinse with warm salt water and avoid very hot, cold, or sugary food. See a dentist soon, especially if there is swelling or fever.',
  ),
  OfflineTriageEntry(
    keywords: ['eye pain', 'red eye', 'eye redness', 'eye irritation', 'kann vali'],
    severity: OfflineSeverity.low,
    department: 'Ophthalmology',
    recommendation: 'Avoid rubbing the eye and remove contact lenses if worn. See a doctor if the pain is severe, vision is affected, or there is significant discharge.',
  ),
  OfflineTriageEntry(
    keywords: ['joint pain', 'body ache', 'muscle pain', 'back pain', 'udal vali'],
    severity: OfflineSeverity.low,
    department: 'General Medicine',
    recommendation: 'Rest, gentle stretching, and over-the-counter pain relief often help. See a doctor if the pain is severe, follows an injury, or does not improve within a few days.',
  ),
];

/// Curated keyword-matching offline triage estimate. NOT a substitute for
/// the real AI analysis — only used when that network call cannot be
/// reached.
///
/// Lowercases the input and scans every table entry for a keyword match,
/// returning the HIGHEST-severity match found (bias toward caution). Returns
/// `null` when nothing recognizable matches — callers must not treat that as
/// "low severity", it means the offline estimate has nothing useful to say.
OfflineTriageResult? offlineTriageEstimate(String symptomsText) {
  if (symptomsText.trim().isEmpty) return null;
  final text = symptomsText.toLowerCase();

  OfflineTriageResult? best;
  for (final entry in offlineTriageTable) {
    for (final keyword in entry.keywords) {
      if (text.contains(keyword.toLowerCase())) {
        if (best == null || entry.severity.rank > best.severity.rank) {
          best = OfflineTriageResult(
            severity: entry.severity,
            department: entry.department,
            recommendation: entry.recommendation,
            matchedKeyword: keyword,
          );
        }
        break; // this entry already matched — no need to check its other keywords
      }
    }
  }
  return best;
}
