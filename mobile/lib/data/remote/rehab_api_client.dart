import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../../core/constants/app_constants.dart';
import '../models/daily_record_request.dart';
import '../models/prescription_model.dart';

class RehabApiClient {
  RehabApiClient({
    required this.baseUrl,
    http.Client? httpClient,
  }) : _httpClient = httpClient ?? http.Client();

  final String baseUrl;
  final http.Client _httpClient;

  Future<PrescriptionModel> fetchPrescription(String userId) async {
    final response = await _httpClient.get(
      Uri.parse('$baseUrl/api/prescription/$userId'),
      headers: {'Content-Type': 'application/json'},
    );

    if (response.statusCode != 200) {
      throw Exception('获取处方失败: ${response.statusCode}');
    }

    final jsonMap = jsonDecode(response.body) as Map<String, dynamic>;
    return PrescriptionModel.fromJson(jsonMap);
  }

  Future<void> submitDailyRecord(DailyRecordRequest request) async {
    final response = await _httpClient.post(
      Uri.parse('$baseUrl/api/daily_record'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(request.toJson()),
    );

    if (response.statusCode != 201) {
      throw Exception('提交训练记录失败: ${response.statusCode}');
    }
  }
}

final rehabApiClientProvider = Provider<RehabApiClient>((ref) {
  return RehabApiClient(baseUrl: AppConstants.apiBaseUrl);
});
