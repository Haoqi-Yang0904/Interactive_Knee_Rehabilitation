class PrescriptionModel {
  const PrescriptionModel({
    required this.userId,
    required this.actionName,
    required this.targetSets,
    required this.targetAngle,
    required this.holdSeconds,
    required this.frequencyNote,
    required this.caution,
    required this.source,
    this.rehabPlan,
  });

  final String userId;
  final String actionName;
  final int targetSets;
  final double targetAngle;
  final int holdSeconds;
  final String frequencyNote;
  final String caution;
  final String source;
  final KneeRehabPlanModel? rehabPlan;

  factory PrescriptionModel.fromJson(Map<String, dynamic> json) {
    return PrescriptionModel(
      userId: json['user_id'] as String,
      actionName: json['action_name'] as String,
      targetSets: json['target_sets'] as int,
      targetAngle: (json['target_angle'] as num).toDouble(),
      holdSeconds: json['hold_seconds'] as int,
      frequencyNote: json['frequency_note'] as String,
      caution: json['caution'] as String,
      source: json['source'] as String,
      rehabPlan: json['rehab_plan'] == null
          ? null
          : KneeRehabPlanModel.fromJson(
              json['rehab_plan'] as Map<String, dynamic>,
            ),
    );
  }
}

class KneeRehabPlanModel {
  const KneeRehabPlanModel({
    required this.planId,
    required this.userId,
    required this.title,
    required this.phase,
    required this.intensityNote,
    required this.educationNotes,
    required this.sections,
    required this.globalStopRules,
  });

  final String planId;
  final String userId;
  final String title;
  final String phase;
  final String intensityNote;
  final List<String> educationNotes;
  final List<RehabPlanSectionModel> sections;
  final List<String> globalStopRules;

  factory KneeRehabPlanModel.fromJson(Map<String, dynamic> json) {
    return KneeRehabPlanModel(
      planId: json['plan_id'] as String,
      userId: json['user_id'] as String,
      title: json['title'] as String,
      phase: json['phase'] as String,
      intensityNote: json['intensity_note'] as String,
      educationNotes: _stringList(json['education_notes']),
      sections: ((json['sections'] as List?) ?? const <dynamic>[])
          .map(
            (item) => RehabPlanSectionModel.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
      globalStopRules: _stringList(json['global_stop_rules']),
    );
  }
}

class RehabPlanSectionModel {
  const RehabPlanSectionModel({
    required this.id,
    required this.title,
    required this.purpose,
    required this.exercises,
  });

  final String id;
  final String title;
  final String purpose;
  final List<RehabExerciseModel> exercises;

  factory RehabPlanSectionModel.fromJson(Map<String, dynamic> json) {
    return RehabPlanSectionModel(
      id: json['id'] as String,
      title: json['title'] as String,
      purpose: json['purpose'] as String,
      exercises: ((json['exercises'] as List?) ?? const <dynamic>[])
          .map(
            (item) => RehabExerciseModel.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }
}

class RehabExerciseModel {
  const RehabExerciseModel({
    required this.id,
    required this.name,
    required this.category,
    required this.purpose,
    required this.startRule,
    required this.status,
    required this.evaluationMode,
    required this.dose,
    required this.standard,
    required this.execution,
    required this.assessment,
    required this.voiceCues,
    required this.contraindications,
    required this.stopRules,
  });

  final String id;
  final String name;
  final String category;
  final String purpose;
  final String startRule;
  final String status;
  final String evaluationMode;
  final ExerciseDoseModel dose;
  final List<String> standard;
  final List<String> execution;
  final List<String> assessment;
  final List<String> voiceCues;
  final List<String> contraindications;
  final List<String> stopRules;

  factory RehabExerciseModel.fromJson(Map<String, dynamic> json) {
    return RehabExerciseModel(
      id: json['id'] as String,
      name: json['name'] as String,
      category: json['category'] as String,
      purpose: json['purpose'] as String,
      startRule: json['start_rule'] as String,
      status: json['status'] as String,
      evaluationMode: json['evaluation_mode'] as String,
      dose: ExerciseDoseModel.fromJson(json['dose'] as Map<String, dynamic>),
      standard: _stringList(json['standard']),
      execution: _stringList(json['execution']),
      assessment: _stringList(json['assessment']),
      voiceCues: _stringList(json['voice_cues']),
      contraindications: _stringList(json['contraindications']),
      stopRules: _stringList(json['stop_rules']),
    );
  }
}

class ExerciseDoseModel {
  const ExerciseDoseModel({
    this.targetDailyCycles,
    this.sessionTargetCycles,
    this.sessionTargetReps,
    this.repsPerSet,
    this.setsPerDayMin,
    this.setsPerDayMax,
    this.contractionSeconds,
    this.relaxSeconds,
    this.holdStrategy,
    this.restBetweenSetsSeconds,
    required this.frequencyNote,
  });

  final int? targetDailyCycles;
  final int? sessionTargetCycles;
  final int? sessionTargetReps;
  final int? repsPerSet;
  final int? setsPerDayMin;
  final int? setsPerDayMax;
  final int? contractionSeconds;
  final int? relaxSeconds;
  final String? holdStrategy;
  final int? restBetweenSetsSeconds;
  final String frequencyNote;

  factory ExerciseDoseModel.fromJson(Map<String, dynamic> json) {
    return ExerciseDoseModel(
      targetDailyCycles: _intOrNull(json['target_daily_cycles']),
      sessionTargetCycles: _intOrNull(json['session_target_cycles']),
      sessionTargetReps: _intOrNull(json['session_target_reps']),
      repsPerSet: _intOrNull(json['reps_per_set']),
      setsPerDayMin: _intOrNull(json['sets_per_day_min']),
      setsPerDayMax: _intOrNull(json['sets_per_day_max']),
      contractionSeconds: _intOrNull(json['contraction_seconds']),
      relaxSeconds: _intOrNull(json['relax_seconds']),
      holdStrategy: json['hold_strategy'] as String?,
      restBetweenSetsSeconds: _intOrNull(json['rest_between_sets_seconds']),
      frequencyNote: json['frequency_note'] as String,
    );
  }

  String get summary {
    final sessionTarget = sessionTargetCycles ?? sessionTargetReps;
    final sessionText = sessionTarget == null ? '' : '，本次 $sessionTarget 次';

    if (targetDailyCycles != null) {
      final timing = contractionSeconds == null || relaxSeconds == null
          ? ''
          : '，用力 $contractionSeconds 秒，放松 $relaxSeconds 秒';
      return '每日不少于 $targetDailyCycles 次$timing$sessionText';
    }

    if (repsPerSet != null && setsPerDayMin != null) {
      final maxText = setsPerDayMax == null ? '' : '-$setsPerDayMax';
      final rest = restBetweenSetsSeconds == null
          ? ''
          : '，组间休息 $restBetweenSetsSeconds 秒';
      return '$repsPerSet 次/组，$setsPerDayMin$maxText 组/日$rest$sessionText';
    }

    return frequencyNote;
  }
}

List<String> _stringList(Object? value) {
  return List<String>.from((value as List?) ?? const <dynamic>[]);
}

int? _intOrNull(Object? value) {
  if (value == null) return null;
  return (value as num).toInt();
}
