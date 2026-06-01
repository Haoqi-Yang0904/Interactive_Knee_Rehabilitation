import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../data/models/training_result.dart';
import '../../application/summary_controller.dart';

class SummaryScreen extends ConsumerWidget {
  const SummaryScreen({
    super.key,
    required this.result,
  });

  final TrainingResult result;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(summaryControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('训练总结')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _MetricCard(
            title: '今日达标率',
            value: '${result.achievementRate.toStringAsFixed(1)}%',
          ),
          const SizedBox(height: 12),
          _MetricCard(
            title: '完成动作',
            value: '${result.completedExercises}/${result.totalExercises}',
          ),
          const SizedBox(height: 12),
          _MetricCard(
            title: '最大屈曲角度',
            value: '${result.maxFlexionAngle.toStringAsFixed(1)}°',
          ),
          const SizedBox(height: 12),
          _MetricCard(
            title: '今日疼痛等级',
            value: '${result.painScore}/10',
          ),
          const SizedBox(height: 16),
          _SummaryTextCard(
            title: '训练效果',
            text: result.effectSummary,
          ),
          if (result.exerciseResults.isNotEmpty) ...[
            const SizedBox(height: 16),
            for (final item in result.exerciseResults)
              _ExerciseResultCard(result: item),
          ],
          if (state.errorMessage != null) ...[
            const SizedBox(height: 16),
            Text(
              state.errorMessage!,
              style: const TextStyle(color: Colors.red),
            ),
          ],
          const SizedBox(height: 24),
          FilledButton(
            onPressed: state.isSubmitting
                ? null
                : () async {
                    final success = await ref
                        .read(summaryControllerProvider.notifier)
                        .submit(result);

                    if (!context.mounted) return;

                    if (success) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('训练数据已提交')),
                      );
                      Navigator.of(context).popUntil((route) => route.isFirst);
                    }
                  },
            style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(56),
            ),
            child: Text(state.isSubmitting ? '提交中...' : '提交'),
          ),
        ],
      ),
    );
  }
}

class _ExerciseResultCard extends StatelessWidget {
  const _ExerciseResultCard({required this.result});

  final ExerciseTrainingResult result;

  @override
  Widget build(BuildContext context) {
    final statusColor = result.completedUnits >= result.targetUnits
        ? const Color(0xFF15803D)
        : const Color(0xFFB45309);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            result.exerciseName,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '${_evaluationModeText(result.evaluationMode)} · ${result.completedUnits}/${result.targetUnits} 次 · ${result.achievementRate.toStringAsFixed(1)}%',
            style: TextStyle(
              color: statusColor,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (result.bestAngle != null) ...[
            const SizedBox(height: 6),
            Text('最佳膝伸直内角：${result.bestAngle!.toStringAsFixed(1)}°'),
          ],
          const SizedBox(height: 6),
          Text(
            result.feedback,
            style: const TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}

class _SummaryTextCard extends StatelessWidget {
  const _SummaryTextCard({
    required this.title,
    required this.text,
  });

  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F7F4),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(text),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.title,
    required this.value,
  });

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(fontSize: 16, color: Colors.black54),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w700,
            ),
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
      return '视觉识别';
    case 'hybrid':
      return '视觉+语音';
    default:
      return mode;
  }
}
