class AppConstants {
  const AppConstants._();

  static const String demoUserId = 'user_001';

  // Android 模拟器请使用 10.0.2.2。
  // iOS 模拟器通常可以使用 127.0.0.1。
  // 真机调试时请改成电脑在局域网中的 IP。
  static const String apiBaseUrl = 'http://10.0.2.2:8000';
}
