import 'dart:ui';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../data/models/prescription_model.dart';
import '../../../summary/presentation/screens/summary_screen.dart';
import '../../application/training_controller.dart';
import '../widgets/pose_painter.dart';

class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({
    super.key,
    required this.userId,
    required this.painScore,
    required this.prescription,
  });

  final String userId;
  final int painScore;
  final PrescriptionModel prescription;

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  bool _autoNavigatedToSummary = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref
          .read(trainingControllerProvider.notifier)
          .initialize(prescription: widget.prescription);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(trainingControllerProvider);
    final controller = state.cameraController;

    if (state.isSessionComplete &&
        !_autoNavigatedToSummary &&
        state.exerciseResults.isNotEmpty) {
      _autoNavigatedToSummary = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;

        final result = ref
            .read(trainingControllerProvider.notifier)
            .buildResult(
              userId: widget.userId,
              actionName: widget.prescription.rehabPlan?.title ??
                  widget.prescription.actionName,
              painScore: widget.painScore,
            );

        Navigator.of(context).pushReplacement(
          MaterialPageRoute(
            builder: (_) => SummaryScreen(result: result),
          ),
        );
      });
    }

    if (controller == null || !controller.value.isInitialized) {
      return Scaffold(
        backgroundColor: Colors.black,
        body: Center(
          child: Text(
            state.errorMessage ?? '正在初始化摄像头...',
            style: const TextStyle(color: Colors.white),
          ),
        ),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          _CameraPreviewLayer(controller: controller),
          if (state.currentPose != null &&
              state.imageSize != null &&
              state.rotation != null)
            IgnorePointer(
              child: CustomPaint(
                painter: PosePainter(
                  pose: state.currentPose!,
                  imageSize: state.imageSize!,
                  rotation: state.rotation!,
                ),
              ),
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  _TopMetrics(
                    angleText: state.currentAngle == null
                        ? '--'
                        : '${state.currentAngle!.toStringAsFixed(1)}°',
                    setsText:
                        '${state.currentExerciseCompletedUnits}/${state.currentExerciseTargetUnits}',
                    sequenceText:
                        '${state.completedSets}/${state.totalExercises}',
                    targetText: state.currentExercise == null
                        ? '训练任务已完成'
                        : '${state.currentExercise!.name} · ${_evaluationModeText(state.currentExercise!.evaluationMode)}',
                    feedbackText: state.feedbackText,
                  ),
                  const Spacer(),
                  FilledButton(
                    onPressed: state.isSessionComplete
                        ? null
                        : () {
                      final result = ref
                          .read(trainingControllerProvider.notifier)
                          .buildResult(
                            userId: widget.userId,
                            actionName: widget.prescription.rehabPlan?.title ??
                                widget.prescription.actionName,
                            painScore: widget.painScore,
                          );

                      Navigator.of(context).pushReplacement(
                        MaterialPageRoute(
                          builder: (_) => SummaryScreen(result: result),
                        ),
                      );
                    },
                    child: Text(state.isSessionComplete ? '查看总结' : '结束训练'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CameraPreviewLayer extends StatelessWidget {
  const _CameraPreviewLayer({required this.controller});

  final CameraController controller;

  @override
  Widget build(BuildContext context) {
    final previewSize = controller.value.previewSize;
    if (previewSize == null) {
      return const SizedBox.shrink();
    }

    final portraitSize = Size(previewSize.height, previewSize.width);

    return ClipRect(
      child: OverflowBox(
        alignment: Alignment.center,
        child: FittedBox(
          fit: BoxFit.cover,
          child: SizedBox(
            width: portraitSize.width,
            height: portraitSize.height,
            child: CameraPreview(controller),
          ),
        ),
      ),
    );
  }
}

class _TopMetrics extends StatelessWidget {
  const _TopMetrics({
    required this.angleText,
    required this.setsText,
    required this.sequenceText,
    required this.targetText,
    required this.feedbackText,
  });

  final String angleText;
  final String setsText;
  final String sequenceText;
  final String targetText;
  final String feedbackText;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.55),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            targetText,
            style: const TextStyle(color: Colors.white70, fontSize: 14),
          ),
          const SizedBox(height: 6),
          Text(
            '膝关节角度：$angleText',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 22,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '当前动作计数：$setsText',
            style: const TextStyle(color: Colors.white, fontSize: 18),
          ),
          const SizedBox(height: 4),
          Text(
            '训练进度：$sequenceText 个动作',
            style: const TextStyle(color: Colors.white, fontSize: 18),
          ),
          const SizedBox(height: 8),
          Text(
            feedbackText,
            style: const TextStyle(color: Color(0xFF86EFAC), fontSize: 16),
          ),
        ],
      ),
    );
  }
}

String _evaluationModeText(String mode) {
  switch (mode) {
    case 'voice_only':
      return '语音引导';
    case 'timer_counter':
      return '计时计数';
    case 'vision':
      return '视觉识别计数';
    case 'hybrid':
      return '视觉识别+语音';
    default:
      return mode;
  }
}
