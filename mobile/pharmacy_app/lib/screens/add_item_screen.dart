import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/api_service.dart';
import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// Add-new-item flow: POST /pharmacy/items. Includes an invoice-photo
/// capture option (image_picker) per the planning doc's restocking flow.
///
/// The captured photo is read by POST /triage/ocr, the same endpoint the
/// web pharmacist portal's invoice scanner uses (and the patient app's
/// prescription scanner — see OCRResponse's own docstring, which names both
/// callers). Recognised medicine names are offered as a one-tap fill for the
/// name field; everything else is still keyed in, since an invoice's price,
/// count, expiry and batch vary too much in layout to trust to OCR.
///
/// This previously only stored the photo for the pharmacist's own reference
/// on the assumption that no invoice-OCR endpoint existed. It did — the web
/// portal was already using it — so the phone was making pharmacists type
/// what the browser filled in for them.
class AddItemScreen extends StatefulWidget {
  const AddItemScreen({super.key});

  @override
  State<AddItemScreen> createState() => _AddItemScreenState();
}

class _AddItemScreenState extends State<AddItemScreen> {
  final _service = PharmacyService();
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _genericController = TextEditingController();
  final _priceController = TextEditingController();
  final _stockController = TextEditingController();
  final _expiryController = TextEditingController();
  final _batchController = TextEditingController();
  bool _requiresPrescription = false;
  bool _saving = false;
  XFile? _invoicePhoto;
  bool _scanning = false;
  List<String> _parsedMedicines = [];
  String? _ocrError;

  Future<void> _captureInvoicePhoto() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);
    if (photo == null) return;
    setState(() {
      _invoicePhoto = photo;
      _parsedMedicines = [];
      _ocrError = null;
      _scanning = true;
    });

    try {
      final bytes = await File(photo.path).readAsBytes();
      final res = await ApiService().client.post('/triage/ocr', data: {
        'image_base64': base64Encode(bytes),
      });
      final parsed = ((res.data as Map)['medicines_parsed'] as List? ?? [])
          .map((e) => e.toString())
          .where((e) => e.trim().isNotEmpty)
          .toList();
      if (!mounted) return;
      setState(() {
        _parsedMedicines = parsed;
        _scanning = false;
        // Sole match: fill it straight in. Several: let the pharmacist pick,
        // since one invoice legitimately lists many medicines.
        if (parsed.length == 1 && _nameController.text.trim().isEmpty) {
          _nameController.text = parsed.first;
        }
      });
    } catch (_) {
      if (!mounted) return;
      // Never blocks the form — the pharmacist can always type it in.
      setState(() {
        _scanning = false;
        _ocrError = context.read<LocaleService>().t('invoice_scan_failed');
      });
    }
  }

  Future<void> _pickExpiryDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime(now.year + 1),
      firstDate: now,
      lastDate: DateTime(now.year + 10),
    );
    if (picked != null) {
      _expiryController.text =
          '${picked.year.toString().padLeft(4, '0')}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
    }
  }

  Future<void> _save(LocaleService locale) async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await _service.addItem(
        medicineName: _nameController.text.trim(),
        genericGroup: _genericController.text.trim(),
        stockCount: int.parse(_stockController.text.trim()),
        price: double.parse(_priceController.text.trim()),
        requiresPrescription: _requiresPrescription,
        expiryDate: _expiryController.text.trim(),
        batchNumber: _batchController.text.trim(),
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(locale.t('error_generic'))));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final locale = context.watch<LocaleService>();
    return Scaffold(
      appBar: AppBar(title: Text(locale.t('add_item'))),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            OutlinedButton.icon(
              onPressed: _captureInvoicePhoto,
              icon: const Icon(Icons.camera_alt),
              label: Text(locale.t('capture_invoice_photo')),
            ),
            if (_invoicePhoto != null) ...[
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.file(File(_invoicePhoto!.path), height: 160, fit: BoxFit.cover),
              ),
              const SizedBox(height: 6),
              if (_scanning)
                Row(children: [
                  const SizedBox(
                      height: 14, width: 14, child: CircularProgressIndicator(strokeWidth: 2)),
                  const SizedBox(width: 8),
                  Text(locale.t('invoice_scanning'),
                      style: const TextStyle(fontSize: 12, color: Colors.black54)),
                ])
              else if (_ocrError != null)
                Text(_ocrError!, style: const TextStyle(fontSize: 12, color: Colors.red))
              else if (_parsedMedicines.isNotEmpty) ...[
                Text(locale.t('invoice_medicines_found'),
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: _parsedMedicines
                      .map((m) => ActionChip(
                            label: Text(m, style: const TextStyle(fontSize: 12)),
                            onPressed: () => setState(() => _nameController.text = m),
                          ))
                      .toList(),
                ),
              ] else
                Text(locale.t('invoice_photo_note'),
                    style: const TextStyle(fontSize: 12, color: Colors.black54)),
            ],
            const SizedBox(height: 20),
            TextFormField(
              controller: _nameController,
              decoration: InputDecoration(labelText: locale.t('medicine_name')),
              validator: (v) => (v == null || v.trim().isEmpty) ? locale.t('medicine_name') : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _genericController,
              decoration: InputDecoration(labelText: locale.t('generic_group')),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _priceController,
              decoration: InputDecoration(labelText: locale.t('price')),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              validator: (v) => (v == null || double.tryParse(v.trim()) == null) ? locale.t('price') : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _stockController,
              decoration: InputDecoration(labelText: locale.t('initial_stock')),
              keyboardType: TextInputType.number,
              validator: (v) => (v == null || int.tryParse(v.trim()) == null) ? locale.t('initial_stock') : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _expiryController,
              readOnly: true,
              onTap: _pickExpiryDate,
              decoration: InputDecoration(labelText: locale.t('expiry_date'), suffixIcon: const Icon(Icons.calendar_today)),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _batchController,
              decoration: InputDecoration(labelText: locale.t('batch_number')),
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              value: _requiresPrescription,
              onChanged: (v) => setState(() => _requiresPrescription = v),
              title: Text(locale.t('requires_prescription')),
              activeThumbColor: PharmacyTheme.primaryGreen,
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _saving ? null : () => _save(locale),
              child: _saving
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : Text(locale.t('save')),
            ),
          ],
        ),
      ),
    );
  }
}
