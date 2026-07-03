import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../services/api_service.dart';

/// Nearby medicine availability — planning doc: "பக்கத்துல இருக்கற எந்த
/// பார்மசியில அந்த மருந்து இருக்குன்னு காட்டும்" with green/red coding and
/// generic substitutes when unavailable.
///
/// GPS capture ships with roadmap Phase 6 (geolocator lands alongside the
/// SOS work); until then the search runs unlocated and the server returns
/// all registered pharmacies with availability.
class PharmacySearchScreen extends StatefulWidget {
  const PharmacySearchScreen({super.key});

  @override
  State<PharmacySearchScreen> createState() => _PharmacySearchScreenState();
}

class _PharmacySearchScreenState extends State<PharmacySearchScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _loading = false;
  String _error = '';
  List<Map<String, dynamic>>? _results;

  // Pharmacy module theme: green (planning doc's per-module color identity)
  static const _themeColor = Color(0xFF10B981);

  Future<void> _search() async {
    final query = _controller.text.trim();
    if (query.length < 2) return;
    setState(() {
      _loading = true;
      _error = '';
      _results = null;
    });
    try {
      final res = await ApiService().client.get(
        '/pharmacy/search',
        queryParameters: {'medicine': query},
      );
      setState(() {
        _results = List<Map<String, dynamic>>.from(res.data as List);
      });
    } catch (_) {
      setState(() => _error = 'Search failed. Are you online?');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFE0E5EC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2D3748)),
          onPressed: () => context.pop(),
        ),
        title: const Text(
          'Find Medicine',
          style: TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                children: [
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: const Color(0xFFE0E5EC),
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: const [
                          BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                          BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                        ],
                      ),
                      child: TextField(
                        controller: _controller,
                        onSubmitted: (_) => _search(),
                        decoration: const InputDecoration(
                          hintText: 'Medicine name (e.g. Paracetamol)',
                          border: InputBorder.none,
                          contentPadding: EdgeInsets.all(18),
                          prefixIcon: Icon(Icons.medication, color: _themeColor),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  GestureDetector(
                    onTap: _loading ? null : _search,
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: _themeColor,
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: const [
                          BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                        ],
                      ),
                      child: _loading
                          ? const SizedBox(
                              width: 22, height: 22,
                              child: CircularProgressIndicator(
                                  color: Colors.white, strokeWidth: 2))
                          : const Icon(Icons.search, color: Colors.white),
                    ),
                  ),
                ],
              ),
            ),

            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Text(_error,
                    style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
              ),

            Expanded(
              child: _results == null
                  ? const Center(
                      child: Text(
                        'Search to see which pharmacy has your medicine.',
                        style: TextStyle(color: Color(0xFF718096)),
                      ),
                    )
                  : _results!.isEmpty
                      ? const Center(
                          child: Text('No pharmacies found.',
                              style: TextStyle(color: Color(0xFF718096))),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 24),
                          itemCount: _results!.length,
                          itemBuilder: (context, i) {
                            final r = _results![i];
                            final available = r['available'] == true;
                            final subs = List<String>.from(r['substitutes'] as List? ?? const []);
                            return Container(
                              margin: const EdgeInsets.only(bottom: 14),
                              padding: const EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: const Color(0xFFE0E5EC),
                                borderRadius: BorderRadius.circular(16),
                                border: Border(
                                  left: BorderSide(
                                    color: available ? _themeColor : Colors.red.shade400,
                                    width: 6,
                                  ),
                                ),
                                boxShadow: const [
                                  BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                                  BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                                ],
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Expanded(
                                        child: Text(
                                          r['pharmacy_name'] as String? ?? 'Pharmacy',
                                          style: const TextStyle(
                                              fontWeight: FontWeight.bold, fontSize: 17),
                                        ),
                                      ),
                                      Icon(
                                        available ? Icons.check_circle : Icons.cancel,
                                        color: available ? _themeColor : Colors.red,
                                      ),
                                    ],
                                  ),
                                  if (r['address'] != null)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 4),
                                      child: Text(r['address'] as String,
                                          style: const TextStyle(
                                              fontSize: 13, color: Color(0xFF718096))),
                                    ),
                                  const SizedBox(height: 8),
                                  Text(
                                    available
                                        ? 'In stock${r['price'] != null ? ' · ₹${r['price']}' : ''}'
                                        : 'Not available here',
                                    style: TextStyle(
                                      fontWeight: FontWeight.bold,
                                      color: available ? _themeColor : Colors.red,
                                    ),
                                  ),
                                  if (!available && subs.isNotEmpty) ...[
                                    const SizedBox(height: 8),
                                    Container(
                                      padding: const EdgeInsets.all(10),
                                      decoration: BoxDecoration(
                                        color: _themeColor.withOpacity(0.12),
                                        borderRadius: BorderRadius.circular(10),
                                      ),
                                      child: Text(
                                        'Same-effect alternatives: ${subs.join(', ')}',
                                        style: const TextStyle(fontSize: 13),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            );
                          },
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
