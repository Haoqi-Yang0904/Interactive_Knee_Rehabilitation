import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

class PoseDetectorService {
  final PoseDetector _detector = PoseDetector(
    options: PoseDetectorOptions(
      mode: PoseDetectionMode.stream,
      model: PoseDetectionModel.base,
    ),
  );

  Future<List<Pose>> detect(InputImage inputImage) {
    return _detector.processImage(inputImage);
  }

  Future<void> dispose() async {
    await _detector.close();
  }
}
