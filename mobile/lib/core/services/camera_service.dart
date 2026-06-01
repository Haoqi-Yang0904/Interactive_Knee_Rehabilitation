import 'dart:async';
import 'dart:io';
import 'dart:ui';

import 'package:camera/camera.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_commons/google_mlkit_commons.dart';
import 'package:permission_handler/permission_handler.dart';

class CameraService {
  CameraController? _controller;
  CameraDescription? _camera;

  final Map<DeviceOrientation, int> _orientations = const {
    DeviceOrientation.portraitUp: 0,
    DeviceOrientation.landscapeLeft: 90,
    DeviceOrientation.portraitDown: 180,
    DeviceOrientation.landscapeRight: 270,
  };

  CameraController? get controller => _controller;

  Future<CameraController> initialize() async {
    final status = await Permission.camera.request();
    if (!status.isGranted) {
      throw Exception('未获得相机权限');
    }

    final cameras = await availableCameras();
    if (cameras.isEmpty) {
      throw Exception('设备未发现可用摄像头');
    }

    _camera = cameras.firstWhere(
      (item) => item.lensDirection == CameraLensDirection.back,
      orElse: () => cameras.first,
    );

    _controller = CameraController(
      _camera!,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup:
          Platform.isAndroid ? ImageFormatGroup.nv21 : ImageFormatGroup.bgra8888,
    );

    await _controller!.initialize();
    return _controller!;
  }

  Future<void> startImageStream(
    Future<void> Function(CameraImage image) onFrame,
  ) async {
    final controller = _controller;
    if (controller == null || controller.value.isStreamingImages) return;

    await controller.startImageStream((image) {
      unawaited(onFrame(image));
    });
  }

  InputImage? toInputImage(CameraImage image) {
    final controller = _controller;
    final camera = _camera;

    if (controller == null || camera == null) return null;
    if (image.planes.isEmpty) return null;

    final deviceRotation = _orientations[controller.value.deviceOrientation];
    if (deviceRotation == null) return null;

    final rotation = _resolveRotation(
      sensorOrientation: camera.sensorOrientation,
      deviceRotation: deviceRotation,
      lensDirection: camera.lensDirection,
    );
    if (rotation == null) return null;

    final format = InputImageFormatValue.fromRawValue(image.format.raw);
    if (format == null) return null;

    // 官方示例明确建议：Android 使用 nv21，iOS 使用 bgra8888。
    // 如果格式不匹配，最常见的问题就是相机预览正常但 ML Kit 无法识别。
    if (Platform.isAndroid && format != InputImageFormat.nv21) return null;
    if (Platform.isIOS && format != InputImageFormat.bgra8888) return null;

    // 这里采用官方示例推荐的单 plane 读取方式，避免多 plane 拼接带来的格式风险。
    if (image.planes.length != 1) return null;
    final plane = image.planes.first;

    return InputImage.fromBytes(
      bytes: plane.bytes,
      metadata: InputImageMetadata(
        size: Size(image.width.toDouble(), image.height.toDouble()),
        rotation: rotation,
        format: format,
        bytesPerRow: plane.bytesPerRow,
      ),
    );
  }

  InputImageRotation? _resolveRotation({
    required int sensorOrientation,
    required int deviceRotation,
    required CameraLensDirection lensDirection,
  }) {
    final rotation = Platform.isIOS
        ? (sensorOrientation + deviceRotation) % 360
        : lensDirection == CameraLensDirection.front
            ? (sensorOrientation + deviceRotation) % 360
            : (sensorOrientation - deviceRotation + 360) % 360;

    return InputImageRotationValue.fromRawValue(rotation);
  }

  Future<void> dispose() async {
    final controller = _controller;
    if (controller == null) return;

    if (controller.value.isStreamingImages) {
      await controller.stopImageStream();
    }

    await controller.dispose();
  }
}
