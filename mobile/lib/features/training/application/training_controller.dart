import 'dart:async';
import 'dart:math' as math;
import 'dart:ui';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_mlkit_commons/google_mlkit_commons.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

import '../../../core/services/camera_service.dart';
import '../../../core/services/pose_detector_service.dart';
import '../../../core/services/tts_service.dart';
import '../../../core/utils/angle_calculator.dart';
import '../../../core/utils/feedback_gate.dart';
import '../../../data/models/prescription_model.dart';
import '../../../data/models/training_result.dart';

const _unset = Object();

@immutable
class TrainingState {
  const TrainingState({
    this.cameraController,
    this.currentPose,
    this.imageSize,
    this.rotation,
    this.currentAngle,
    this.deepestInteriorAngle,
    this.completedSets = 0,
    this.isReady = false,
    this.feedbackText = '正在准备训练计划',
    this.errorMessage,
    this.currentExercise,
    this.currentExerciseIndex = 0,
    this.totalExercises = 0,
    this.currentExerciseCompletedUnits = 0,
    this.currentExerciseTargetUnits = 1,
    this.isSessionComplete = false,
    this.exerciseResults = const [],
    this.sessionBestInteriorAngle,
  });

  final CameraController? cameraController;
  final Pose? currentPose;
  final Size? imageSize;
  final InputImageRotation? rotation;
  final double? currentAngle;
  final double? deepestInteriorAngle;
  final int completedSets;
  final bool isReady;
  final String feedbackText;
  final String? errorMessage;
  final RehabExerciseModel? currentExercise;
  final int currentExerciseIndex;
  final int totalExercises;
  final int currentExerciseCompletedUnits;
  final int currentExerciseTargetUnits;
  final bool isSessionComplete;
  final List<ExerciseTrainingResult> exerciseResults;
  final double? sessionBestInteriorAngle;

  TrainingState copyWith({
    CameraController? cameraController,
    bool? isReady,
    String? feedbackText,
    int? completedSets,
    int? currentExerciseIndex,
    int? totalExercises,
    int? currentExerciseCompletedUnits,
    int? currentExerciseTargetUnits,
    bool? isSessionComplete,
    List<ExerciseTrainingResult>? exerciseResults,
    Object? sessionBestInteriorAngle = _unset,
    Object? currentPose = _unset,
    Object? imageSize = _unset,
    Object? rotation = _unset,
    Object? currentAngle = _unset,
    Object? deepestInteriorAngle = _unset,
    Object? errorMessage = _unset,
    Object? currentExercise = _unset,
  }) {
    return TrainingState(
      cameraController: cameraController ?? this.cameraController,
      currentPose: identical(currentPose, _unset)
          ? this.currentPose
          : currentPose as Pose?,
      imageSize: identical(imageSize, _unset)
          ? this.imageSize
          : imageSize as Size?,
      rotation: identical(rotation, _unset)
          ? this.rotation
          : rotation as InputImageRotation?,
      currentAngle: identical(currentAngle, _unset)
          ? this.currentAngle
          : currentAngle as double?,
      deepestInteriorAngle: identical(deepestInteriorAngle, _unset)
          ? this.deepestInteriorAngle
          : deepestInteriorAngle as double?,
      completedSets: completedSets ?? this.completedSets,
      isReady: isReady ?? this.isReady,
      feedbackText: feedbackText ?? this.feedbackText,
      errorMessage: identical(errorMessage, _unset)
          ? this.errorMessage
          : errorMessage as String?,
      currentExercise: identical(currentExercise, _unset)
          ? this.currentExercise
          : currentExercise as RehabExerciseModel?,
      currentExerciseIndex:
          currentExerciseIndex ?? this.currentExerciseIndex,
      totalExercises: totalExercises ?? this.totalExercises,
      currentExerciseCompletedUnits: currentExerciseCompletedUnits ??
          this.currentExerciseCompletedUnits,
      currentExerciseTargetUnits:
          currentExerciseTargetUnits ?? this.currentExerciseTargetUnits,
      isSessionComplete: isSessionComplete ?? this.isSessionComplete,
      exerciseResults: exerciseResults ?? this.exerciseResults,
      sessionBestInteriorAngle: identical(sessionBestInteriorAngle, _unset)
          ? this.sessionBestInteriorAngle
          : sessionBestInteriorAngle as double?,
    );
  }
}

class _TrackedLeg {
  const _TrackedLeg({
    required this.hip,
    required this.knee,
    required this.ankle,
    required this.sideLabel,
    required this.profileScore,
    this.heel,
    this.footIndex,
  });

  final Offset hip;
  final Offset knee;
  final Offset ankle;
  final String sideLabel;
  final double profileScore;
  final Offset? heel;
  final Offset? footIndex;

  double get legLength {
    return (hip - knee).distance + (knee - ankle).distance;
  }
}

class TrainingController extends StateNotifier<TrainingState> {
  TrainingController({
    required this.cameraService,
    required this.poseDetectorService,
    required this.ttsService,
  }) : super(const TrainingState());

  final CameraService cameraService;
  final PoseDetectorService poseDetectorService;
  final TtsService ttsService;

  final FeedbackGate _feedbackGate = FeedbackGate(
    cooldown: const Duration(seconds: 3),
  );

  final List<ExerciseTrainingResult> _exerciseResults = [];
  final List<String> _currentWarnings = [];

  List<RehabExerciseModel> _sessionExercises = const [];
  int _currentExerciseIndex = 0;
  int _currentCompletedUnits = 0;
  int _timerElapsedSeconds = 0;
  int _voiceCueIndex = 0;
  bool _isProcessingFrame = false;
  bool _visualRepActive = false;
  bool _isAdvancing = false;
  bool _disposed = false;
  bool _anklePumpFootVisible = false;
  bool _anklePumpVisualConfirmed = false;
  Offset? _baselineAnkle;
  double? _minAnklePumpAngle;
  double? _maxAnklePumpAngle;
  double? _currentBestAngle;
  double? _sessionBestInteriorAngle;
  Timer? _timerCounter;
  Timer? _advanceTimer;

  RehabExerciseModel? get _currentExercise {
    if (_currentExerciseIndex < 0 ||
        _currentExerciseIndex >= _sessionExercises.length) {
      return null;
    }
    return _sessionExercises[_currentExerciseIndex];
  }

  Future<void> initialize({required PrescriptionModel prescription}) async {
    try {
      await ttsService.init();

      _sessionExercises = _buildExerciseSequence(prescription);
      if (_sessionExercises.isEmpty) {
        throw Exception('当前处方没有可执行动作');
      }

      final controller = await cameraService.initialize();

      state = state.copyWith(
        cameraController: controller,
        isReady: true,
        totalExercises: _sessionExercises.length,
        errorMessage: null,
      );

      _startCurrentExercise();
      await cameraService.startImageStream(_processFrame);
    } catch (e) {
      state = state.copyWith(
        feedbackText: '训练初始化失败，请检查权限、设备状态或处方数据',
        errorMessage: e.toString(),
      );
    }
  }

  List<RehabExerciseModel> _buildExerciseSequence(
    PrescriptionModel prescription,
  ) {
    final plan = prescription.rehabPlan;
    if (plan == null) return const <RehabExerciseModel>[];

    return [
      for (final section in plan.sections)
        for (final exercise in section.exercises)
          if (exercise.status != 'contraindicated') exercise,
    ];
  }

  void _startCurrentExercise() {
    _timerCounter?.cancel();
    _advanceTimer?.cancel();
    _timerElapsedSeconds = 0;
    _currentCompletedUnits = 0;
    _currentBestAngle = null;
    _baselineAnkle = null;
    _minAnklePumpAngle = null;
    _maxAnklePumpAngle = null;
    _anklePumpFootVisible = false;
    _anklePumpVisualConfirmed = false;
    _visualRepActive = false;
    _voiceCueIndex = 0;
    _currentWarnings.clear();
    _isAdvancing = false;

    final exercise = _currentExercise;
    if (exercise == null) {
      _completeSession();
      return;
    }

    final targetUnits = _targetUnitsFor(exercise);
    final modeText = _evaluationModeText(exercise.evaluationMode);

    state = state.copyWith(
      currentExercise: exercise,
      currentExerciseIndex: _currentExerciseIndex,
      totalExercises: _sessionExercises.length,
      currentExerciseCompletedUnits: 0,
      currentExerciseTargetUnits: targetUnits,
      currentAngle: null,
      deepestInteriorAngle: null,
      feedbackText:
          '第 ${_currentExerciseIndex + 1}/${_sessionExercises.length} 个动作：${exercise.name}。$modeText。',
      errorMessage: null,
    );

    final firstCue = _nextVoiceCue(exercise);
    _speak('开始${exercise.name}。目标 $targetUnits 次。$firstCue');

    if (_usesTimer(exercise)) {
      _startTimerExercise(exercise);
    }
  }

  bool _usesTimer(RehabExerciseModel exercise) {
    return exercise.evaluationMode == 'voice_only' ||
        exercise.evaluationMode == 'timer_counter' ||
        exercise.id == 'ankle_pump';
  }

  bool _usesVision(RehabExerciseModel exercise) {
    return exercise.evaluationMode == 'vision' ||
        exercise.evaluationMode == 'hybrid';
  }

  void _startTimerExercise(RehabExerciseModel exercise) {
    final cycleSeconds = _cycleSecondsFor(exercise);

    _timerCounter = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_disposed || _isAdvancing) return;

      _timerElapsedSeconds += 1;
      final phaseText = _timerPhaseText(exercise, _timerElapsedSeconds);
      _speakTimerPhaseCue(exercise, _timerElapsedSeconds);

      if (_timerElapsedSeconds % cycleSeconds == 0) {
        _currentCompletedUnits += 1;
        final targetUnits = _targetUnitsFor(exercise);

        state = state.copyWith(
          currentExerciseCompletedUnits: _currentCompletedUnits,
          feedbackText:
              '${exercise.name}：已完成 $_currentCompletedUnits/$targetUnits 次。$phaseText${_timerVisualSuffix(exercise)}',
        );

        if (_currentCompletedUnits >= targetUnits) {
          _completeCurrentExercise('节拍计数达标');
        } else if (_currentCompletedUnits % 3 == 0) {
          _speak('已完成 $_currentCompletedUnits 次，继续保持节奏。');
        }
        return;
      }

      state = state.copyWith(
        feedbackText:
            '${exercise.name}：$_currentCompletedUnits/${_targetUnitsFor(exercise)} 次。$phaseText${_timerVisualSuffix(exercise)}',
      );
    });
  }

  int _cycleSecondsFor(RehabExerciseModel exercise) {
    final contraction = exercise.dose.contractionSeconds ?? 4;
    final relax = exercise.dose.relaxSeconds ?? 2;
    if (exercise.id == 'ankle_pump') {
      return (contraction + relax) * 2;
    }
    return contraction + relax;
  }

  String _timerPhaseText(RehabExerciseModel exercise, int elapsedSeconds) {
    final contraction = exercise.dose.contractionSeconds ?? 4;
    final relax = exercise.dose.relaxSeconds ?? 2;
    final phaseLength = contraction + relax;
    final step = (elapsedSeconds - 1) % _cycleSecondsFor(exercise);

    if (exercise.id == 'ankle_pump') {
      if (step < contraction) return '脚尖往头侧勾，保持。';
      if (step < phaseLength) return '放松。';
      if (step < phaseLength + contraction) return '脚尖往下踩，保持。';
      return '放松，准备下一次。';
    }

    if (step < contraction) return '主动收紧，保持。';
    return '放松，准备下一次。';
  }

  String _timerVisualSuffix(RehabExerciseModel exercise) {
    if (exercise.id != 'ankle_pump' || !_usesVision(exercise)) return '';
    if (_timerElapsedSeconds < 3) return '摄像头正在确认脚踝和脚尖。';
    if (!_anklePumpFootVisible) return '请把脚跟和脚尖完整露出来。';
    if (_anklePumpVisualConfirmed) return '视觉已确认脚尖活动。';
    return '脚尖活动幅度再明显一些。';
  }

  void _speakTimerPhaseCue(RehabExerciseModel exercise, int elapsedSeconds) {
    final contraction = exercise.dose.contractionSeconds ?? 4;
    final relax = exercise.dose.relaxSeconds ?? 2;
    final phaseLength = contraction + relax;
    final step = (elapsedSeconds - 1) % _cycleSecondsFor(exercise);

    if (exercise.id == 'ankle_pump') {
      if (elapsedSeconds == 1) return;
      if (step == 0) {
        _speak('脚尖往头侧勾，保持四秒。');
      } else if (step == contraction) {
        _speak('放松两秒。');
      } else if (step == phaseLength) {
        _speak('脚尖往下踩，保持四秒。');
      } else if (step == phaseLength + contraction) {
        _speak('放松两秒。');
      }
      return;
    }

    if (exercise.evaluationMode != 'voice_only') return;

    if (step == 0 && elapsedSeconds != 1) {
      _speak(_nextVoiceCue(exercise));
    } else if (step == contraction) {
      _speak('放松两秒。');
    }
  }

  Future<void> _processFrame(CameraImage image) async {
    if (_isProcessingFrame || _disposed) return;
    _isProcessingFrame = true;

    try {
      final inputImage = cameraService.toInputImage(image);
      if (inputImage == null) return;

      final poses = await poseDetectorService.detect(inputImage);
      final metadata = inputImage.metadata;

      if (poses.isEmpty) {
        final exercise = _currentExercise;
        final needsVision = exercise != null && _usesVision(exercise);
        state = state.copyWith(
          currentPose: null,
          currentAngle: null,
          imageSize: metadata?.size,
          rotation: metadata?.rotation,
          feedbackText: needsVision
              ? '未检测到人体，请后退半步并完整露出下肢'
              : state.feedbackText,
          errorMessage: null,
        );
        return;
      }

      final pose = poses.first;
      final exercise = _currentExercise;

      if (exercise == null || !_usesVision(exercise)) {
        state = state.copyWith(
          currentPose: pose,
          imageSize: metadata?.size,
          rotation: metadata?.rotation,
          currentAngle: null,
          errorMessage: null,
        );
        return;
      }

      if (exercise.id == 'ankle_pump') {
        _handleAnklePumpVisualFrame(
          pose: pose,
          imageSize: metadata?.size,
          rotation: metadata?.rotation,
          exercise: exercise,
        );
        return;
      }

      _handleVisualExercise(
        pose: pose,
        imageSize: metadata?.size,
        rotation: metadata?.rotation,
        exercise: exercise,
      );
    } catch (e) {
      state = state.copyWith(
        feedbackText: '姿态检测发生异常，请重试',
        errorMessage: e.toString(),
      );
    } finally {
      _isProcessingFrame = false;
    }
  }

  void _handleVisualExercise({
    required Pose pose,
    required Size? imageSize,
    required InputImageRotation? rotation,
    required RehabExerciseModel exercise,
  }) {
    if (_isAdvancing) return;

    final trackedLeg = _pickTrackedLeg(pose);

    if (trackedLeg == null) {
      state = state.copyWith(
        currentPose: pose,
        currentAngle: null,
        imageSize: imageSize,
        rotation: rotation,
        feedbackText: '请确保髋、膝、踝三个关键点都清晰可见',
        errorMessage: null,
      );
      return;
    }

    final kneeAngle = AngleCalculator.calculateKneeAngle(
      hip: trackedLeg.hip,
      knee: trackedLeg.knee,
      ankle: trackedLeg.ankle,
    );

    final deepestInteriorAngle = state.deepestInteriorAngle == null
        ? kneeAngle
        : math.min(state.deepestInteriorAngle!, kneeAngle);
    _sessionBestInteriorAngle = _sessionBestInteriorAngle == null
        ? kneeAngle
        : math.min(_sessionBestInteriorAngle!, kneeAngle);
    _currentBestAngle = _currentBestAngle == null
        ? kneeAngle
        : math.max(_currentBestAngle!, kneeAngle);

    _baselineAnkle ??= trackedLeg.ankle;
    final baseline = _baselineAnkle!;
    final legLength = math.max(trackedLeg.legLength, 1.0);
    final normalizedDisplacement = (trackedLeg.ankle - baseline).distance /
        legLength;
    final kneeStraight = kneeAngle >= 150;
    final targetUnits = _targetUnitsFor(exercise);

    var feedback = '${exercise.name}：$_currentCompletedUnits/$targetUnits 次。';

    if (!kneeStraight) {
      feedback += '膝盖尽量伸直，不要弯着抬腿。';
      _rememberWarning('膝关节未保持伸直');
      _feedbackGate.run(() {
        _speak('膝盖尽量伸直，再继续动作。');
      });
    } else if (!_visualRepActive && normalizedDisplacement > 0.13) {
      _visualRepActive = true;
      feedback += '已经抬起，保持控制，慢慢放回。';
    } else if (_visualRepActive && normalizedDisplacement < 0.06) {
      _visualRepActive = false;
      _currentCompletedUnits += 1;
      feedback += '完成一次，有效计数。';
      final completedText = _visualRepCue(exercise);
      if (completedText.isNotEmpty) {
        _speak('完成一次。$completedText');
      } else {
        _speak('完成一次。');
      }

      if (_currentCompletedUnits >= targetUnits) {
        state = state.copyWith(
          currentPose: pose,
          imageSize: imageSize,
          rotation: rotation,
          currentAngle: kneeAngle,
          deepestInteriorAngle: deepestInteriorAngle,
          sessionBestInteriorAngle: _sessionBestInteriorAngle,
          currentExerciseCompletedUnits: _currentCompletedUnits,
          completedSets: _currentExerciseIndex + 1,
          feedbackText: '${exercise.name} 已达标，准备进入下一个动作。',
          errorMessage: null,
        );
        _completeCurrentExercise('视觉计数达标');
        return;
      }
    } else {
      feedback += kneeStraight ? '腿伸直后完成抬起和控制放下。' : '';
    }

    state = state.copyWith(
      currentPose: pose,
      imageSize: imageSize,
      rotation: rotation,
      currentAngle: kneeAngle,
      deepestInteriorAngle: deepestInteriorAngle,
      sessionBestInteriorAngle: _sessionBestInteriorAngle,
      currentExerciseCompletedUnits: _currentCompletedUnits,
      feedbackText: feedback,
      errorMessage: null,
    );
  }

  void _handleAnklePumpVisualFrame({
    required Pose pose,
    required Size? imageSize,
    required InputImageRotation? rotation,
    required RehabExerciseModel exercise,
  }) {
    if (_isAdvancing) return;

    final trackedLeg = _pickTrackedLeg(pose);
    final targetUnits = _targetUnitsFor(exercise);

    if (trackedLeg == null) {
      _anklePumpFootVisible = false;
      if (_timerElapsedSeconds >= _cycleSecondsFor(exercise)) {
        _rememberWarning('踝泵训练中下肢关键点未清晰可见');
      }
      state = state.copyWith(
        currentPose: pose,
        imageSize: imageSize,
        rotation: rotation,
        currentAngle: null,
        errorMessage: null,
      );
      return;
    }

    final footAngle = _anklePumpFootAngle(trackedLeg);
    if (footAngle == null) {
      _anklePumpFootVisible = false;
      if (_timerElapsedSeconds >= _cycleSecondsFor(exercise)) {
        _rememberWarning('踝泵训练中脚跟或脚尖未清晰可见');
      }
      _feedbackGate.run(() {
        if (_timerElapsedSeconds >= 3) {
          _speak('请把脚跟和脚尖完整露出来，继续跟随节拍。');
        }
      });
      state = state.copyWith(
        currentPose: pose,
        imageSize: imageSize,
        rotation: rotation,
        currentAngle: null,
        errorMessage: null,
      );
      return;
    }

    _anklePumpFootVisible = true;
    _minAnklePumpAngle = _minAnklePumpAngle == null
        ? footAngle
        : math.min(_minAnklePumpAngle!, footAngle);
    _maxAnklePumpAngle = _maxAnklePumpAngle == null
        ? footAngle
        : math.max(_maxAnklePumpAngle!, footAngle);

    final angleRange = (_maxAnklePumpAngle! - _minAnklePumpAngle!).abs();
    if (angleRange >= 12) {
      _anklePumpVisualConfirmed = true;
    } else if (_timerElapsedSeconds >= _cycleSecondsFor(exercise)) {
      _rememberWarning('踝泵脚尖活动幅度不足');
      _feedbackGate.run(() {
        _speak('脚尖往上勾和往下踩的幅度再明显一些。');
      });
    }

    state = state.copyWith(
      currentPose: pose,
      imageSize: imageSize,
      rotation: rotation,
      currentAngle: null,
      currentExerciseCompletedUnits: _currentCompletedUnits,
      feedbackText:
          '${exercise.name}：$_currentCompletedUnits/$targetUnits 次。${_timerPhaseText(exercise, math.max(_timerElapsedSeconds, 1))}${_timerVisualSuffix(exercise)}',
      errorMessage: null,
    );
  }

  double? _anklePumpFootAngle(_TrackedLeg leg) {
    final heel = leg.heel;
    final footIndex = leg.footIndex;
    if (heel == null || footIndex == null) return null;

    final footLength = (footIndex - heel).distance;
    final legLength = math.max(leg.legLength, 1.0);
    if (footLength < legLength * 0.08) return null;

    final shankAngle = math.atan2(
      leg.ankle.dy - leg.knee.dy,
      leg.ankle.dx - leg.knee.dx,
    );
    final footAngle = math.atan2(
      footIndex.dy - heel.dy,
      footIndex.dx - heel.dx,
    );

    return _smallestAngleDifferenceDegrees(shankAngle, footAngle);
  }

  double _smallestAngleDifferenceDegrees(double a, double b) {
    var degrees = (a - b).abs() * 180 / math.pi;
    while (degrees > 360) {
      degrees -= 360;
    }
    return degrees > 180 ? 360 - degrees : degrees;
  }

  void _rememberWarning(String warning) {
    if (_currentWarnings.contains(warning)) return;
    _currentWarnings.add(warning);
  }

  _TrackedLeg? _pickTrackedLeg(Pose pose) {
    _TrackedLeg? buildLeg({
      required PoseLandmarkType hipType,
      required PoseLandmarkType kneeType,
      required PoseLandmarkType ankleType,
      required PoseLandmarkType heelType,
      required PoseLandmarkType footIndexType,
      required String sideLabel,
    }) {
      final hip = pose.landmarks[hipType];
      final knee = pose.landmarks[kneeType];
      final ankle = pose.landmarks[ankleType];
      final heel = pose.landmarks[heelType];
      final footIndex = pose.landmarks[footIndexType];

      if (hip == null || knee == null || ankle == null) return null;

      final hipOffset = Offset(hip.x, hip.y);
      final kneeOffset = Offset(knee.x, knee.y);
      final ankleOffset = Offset(ankle.x, ankle.y);
      final heelOffset = heel == null ? null : Offset(heel.x, heel.y);
      final footIndexOffset = footIndex == null
          ? null
          : Offset(footIndex.x, footIndex.y);
      final profileScore = (hipOffset.dx - kneeOffset.dx).abs() +
          (kneeOffset.dx - ankleOffset.dx).abs();

      return _TrackedLeg(
        hip: hipOffset,
        knee: kneeOffset,
        ankle: ankleOffset,
        sideLabel: sideLabel,
        profileScore: profileScore,
        heel: heelOffset,
        footIndex: footIndexOffset,
      );
    }

    final left = buildLeg(
      hipType: PoseLandmarkType.leftHip,
      kneeType: PoseLandmarkType.leftKnee,
      ankleType: PoseLandmarkType.leftAnkle,
      heelType: PoseLandmarkType.leftHeel,
      footIndexType: PoseLandmarkType.leftFootIndex,
      sideLabel: 'left',
    );

    final right = buildLeg(
      hipType: PoseLandmarkType.rightHip,
      kneeType: PoseLandmarkType.rightKnee,
      ankleType: PoseLandmarkType.rightAnkle,
      heelType: PoseLandmarkType.rightHeel,
      footIndexType: PoseLandmarkType.rightFootIndex,
      sideLabel: 'right',
    );

    final candidates = [
      if (left != null) left,
      if (right != null) right,
    ];
    if (candidates.isEmpty) return null;

    candidates.sort((a, b) => b.profileScore.compareTo(a.profileScore));
    return candidates.first;
  }

  void _completeCurrentExercise(String reason) {
    if (_isAdvancing || _disposed) return;
    _isAdvancing = true;
    _timerCounter?.cancel();

    final exercise = _currentExercise;
    if (exercise == null) {
      _completeSession();
      return;
    }

    final targetUnits = _targetUnitsFor(exercise);
    final achievementRate = targetUnits <= 0
        ? 0.0
        : ((_currentCompletedUnits / targetUnits).clamp(0.0, 1.0) as num)
                .toDouble() *
            100.0;

    final warningsText = _currentWarnings.isEmpty
        ? '动作质量达标'
        : _currentWarnings.join('；');

    final result = ExerciseTrainingResult(
      exerciseId: exercise.id,
      exerciseName: exercise.name,
      evaluationMode: exercise.evaluationMode,
      completedUnits: _currentCompletedUnits,
      targetUnits: targetUnits,
      achievementRate: achievementRate,
      bestAngle: _currentBestAngle,
      feedback: '$reason，$warningsText。',
    );
    _exerciseResults.add(result);

    state = state.copyWith(
      exerciseResults: List<ExerciseTrainingResult>.unmodifiable(
        _exerciseResults,
      ),
      completedSets: _exerciseResults.length,
      feedbackText: '${exercise.name} 已完成，准备进入下一个动作。',
    );

    _speak('${exercise.name} 已完成。');

    _advanceTimer = Timer(const Duration(seconds: 2), () {
      if (_disposed) return;
      _currentExerciseIndex += 1;
      if (_currentExerciseIndex >= _sessionExercises.length) {
        _completeSession();
      } else {
        _startCurrentExercise();
      }
    });
  }

  void _completeSession() {
    _timerCounter?.cancel();
    _advanceTimer?.cancel();

    state = state.copyWith(
      currentExercise: null,
      currentExerciseCompletedUnits: 0,
      currentExerciseTargetUnits: 1,
      isSessionComplete: true,
      sessionBestInteriorAngle: _sessionBestInteriorAngle,
      exerciseResults: List<ExerciseTrainingResult>.unmodifiable(
        _exerciseResults,
      ),
      feedbackText: '整套训练任务已完成，可以查看训练总结。',
      completedSets: _exerciseResults.length,
    );

    _speak('整套训练任务已完成，可以查看训练总结。');
  }

  int _targetUnitsFor(RehabExerciseModel exercise) {
    return exercise.dose.sessionTargetCycles ??
        exercise.dose.sessionTargetReps ??
        exercise.dose.repsPerSet ??
        exercise.dose.targetDailyCycles ??
        1;
  }

  String _evaluationModeText(String mode) {
    switch (mode) {
      case 'voice_only':
        return '跟随语音节拍完成';
      case 'timer_counter':
        return '按计时节拍自动计数';
      case 'vision':
        return '摄像头会识别动作并计数';
      case 'hybrid':
        return '摄像头计数，并配合语音提示';
      default:
        return mode;
    }
  }

  String _nextVoiceCue(RehabExerciseModel exercise) {
    if (exercise.voiceCues.isEmpty) return '';

    final cue = exercise.voiceCues[_voiceCueIndex % exercise.voiceCues.length];
    _voiceCueIndex += 1;
    return cue;
  }

  String _visualRepCue(RehabExerciseModel exercise) {
    if (exercise.voiceCues.isEmpty) return '';
    if (_currentCompletedUnits <= 1 || _currentCompletedUnits % 3 == 0) {
      return _nextVoiceCue(exercise);
    }
    return '';
  }

  void _speak(String text) {
    unawaited(ttsService.speak(text));
  }

  TrainingResult buildResult({
    required String userId,
    required String actionName,
    required int painScore,
  }) {
    final results = _exerciseResults.isEmpty && state.exerciseResults.isNotEmpty
        ? state.exerciseResults
        : _exerciseResults;

    return TrainingResult.fromExerciseResults(
      userId: userId,
      actionName: actionName,
      painScore: painScore,
      exerciseResults: List<ExerciseTrainingResult>.unmodifiable(results),
      deepestInteriorAngle:
          state.sessionBestInteriorAngle ?? state.deepestInteriorAngle,
    );
  }

  @override
  void dispose() {
    _disposed = true;
    _timerCounter?.cancel();
    _advanceTimer?.cancel();
    unawaited(cameraService.dispose());
    unawaited(poseDetectorService.dispose());
    unawaited(ttsService.dispose());
    _feedbackGate.dispose();
    super.dispose();
  }
}

final trainingControllerProvider =
    StateNotifierProvider.autoDispose<TrainingController, TrainingState>((ref) {
  final controller = TrainingController(
    cameraService: CameraService(),
    poseDetectorService: PoseDetectorService(),
    ttsService: TtsService(),
  );

  ref.onDispose(controller.dispose);
  return controller;
});
