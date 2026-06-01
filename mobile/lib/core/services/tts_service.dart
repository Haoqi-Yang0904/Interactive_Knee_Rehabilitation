import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  final FlutterTts _tts = FlutterTts();
  bool _initialized = false;

  Future<void> init() async {
    if (_initialized) return;

    await _tts.awaitSpeakCompletion(true);
    await _tts.setLanguage('zh-CN');
    await _tts.setSpeechRate(0.45);
    await _tts.setPitch(1.0);
    await _tts.setVolume(1.0);

    _initialized = true;
  }

  Future<void> speak(String text) async {
    if (!_initialized) {
      await init();
    }

    await _tts.stop();
    await _tts.speak(text);
  }

  Future<void> dispose() async {
    await _tts.stop();
  }
}
