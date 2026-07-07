/// Mirrors the shape returned by GET /pharmacy/stock, POST /pharmacy/items,
/// etc. — see _item_response() in
/// apps/backend_service/modules/pharmacy_inventory/router.py:69-81 and
/// schemas.PharmacyItemResponse (apps/backend_service/schemas.py:251-256).
class StockItem {
  final int id;
  final int? pharmacyId;
  final String medicineName;
  final String? genericGroup;
  final int stockCount;
  final double price;
  final bool requiresPrescription;
  final String? expiryDate; // ISO yyyy-MM-dd, nullable
  final String? batchNumber;
  final String status; // "Optimal" | "Low" | "Out of Stock" (backend-computed)
  final int? daysLeft; // only present on GET /pharmacy/expiring rows

  StockItem({
    required this.id,
    this.pharmacyId,
    required this.medicineName,
    this.genericGroup,
    required this.stockCount,
    required this.price,
    required this.requiresPrescription,
    this.expiryDate,
    this.batchNumber,
    required this.status,
    this.daysLeft,
  });

  factory StockItem.fromJson(Map<String, dynamic> json) {
    return StockItem(
      id: json['id'] as int,
      pharmacyId: json['pharmacy_id'] as int?,
      medicineName: json['medicine_name'] as String? ?? '',
      genericGroup: json['generic_group'] as String?,
      stockCount: json['stock_count'] as int? ?? 0,
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      requiresPrescription: json['requires_prescription'] as bool? ?? false,
      expiryDate: json['expiry_date'] as String?,
      batchNumber: json['batch_number'] as String?,
      status: json['status'] as String? ?? 'Optimal',
      daysLeft: json['days_left'] as int?,
    );
  }

  StockItem copyWith({int? stockCount, String? status}) {
    return StockItem(
      id: id,
      pharmacyId: pharmacyId,
      medicineName: medicineName,
      genericGroup: genericGroup,
      stockCount: stockCount ?? this.stockCount,
      price: price,
      requiresPrescription: requiresPrescription,
      expiryDate: expiryDate,
      batchNumber: batchNumber,
      status: status ?? this.status,
      daysLeft: daysLeft,
    );
  }
}
