import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/sos_service.dart';

/// Emergency contacts management — the numbers alerted by SMS when an SOS
/// cannot reach the server (planning doc requirement).
class EmergencyContactsScreen extends StatefulWidget {
  const EmergencyContactsScreen({super.key});

  @override
  State<EmergencyContactsScreen> createState() => _EmergencyContactsScreenState();
}

class _EmergencyContactsScreenState extends State<EmergencyContactsScreen> {
  List<Map<String, dynamic>> _contacts = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final contacts = await SosService().fetchContacts();
      if (mounted) setState(() => _contacts = contacts);
    } catch (_) {/* offline — show empty state */} finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addDialog() async {
    final s = context.read<LocaleService>();
    final name = TextEditingController();
    final phone = TextEditingController();
    final relation = TextEditingController();

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(s.t('add_contact')),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: name, decoration: InputDecoration(labelText: s.t('name'))),
          TextField(controller: phone, keyboardType: TextInputType.phone,
              decoration: InputDecoration(labelText: s.t('phone'))),
          TextField(controller: relation, decoration: InputDecoration(labelText: s.t('relation'))),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(s.t('cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(s.t('save'))),
        ],
      ),
    );
    if (ok == true && name.text.trim().isNotEmpty && phone.text.trim().length >= 5) {
      try {
        await SosService().addContact(name.text.trim(), phone.text.trim(), relation.text.trim());
        await _load();
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(s.t('search_failed'))));
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<LocaleService>();
    return Scaffold(
      backgroundColor: const Color(0xFFE0E5EC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2D3748)),
          onPressed: () => context.pop(),
        ),
        title: Text(s.t('emergency_contacts'),
            style: const TextStyle(color: Color(0xFF2D3748), fontWeight: FontWeight.bold)),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addDialog,
        backgroundColor: const Color(0xFFEF4444),
        child: const Icon(Icons.person_add, color: Colors.white),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _contacts.isEmpty
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text(s.t('no_contacts'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Color(0xFF718096), fontSize: 16)),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(24),
                  itemCount: _contacts.length,
                  itemBuilder: (context, i) {
                    final c = _contacts[i];
                    return Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE0E5EC),
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: const [
                          BoxShadow(color: Color(0xFFA3B1C6), offset: Offset(4, 4), blurRadius: 8),
                          BoxShadow(color: Color(0xFFFFFFFF), offset: Offset(-4, -4), blurRadius: 8),
                        ],
                      ),
                      child: ListTile(
                        leading: const CircleAvatar(
                          backgroundColor: Color(0xFFEF4444),
                          child: Icon(Icons.contact_phone, color: Colors.white, size: 20),
                        ),
                        title: Text(c['name'] as String? ?? '',
                            style: const TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: Text('${c['phone']}${c['relation'] != null ? ' • ${c['relation']}' : ''}'),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                          onPressed: () async {
                            await SosService().deleteContact(c['id'] as int);
                            await _load();
                          },
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
