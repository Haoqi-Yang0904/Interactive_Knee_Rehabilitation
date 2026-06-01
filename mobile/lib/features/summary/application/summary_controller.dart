import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/daily_record_request.dart';
import '../../../data/models/training_result.dart';
import '../../../data/remote/rehab_api_client.dart';

@immutable
class SummaryState {
  const SummaryState({
    this.isSubmitting = false,
    this.errorMessage,
  });

  final bool isSubmitting;
  final String? errorMessage;

  SummaryState copyWith({
    bool? isSubmitting,
    Object? errorMessage = _summarySentinel,
  }) {
    return SummaryState(
      isSubmitting: isSubmitting ?? this.isSubmitting,
      errorMessage: identical(errorMessage, _summarySentinel)
          ? this.errorMessage
          : errorMessage as String?,
    );
  }
}

const _summarySentinel = Object();

class SummaryController extends StateNotifier<SummaryState> {
  SummaryController(this._apiClient) : super(const SummaryState());

  final RehabApiClient _apiClient;

  Future<bool> submit(TrainingResult result) async {
    state = state.copyWith(isSubmitting: true, errorMessage: null);

    try {
      final request = DailyRecordRequest.fromTrainingResult(result);
      await _apiClient.submitDailyRecord(request);
      state = state.copyWith(isSubmitting: false, errorMessage: null);
      return true;
    } catch (e) {
      state = state.copyWith(
        isSubmitting: false,
        errorMessage: e.toString(),
      );
      return false;
    }
  }
}

final summaryControllerProvider =
    StateNotifierProvider<SummaryController, SummaryState>((ref) {
  return SummaryController(ref.read(rehabApiClientProvider));
});
