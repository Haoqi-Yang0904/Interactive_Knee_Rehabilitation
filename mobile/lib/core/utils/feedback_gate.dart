import 'dart:async';

import 'package:flutter/foundation.dart';

class FeedbackGate {
  FeedbackGate({required this.cooldown});

  final Duration cooldown;
  Timer? _timer;
  bool _locked = false;

  void run(VoidCallback action) {
    // 这里实现的是“冷却门控”而不是传统 trailing debounce。
    // 在实时视频流里，如果每一帧都满足条件就直接播报，
    // TTS 会非常频繁重复，用户体验很差。
    //
    // 所以这里的策略是：
    // 1. 第一次满足条件时立即播报；
    // 2. 进入冷却时间，在冷却期内忽略重复触发；
    // 3. 冷却结束后才允许再次播报。
    if (_locked) return;

    _locked = true;
    action();

    _timer?.cancel();
    _timer = Timer(cooldown, () {
      _locked = false;
    });
  }

  void dispose() {
    _timer?.cancel();
  }
}
