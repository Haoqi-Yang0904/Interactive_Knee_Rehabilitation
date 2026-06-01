import 'training_result.dart';

class DailyRecordRequest {
  const DailyRecordRequest({
    required this.userId,
    required this.actionName,
    required this.painScore,
    required this.achievementRate,
    required this.maxFlexionAngle,
    required this.completedSets,
  });

  final String userId;
  final String actionName;
  final int painScore;
  final double achievementRate;
  final double maxFlexionAngle;
  final int completedSets;

  factory DailyRecordRequest.fromTrainingResult(TrainingResult result) {
    return DailyRecordRequest(
      userId: result.userId,
      actionName: result.actionName,
      painScore: result.painScore,
      achievementRate: result.achievementRate,
      maxFlexionAngle: result.maxFlexionAngle,
      completedSets: result.completedSets,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'action_name': actionName,
      'pain_score': painScore,
      'achievement_rate': achievementRate,
      'max_flexion_angle': maxFlexionAngle,
      'completed_sets': completedSets,
    };
  }
}
