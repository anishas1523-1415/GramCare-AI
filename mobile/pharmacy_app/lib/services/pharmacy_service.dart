import 'package:dio/dio.dart';

import '../models/prescription.dart';
import '../models/stock_item.dart';
import 'api_service.dart';
import 'offline_cache.dart';

/// Thin wrapper around apps/backend_service/modules/pharmacy_inventory/router.py
/// (mounted at /api/v1/pharmacy — see main.dart's include_router prefix in the
/// backend). Every method here maps 1:1 to an endpoint read from that file.
class PharmacyService {
  final _dio = ApiService().client;

  /// When the most recent read on this instance was served from the offline
  /// cache, this holds the age of that data ("2h ago"); null when the data
  /// came from the network. Screens read it to show the offline banner.
  String? servedFromCacheAge;

  /// Runs a GET that stays useful without connectivity: the response is
  /// cached on success, and a network failure falls back to the last cached
  /// copy rather than an error screen. A server-side failure (4xx/5xx) is
  /// still raised — a 409 "no pharmacy registered" or a 401 means something
  /// the pharmacist has to act on, and hiding it behind stale data would be
  /// worse than showing it.
  Future<T> _cachedGet<T>(
    String cacheKey,
    String path, {
    Map<String, dynamic>? queryParameters,
    required T Function(dynamic payload) parse,
  }) async {
    try {
      final res = await _dio.get(path, queryParameters: queryParameters);
      await OfflineCache().save(cacheKey, res.data);
      servedFromCacheAge = null;
      return parse(res.data);
    } on DioException catch (e) {
      if (e.response != null) rethrow;
      final cached = await OfflineCache().read(cacheKey);
      if (cached == null) rethrow;
      servedFromCacheAge = cached.ageLabel;
      return parse(cached.payload);
    }
  }

  /// GET /pharmacy/me -> schemas.PharmacyResponse. Throws a DioException
  /// with statusCode 409 ("No pharmacy registered for this account yet.")
  /// for any account that has never called registerPharmacy() below — every
  /// screen in this app depends on this succeeding, so callers should treat
  /// a 409 here as "needs onboarding", not a generic error.
  Future<Map<String, dynamic>> getMyPharmacy() async {
    final res = await _dio.get('/pharmacy/me');
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// POST /pharmacy/register — creates (or updates) the Pharmacy business
  /// entity for the current account. A PHARMACIST user account alone isn't
  /// enough to use this app: every other endpoint (/stock, /queue,
  /// /expiring, /me itself) looks up a Pharmacy row by owner_user_id and
  /// 409s if one doesn't exist yet. Previously nothing in this app ever
  /// called this endpoint, so a newly-registered pharmacist had no way to
  /// get past that 409 — every screen was a permanent dead end.
  Future<Map<String, dynamic>> registerPharmacy({
    required String name,
    String? address,
    String? phone,
    double? lat,
    double? lng,
  }) async {
    final res = await _dio.post('/pharmacy/register', data: {
      'name': name,
      if (address != null && address.isNotEmpty) 'address': address,
      if (phone != null && phone.isNotEmpty) 'phone': phone,
      if (lat != null) 'lat': lat,
      if (lng != null) 'lng': lng,
    });
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// GET /pharmacy/stock -> List[_item_response(...)]
  Future<List<StockItem>> getStock() async {
    return _cachedGet(
      'stock',
      '/pharmacy/stock',
      parse: (payload) => (payload as List<dynamic>)
          .map((e) => StockItem.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }

  /// POST /pharmacy/items — add a new item, or restock an existing one
  /// (backend merges by case-insensitive medicine_name; router.py:141-177).
  Future<StockItem> addItem({
    required String medicineName,
    String? genericGroup,
    required int stockCount,
    required double price,
    required bool requiresPrescription,
    String? expiryDate, // yyyy-MM-dd
    String? batchNumber,
  }) async {
    final res = await _dio.post('/pharmacy/items', data: {
      'medicine_name': medicineName,
      if (genericGroup != null && genericGroup.isNotEmpty) 'generic_group': genericGroup,
      'stock_count': stockCount,
      'price': price,
      'requires_prescription': requiresPrescription,
      if (expiryDate != null && expiryDate.isNotEmpty) 'expiry_date': expiryDate,
      if (batchNumber != null && batchNumber.isNotEmpty) 'batch_number': batchNumber,
    });
    return StockItem.fromJson(Map<String, dynamic>.from(res.data as Map));
  }

  /// POST /pharmacy/update_stock/{id}?quantity_added=N — shipment delta
  /// (positive) or correction (negative). router.py:195-215.
  Future<int> updateStock(int medicineId, int quantityAdded) async {
    final res = await _dio.post(
      '/pharmacy/update_stock/$medicineId',
      queryParameters: {'quantity_added': quantityAdded},
    );
    return (res.data as Map)['id'] as int;
  }

  /// POST /pharmacy/set_stock/{id}?count=N — absolute end-of-day count.
  /// router.py:218-230.
  Future<void> setStock(int medicineId, int count) async {
    await _dio.post(
      '/pharmacy/set_stock/$medicineId',
      queryParameters: {'count': count},
    );
  }

  /// POST /pharmacy/decrement/{id}?count=N — tap-to-decrement sale logging.
  /// router.py:233-244. Returns the new remaining count from the response
  /// message so the caller doesn't need a second round trip.
  Future<int> decrementStock(int medicineId, {int count = 1}) async {
    final res = await _dio.post(
      '/pharmacy/decrement/$medicineId',
      queryParameters: {'count': count},
    );
    final data = Map<String, dynamic>.from(res.data as Map);
    final message = data['message'] as String? ?? '';
    final match = RegExp(r'Remaining:\s*(\d+)').firstMatch(message);
    return match != null ? int.parse(match.group(1)!) : 0;
  }

  /// GET /pharmacy/expiring?days=N -> orange-coded expiry list, soonest first
  /// (already sorted server-side by expiry_date; router.py:247-271).
  Future<List<StockItem>> getExpiring({int days = 90}) async {
    return _cachedGet(
      'expiring_$days',
      '/pharmacy/expiring',
      queryParameters: {'days': days},
      parse: (payload) => (payload as List<dynamic>)
          .map((e) => StockItem.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }

  /// GET /pharmacy/queue -> List[schemas.PrescriptionResponse], unfulfilled
  /// prescriptions newest first (router.py:278-290).
  Future<List<PrescriptionQueueItem>> getQueue() async {
    return _cachedGet(
      'queue',
      '/pharmacy/queue',
      parse: (payload) => (payload as List<dynamic>)
          .map((e) => PrescriptionQueueItem.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }

  /// PUT /pharmacy/fulfill/{id} — no request body (router.py:293-346).
  /// Response includes stock_decremented / not_in_your_stock name lists.
  Future<Map<String, dynamic>> fulfillPrescription(int prescriptionId) async {
    final res = await _dio.put('/pharmacy/fulfill/$prescriptionId');
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// GET /pharmacy/substitutes?medicine=NAME -> [{name, price}, ...],
  /// cheapest first (router.py:353-384).
  Future<List<Map<String, dynamic>>> getSubstitutes(String medicineName) async {
    try {
      final res = await _dio.get('/pharmacy/substitutes', queryParameters: {'medicine': medicineName});
      return (res.data as List<dynamic>)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    } catch (_) {
      // Substitute suggestions are a nice-to-have inline hint — never let a
      // lookup failure block viewing/fulfilling the queue item itself.
      return [];
    }
  }
}
