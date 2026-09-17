import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/ai_key_service.dart';
import '../services/app_strings.dart';

/// Shown only once the server reports its shared AI quota is spent.
///
/// The alternative was the silent placeholder answer users were getting —
/// a card that looks like a real assessment but says "AI Engines
/// Unavailable" with 0% confidence. Telling someone plainly that the limit
/// is reached, and offering them a way through it, is more honest than a
/// confident-looking empty result.
///
/// Deliberately not shown when the user already supplied a key, and never
/// shown for an ordinary failure — a server that is merely misconfigured
/// must not ask a patient to fix it with a credential of their own.
class AiQuotaPrompt extends StatefulWidget {
  /// Called after the user saves a key, so the caller can retry the request
  /// that triggered this prompt.
  final VoidCallback onKeySaved;

  /// String key for the headline. The reason there is no AI answer decides
  /// it: "limit reached" shown for an unfunded account or a retired model
  /// told patients they had hit a limit they had not.
  final String titleKey;

  /// Called when the patient says they have no key.
  final VoidCallback? onDismiss;

  const AiQuotaPrompt({
    super.key,
    required this.onKeySaved,
    this.titleKey = 'ai_limit_exhausted',
    this.onDismiss,
  });

  @override
  State<AiQuotaPrompt> createState() => _AiQuotaPromptState();
}

class _AiQuotaPromptState extends State<AiQuotaPrompt> {
  final TextEditingController _controller = TextEditingController();
  bool _entering = false;
  bool _saving = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final value = _controller.text.trim();
    if (value.isEmpty) return;
    setState(() => _saving = true);
    await AiKeyService().save(value);
    if (!mounted) return;
    setState(() {
      _saving = false;
      _entering = false;
    });
    _controller.clear();
    widget.onKeySaved();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<LocaleService>();

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFEE2E2),
        border: Border.all(color: const Color(0xFFEF4444), width: 1.2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.error_outline, size: 18, color: Color(0xFFB91C1C)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.t(widget.titleKey),
                  style: const TextStyle(
                    color: Color(0xFFB91C1C),
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          if (!_entering) ...[
            Text(
              s.t('have_own_api_key'),
              style: const TextStyle(fontSize: 13, color: Color(0xFF7F1D1D)),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                ElevatedButton(
                  onPressed: () => setState(() => _entering = true),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEF4444),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 8),
                  ),
                  child: Text(s.t('yes')),
                ),
                const SizedBox(width: 10),
                OutlinedButton(
                  // "No" simply dismisses. The offline estimate below is
                  // still there; nagging someone who does not have a key
                  // would just be in the way of reading it.
                  onPressed: () {
                    AiKeyService().noteQuotaExhausted(false);
                    widget.onDismiss?.call();
                  },
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFFB91C1C),
                    side: const BorderSide(color: Color(0xFFEF4444)),
                    padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 8),
                  ),
                  child: Text(s.t('no')),
                ),
              ],
            ),
          ] else ...[
            TextField(
              controller: _controller,
              autofocus: true,
              obscureText: true,
              enableSuggestions: false,
              autocorrect: false,
              style: const TextStyle(fontSize: 13),
              decoration: InputDecoration(
                hintText: s.t('paste_api_key'),
                filled: true,
                fillColor: Colors.white,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onSubmitted: (_) => _save(),
            ),
            const SizedBox(height: 6),
            Text(
              s.t('api_key_stays_on_phone'),
              style: const TextStyle(fontSize: 11, color: Color(0xFF7F1D1D)),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                ElevatedButton(
                  onPressed: _saving ? null : _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFEF4444),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 8),
                  ),
                  child: _saving
                      ? const SizedBox(
                          height: 14, width: 14,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : Text(s.t('save_and_retry')),
                ),
                const SizedBox(width: 10),
                TextButton(
                  onPressed: _saving ? null : () => setState(() => _entering = false),
                  style: TextButton.styleFrom(foregroundColor: const Color(0xFFB91C1C)),
                  child: Text(s.t('cancel')),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
