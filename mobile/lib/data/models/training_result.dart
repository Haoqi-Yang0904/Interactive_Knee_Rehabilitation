import '../../core/utils/angle_calculator.dart';

class ExerciseTrainingResult {
  const ExerciseTrainingResult({
    required this.exerciseId,
    required this.exerciseName,
    required this.evaluationMode,
    required this.completedUnits,
    required this.targetUnits,
    required this.achievementRate,
    required this.feedback,
    this.bestAngle,
  });

  final String exerciseId;
  final String exerciseName;
  final String evaluationMode;
  final int completedUnits;
  final int targetUnits;
  final double achievementRate;
  final String feedback;
  final double? bestAngle;
}

class TrainingResult {
  const TrainingResult({
    required this.userId,
    required this.actionName,
    required this.painScore,
    required this.completedSets,
    required this.targetSets,
    required this.targetAngle,
    required this.achievementRate,
    required this.maxFlexionAngle,
    required this.lowestInteriorAngle,
    this.exerciseResults = const [],
    this.completedExercises = 0,
    this.totalExercises = 1,
    this.effectSummary = '',
  });

  final String userId;
  final String actionName;
  final int painScore;
  final int completedSets;
  final int targetSets;
  final double targetAngle;
  final double achievementRate;
  final double maxFlexionAngle;
  final double? lowestInteriorAngle;
  final List<ExerciseTrainingResult> exerciseResults;
  final int completedExercises;
  final int totalExercises;
  final String effectSummary;

  factory TrainingResult.fromSession({
    required String userId,
    required String actionName,
    required int painScore,
    required int completedSets,
    required int targetSets,
    required double targetAngle,
    required double? deepestInteriorAngle,
  }) {
    final safeInteriorAngle = deepestInteriorAngle ?? 180.0;
    final maxFlexionAngle = deepestInteriorAngle == null
        ? 0.0
        : AngleCalculator.toClinicalFlexion(safeInteriorAngle);

    final targetFlexionAngle = 180.0 - targetAngle;

    final setRate = targetSets <= 0
        ? 0.0
        : ((completedSets / targetSets).clamp(0.0, 1.0) as num).toDouble();

    // MVP 阶段这里使用一个简单、可解释的达标率算法：
    // 60% 来源于完成组数，40% 来源于是否达到目标弯曲幅度。
    // 这样既能满足总结页展示，也能避免在实时推理回调里做复杂统计。
    final angleRate = targetFlexionAngle <= 0
        ? 0.0
        : ((maxFlexionAngle / targetFlexionAngle).clamp(0.0, 1.0) as num)
            .toDouble();

    final achievementRate = ((setRate * 0.6) + (angleRate * 0.4)) * 100.0;

    return TrainingResult(
      userId: userId,
      actionName: actionName,
      painScore: painScore,
      completedSets: completedSets,
      targetSets: targetSets,
      targetAngle: targetAngle,
      achievementRate: achievementRate,
      maxFlexionAngle: maxFlexionAngle.clamp(0.0, 180.0),
      lowestInteriorAngle: deepestInteriorAngle,
      completedExercises: completedSets >= targetSets ? 1 : 0,
      totalExercises: 1,
      effectSummary: achievementRate >= 80
          ? '本次训练完成度较好，继续保持动作质量。'
          : '本次训练仍有未完成部分，建议下次降低速度、优先保证标准动作。',
    );
  }

  factory TrainingResult.fromExerciseResults({
    required String userId,
    required String actionName,
    required int painScore,
    required List<ExerciseTrainingResult> exerciseResults,
    required double? deepestInteriorAngle,
  }) {
    final totalExercises = exerciseResults.length;
    final completedExercises = exerciseResults
        .where((item) => item.completedUnits >= item.targetUnits)
        .length;

    final weightedUnits = exerciseResults.fold<int>(
      0,
      (sum, item) => sum + (item.targetUnits <= 0 ? 1 : item.targetUnits),
    );
    final achievementRate = weightedUnits == 0
        ? 0.0
        : exerciseResults.fold<double>(0.0, (sum, item) {
            final weight = item.targetUnits <= 0 ? 1 : item.targetUnits;
            final rate =
                (item.achievementRate.clamp(0.0, 100.0) as num).toDouble();
            return sum + (rate * weight);
          }) /
            weightedUnits;

    final maxFlexionAngle = deepestInteriorAngle == null
        ? 0.0
        : AngleCalculator.toClinicalFlexion(deepestInteriorAngle);

    final effectSummary = _buildEffectSummary(
      achievementRate: achievementRate,
      completedExercises: completedExercises,
      totalExercises: totalExercises,
    );

    return TrainingResult(
      userId: userId,
      actionName: actionName,
      painScore: painScore,
      completedSets: completedExercises,
      targetSets: totalExercises,
      targetAngle: 0,
      achievementRate: achievementRate,
      maxFlexionAngle: maxFlexionAngle.clamp(0.0, 180.0),
      lowestInteriorAngle: deepestInteriorAngle,
      exerciseResults: exerciseResults,
      completedExercises: completedExercises,
      totalExercises: totalExercises,
      effectSummary: effectSummary,
    );
  }
}

String _buildEffectSummary({
  required double achievementRate,
  required int completedExercises,
  required int totalExercises,
}) {
  if (totalExercises == 0) {
    return '本次没有记录到有效训练动作。';
  }

  if (achievementRate >= 90) {
    return '本次训练整体完成度很好，动作序列基本达标。';
  }

  if (achievementRate >= 70) {
    return '本次训练完成大部分目标，后续重点补足未达标动作并保持动作质量。';
  }

  if (completedExercises > 0) {
    return '本次训练完成了部分动作，但整体完成量不足，建议分段训练并降低疲劳累积。';
  }

  return '本次训练未达到有效完成标准，建议重新检查摄像头站位、疼痛状态和动作理解。';
}
