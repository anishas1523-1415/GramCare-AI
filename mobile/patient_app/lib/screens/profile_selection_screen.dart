import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../models/family_profile.dart';
import '../services/profile_service.dart';
import '../theme/neumorphic_colors.dart';

/// "Who is this for?" — big, tappable member buttons per the planning doc:
/// one box per family member, avatar-first so low-literacy users can pick by
/// face/color rather than by reading.
class ProfileSelectionScreen extends StatefulWidget {
  const ProfileSelectionScreen({super.key});

  @override
  State<ProfileSelectionScreen> createState() => _ProfileSelectionScreenState();
}

class _ProfileSelectionScreenState extends State<ProfileSelectionScreen> {
  @override
  void initState() {
    super.initState();
    // Refresh from API (falls back to offline cache inside the service)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProfileService>().load();
    });
  }

  Color _tagColor(FamilyProfile? p) {
    if (p?.colorTag != null && p!.colorTag!.startsWith('#') && p.colorTag!.length == 7) {
      return Color(int.parse('FF${p.colorTag!.substring(1)}', radix: 16));
    }
    return const Color(0xFF4F46E5);
  }

  Widget _bigAvatarButton({
    required BuildContext context,
    required String label,
    required String sublabel,
    required Widget avatar,
    required bool selected,
    required VoidCallback onTap,
  }) {
    final neu = Theme.of(context).extension<NeumorphicColors>()!;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: neu.background,
          borderRadius: BorderRadius.circular(20),
          border: selected ? Border.all(color: const Color(0xFF2DD4BF), width: 3) : null,
          boxShadow: [
            BoxShadow(color: neu.shadowDark, offset: const Offset(4, 4), blurRadius: 8),
            BoxShadow(color: neu.shadowLight, offset: const Offset(-4, -4), blurRadius: 8),
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            avatar,
            const SizedBox(height: 12),
            Text(
              label,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: neu.foreground),
            ),
            const SizedBox(height: 4),
            Text(
              sublabel,
              style: TextStyle(fontSize: 12, color: neu.foregroundMuted),
            ),
            if (selected) ...[
              const SizedBox(height: 8),
              const Icon(Icons.check_circle, color: Color(0xFF2DD4BF), size: 22),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final service = context.watch<ProfileService>();
    final neu = Theme.of(context).extension<NeumorphicColors>()!;

    return Scaffold(
      backgroundColor: neu.background,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: neu.foreground),
          onPressed: () => context.pop(),
        ),
        title: Text(
          'Who is this for?',
          style: TextStyle(color: neu.foreground, fontWeight: FontWeight.bold),
        ),
      ),
      body: SafeArea(
        child: service.loading
            ? const Center(child: CircularProgressIndicator())
            : GridView.count(
                padding: const EdgeInsets.all(24),
                crossAxisCount: 2,
                mainAxisSpacing: 20,
                crossAxisSpacing: 20,
                children: [
                  // "Myself" — the account owner
                  _bigAvatarButton(
                    context: context,
                    label: 'Myself',
                    sublabel: 'My own health',
                    selected: service.active == null,
                    avatar: const CircleAvatar(
                      radius: 36,
                      backgroundColor: Color(0xFF4F46E5),
                      child: Icon(Icons.person, size: 40, color: Colors.white),
                    ),
                    onTap: () async {
                      await service.setActive(null);
                      if (context.mounted) context.pop();
                    },
                  ),
                  ...service.profiles.map(
                    (p) => _bigAvatarButton(
                      context: context,
                      label: p.fullName,
                      sublabel: '${p.relation} • ${p.age} yrs',
                      selected: service.active?.id == p.id,
                      avatar: CircleAvatar(
                        radius: 36,
                        backgroundColor: _tagColor(p),
                        child: Text(
                          p.initials,
                          style: const TextStyle(
                            fontSize: 26, fontWeight: FontWeight.bold, color: Colors.white),
                        ),
                      ),
                      onTap: () async {
                        await service.setActive(p);
                        if (context.mounted) context.pop();
                      },
                    ),
                  ),
                  // Add-member card
                  GestureDetector(
                    onTap: () => _showAddDialog(context),
                    child: Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: neu.shadowDark, width: 2),
                      ),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.add_circle_outline, size: 48, color: neu.foregroundMuted),
                          const SizedBox(height: 8),
                          Text('Add member', style: TextStyle(color: neu.foregroundMuted, fontWeight: FontWeight.bold)),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Future<void> _showAddDialog(BuildContext context) async {
    final nameCtl = TextEditingController();
    final relationCtl = TextEditingController();
    final ageCtl = TextEditingController();
    String gender = 'Female';

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add family member'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: nameCtl, decoration: const InputDecoration(labelText: 'Full name')),
            TextField(controller: relationCtl, decoration: const InputDecoration(labelText: 'Relation (e.g. Mother)')),
            TextField(controller: ageCtl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Age')),
            StatefulBuilder(
              builder: (ctx2, setSt) => DropdownButton<String>(
                value: gender,
                isExpanded: true,
                items: const [
                  DropdownMenuItem(value: 'Female', child: Text('Female')),
                  DropdownMenuItem(value: 'Male', child: Text('Male')),
                  DropdownMenuItem(value: 'Other', child: Text('Other')),
                ],
                onChanged: (v) => setSt(() => gender = v ?? 'Female'),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.of(ctx).pop(true), child: const Text('Save')),
        ],
      ),
    );

    if (saved == true && context.mounted) {
      final age = int.tryParse(ageCtl.text) ?? 0;
      if (nameCtl.text.trim().isEmpty || relationCtl.text.trim().isEmpty) return;
      try {
        await context.read<ProfileService>().create({
          'full_name': nameCtl.text.trim(),
          'relation': relationCtl.text.trim(),
          'age': age,
          'gender': gender,
        });
      } catch (_) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Could not save member. Are you online?')),
          );
        }
      }
    }
  }
}
