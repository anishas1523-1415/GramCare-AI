import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../services/app_strings.dart';
import '../services/pharmacy_service.dart';
import '../theme.dart';

/// Add-new-item flow: POST /pharmacy/items. Includes an invoice-photo
/// capture option (image_picker) per the planning doc's restocking flow.
///
/// SCOPING NOTE: this does NOT run on-device OCR on the captured photo. The
/// patient app's prescription scanner sends its photo to a backend OCR
/// endpoint (/prescriptions/scan or similar) that is specific to
/// prescription documents, not pharmacy invoices — there is no equivalent
/// invoice-OCR endpoint in apps/backend_service today, and adding one would
/// be well beyond a "minimal endpoint" (it needs an invoice-layout parser,
/// not just a route). So this screen lets the pharmacist snap the invoice
/// photo for their own reference while on this form, then key in the
/// medicine name/price/count/expiry/batch themselves — still much faster
/// than writing it into a paper ledger first.
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

  Future<void> _captureInvoicePhoto() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 80);
    if (photo != null) {
      setState(() => _invoicePhoto = photo);
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
              Text(locale.t('invoice_photo_note'), style: const TextStyle(fontSize: 12, color: Colors.black54)),
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
