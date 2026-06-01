import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../data/models/prescription_model.dart';
import '../../../training/presentation/screens/camera_screen.dart';
import '../../application/home_controller.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(homeControllerProvider.notifier).initialize(
            AppConstants.demoUserId,
          );
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(homeControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('智能骨科康复伴侣'),
        centerTitle: true,
      ),
      body: SafeArea(
        child: state.isLoading
            ? const Center(child: CircularProgressIndicator())
            : state.errorMessage != null
                ? _ErrorView(message: state.errorMessage!)
                : _ContentView(
                    prescription: state.prescription,
                    painScore: state.painScore,
                    onPainChanged: (value) {
                      ref.read(homeControllerProvider.notifier).updatePainScore(
                            value,
                          );
                    },
                    onRetry: () {
                      ref.read(homeControllerProvider.notifier).initialize(
                            AppConstants.demoUserId,
                          );
                    },
                    onStartTraining: state.prescription == null
                        ? null
                        : () {
                            Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => CameraScreen(
                                  userId: AppConstants.demoUserId,
                                  painScore: state.painScore,
                                  prescription: state.prescription!,
                                ),
                              ),
                            );
                          },
                  ),
      ),
    );
  }
}

class _ContentView extends StatelessWidget {
  const _ContentView({
    required this.prescription,
    required this.painScore,
    required this.onPainChanged,
    required this.onRetry,
    required this.onStartTraining,
  });

  final PrescriptionModel? prescription;
  final int painScore;
  final ValueChanged<double> onPainChanged;
  final VoidCallback onRetry;
  final VoidCallback? onStartTraining;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFFF3F7F4),
            borderRadius: BorderRadius.circular(20),
          ),
          child: prescription == null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '今日康复处方',
                      style: textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text('暂无处方数据'),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: onRetry,
                      child: const Text('重新获取'),
                    ),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '今日康复处方',
                      style: textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text('动作名称：${prescription!.actionName}'),
                    Text('目标组数：${prescription!.targetSets} 组'),
                    Text('目标角度：${prescription!.targetAngle.toStringAsFixed(0)}°'),
                    Text('保持时长：${prescription!.holdSeconds} 秒'),
                    Text('频率建议：${prescription!.frequencyNote}'),
                    const SizedBox(height: 8),
                    Text(
                      '注意事项：${prescription!.caution}',
                      style: const TextStyle(color: Colors.black54),
                    ),
                    if (prescription!.rehabPlan != null) ...[
                      const SizedBox(height: 16),
                      _RehabPlanView(plan: prescription!.rehabPlan!),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFFFFF7ED),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '患者自报量表（PROM）',
                style: textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Text('今日疼痛等级：$painScore / 10'),
              Slider(
                min: 1,
                max: 10,
                divisions: 9,
                value: painScore.toDouble(),
                label: '$painScore',
                onChanged: onPainChanged,
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: onStartTraining,
          style: FilledButton.styleFrom(
            minimumSize: const Size.fromHeight(56),
          ),
          child: const Text('开始训练'),
        ),
      ],
    );
  }
}

class _RehabPlanView extends StatelessWidget {
  const _RehabPlanView({required this.plan});

  final KneeRehabPlanModel plan;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 14, 14, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  plan.title,
                  style: textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  plan.phase,
                  style: const TextStyle(color: Colors.black54),
                ),
                const SizedBox(height: 8),
                Text(plan.intensityNote),
                if (plan.educationNotes.isNotEmpty)
                  _DetailBlock(
                    title: '术后教育',
                    items: plan.educationNotes,
                  ),
              ],
            ),
          ),
          for (final section in plan.sections)
            _PlanSectionTile(section: section),
          if (plan.globalStopRules.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 14),
              child: _DetailBlock(
                title: '停止规则',
                items: plan.globalStopRules,
              ),
            ),
        ],
      ),
    );
  }
}

class _PlanSectionTile extends StatelessWidget {
  const _PlanSectionTile({required this.section});

  final RehabPlanSectionModel section;

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      tilePadding: const EdgeInsets.symmetric(horizontal: 14),
      childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
      title: Text(
        section.title,
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
      subtitle: Text(section.purpose),
      children: [
        for (final exercise in section.exercises)
          _ExerciseTile(exercise: exercise),
      ],
    );
  }
}

class _ExerciseTile extends StatelessWidget {
  const _ExerciseTile({required this.exercise});

  final RehabExerciseModel exercise;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFB),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFE5E7EB)),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 12),
        childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
        title: Text(
          exercise.name,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Text(
          '${exercise.dose.summary} · ${_evaluationModeText(exercise.evaluationMode)}',
        ),
        children: [
          Align(
            alignment: Alignment.centerLeft,
            child: Text('目的：${exercise.purpose}'),
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text('开始条件：${exercise.startRule}'),
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerLeft,
            child: Text('计划状态：${_statusText(exercise.status)}'),
          ),
          _DetailBlock(title: '动作标准', items: exercise.standard),
          _DetailBlock(title: '执行步骤', items: exercise.execution),
          _DetailBlock(title: '评估方式', items: exercise.assessment),
          _DetailBlock(title: '语音提示', items: exercise.voiceCues),
          if (exercise.contraindications.isNotEmpty)
            _DetailBlock(title: '禁忌/暂缓', items: exercise.contraindications),
          if (exercise.stopRules.isNotEmpty)
            _DetailBlock(title: '停止本动作', items: exercise.stopRules),
        ],
      ),
    );
  }
}

class _DetailBlock extends StatelessWidget {
  const _DetailBlock({
    required this.title,
    required this.items,
  });

  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          for (final item in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text('• $item'),
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
      return '视觉评估';
    case 'hybrid':
      return '视觉+语音';
    default:
      return mode;
  }
}

String _statusText(String status) {
  switch (status) {
    case 'daily_required':
      return '每日必做';
    case 'voice_guided':
      return '语音引导';
    case 'conditional_after_clearance':
      return '医生允许后执行';
    case 'conditional_reduce_or_hold':
      return '疼痛偏高，减量或暂缓';
    case 'contraindicated':
      return '禁忌';
    case 'optional_after_home_recovery':
      return '居家日常恢复后可选';
    default:
      return status;
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          '首页加载失败\n$message',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
