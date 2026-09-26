import 'package:hive_flutter/hive_flutter.dart';

import 'secure_store.dart';

/// Every Hive box in the app is opened through here.
///
/// Health records, reminders and the cached profile all hold clinical data,
/// so each box is opened with the AES cipher keyed from the platform secure
/// store. Calling `Hive.openBox` directly is what previously left the
/// health wallet unencrypted whenever a background sync opened it before
/// `main()` did — Hive returns the already-open box, cipher or not.
class EncryptedBoxes {
  static Future<Box<T>> open<T>(String name) async {
    if (Hive.isBoxOpen(name)) return Hive.box<T>(name);
    final key = await SecureStore().getOrCreateHiveKey();
    return Hive.openBox<T>(name, encryptionCipher: HiveAesCipher(key));
  }

  static Future<Box> openDynamic(String name) async {
    if (Hive.isBoxOpen(name)) return Hive.box(name);
    final key = await SecureStore().getOrCreateHiveKey();
    return Hive.openBox(name, encryptionCipher: HiveAesCipher(key));
  }
}
