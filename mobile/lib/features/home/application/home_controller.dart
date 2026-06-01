import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/models/prescription_model.dart';
import '../../../data/remote/rehab_api_client.dart';

@immutable
class HomeState {
  const HomeState({
    this.isLoading = false,
    this.prescription,
    this.painScore = 4,
    this.errorMessage,
  });

  final bool isLoading;
  final PrescriptionModel? prescription;
  final int painScore;
  final String? errorMessage;

  HomeState copyWith({
    bool? isLoading,
    PrescriptionModel? prescription,
    int? painScore,
    Object? errorMessage = _sentinel,
  }) {
    return HomeState(
      isLoading: isLoading ?? this.isLoading,
      prescription: prescription ?? this.prescription,
      painScore: painScore ?? this.painScore,
      errorMessage: identical(errorMessage, _sentinel)
          ? this.errorMessage
          : errorMessage as String?,
    );
  }
}

const _sentinel = Object();

class HomeController extends StateNotifier<HomeState> {
  HomeController(this._apiClient) : super(const HomeState());

  final RehabApiClient _apiClient;

  Future<void> initialize(String userId) async {
    state = state.copyWith(isLoading: true, errorMessage: null);

    try {
      final prescription = await _apiClient.fetchPrescription(userId);
      state = state.copyWith(
        isLoading: false,
        prescription: prescription,
        errorMessage: null,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  void updatePainScore(double value) {
    state = state.copyWith(painScore: value.round());
  }
}

final homeControllerProvider =
    StateNotifierProvider<HomeController, HomeState>((ref) {
  return HomeController(ref.read(rehabApiClientProvider));
});
