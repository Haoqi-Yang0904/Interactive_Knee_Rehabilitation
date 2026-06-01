import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:google_mlkit_commons/google_mlkit_commons.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

class PosePainter extends CustomPainter {
  PosePainter({
    required this.pose,
    required this.imageSize,
    required this.rotation,
  });

  final Pose pose;
  final Size imageSize;
  final InputImageRotation rotation;

  @override
  void paint(Canvas canvas, Size size) {
    final skeletonPaint = Paint()
      ..color = const Color(0xFF4ADE80)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final jointPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;

    final orientedImageSize = _orientedImageSize();
    final fitted = applyBoxFit(BoxFit.cover, orientedImageSize, size);
    final renderSize = fitted.destination;

    final offsetX = (size.width - renderSize.width) / 2;
    final offsetY = (size.height - renderSize.height) / 2;
    final scaleX = renderSize.width / orientedImageSize.width;
    final scaleY = renderSize.height / orientedImageSize.height;

    Offset translate(PoseLandmark landmark) {
      final rotated = _rotatePoint(Offset(landmark.x, landmark.y));
      return Offset(
        rotated.dx * scaleX + offsetX,
        rotated.dy * scaleY + offsetY,
      );
    }

    void drawLine(PoseLandmarkType a, PoseLandmarkType b) {
      final p1 = pose.landmarks[a];
      final p2 = pose.landmarks[b];
      if (p1 == null || p2 == null) return;
      canvas.drawLine(translate(p1), translate(p2), skeletonPaint);
    }

    const connections = [
      (PoseLandmarkType.leftShoulder, PoseLandmarkType.rightShoulder),
      (PoseLandmarkType.leftShoulder, PoseLandmarkType.leftElbow),
      (PoseLandmarkType.leftElbow, PoseLandmarkType.leftWrist),
      (PoseLandmarkType.rightShoulder, PoseLandmarkType.rightElbow),
      (PoseLandmarkType.rightElbow, PoseLandmarkType.rightWrist),
      (PoseLandmarkType.leftShoulder, PoseLandmarkType.leftHip),
      (PoseLandmarkType.rightShoulder, PoseLandmarkType.rightHip),
      (PoseLandmarkType.leftHip, PoseLandmarkType.rightHip),
      (PoseLandmarkType.leftHip, PoseLandmarkType.leftKnee),
      (PoseLandmarkType.leftKnee, PoseLandmarkType.leftAnkle),
      (PoseLandmarkType.leftAnkle, PoseLandmarkType.leftHeel),
      (PoseLandmarkType.leftHeel, PoseLandmarkType.leftFootIndex),
      (PoseLandmarkType.rightHip, PoseLandmarkType.rightKnee),
      (PoseLandmarkType.rightKnee, PoseLandmarkType.rightAnkle),
      (PoseLandmarkType.rightAnkle, PoseLandmarkType.rightHeel),
      (PoseLandmarkType.rightHeel, PoseLandmarkType.rightFootIndex),
    ];

    for (final connection in connections) {
      drawLine(connection.$1, connection.$2);
    }

    for (final landmark in pose.landmarks.values) {
      canvas.drawCircle(translate(landmark), 4, jointPaint);
    }
  }

  Size _orientedImageSize() {
    switch (rotation) {
      case InputImageRotation.rotation90deg:
      case InputImageRotation.rotation270deg:
        return Size(imageSize.height, imageSize.width);
      case InputImageRotation.rotation0deg:
      case InputImageRotation.rotation180deg:
        return imageSize;
    }
  }

  Offset _rotatePoint(Offset point) {
    switch (rotation) {
      case InputImageRotation.rotation90deg:
        return Offset(point.dy, imageSize.width - point.dx);
      case InputImageRotation.rotation180deg:
        return Offset(imageSize.width - point.dx, imageSize.height - point.dy);
      case InputImageRotation.rotation270deg:
        return Offset(imageSize.height - point.dy, point.dx);
      case InputImageRotation.rotation0deg:
        return point;
    }
  }

  @override
  bool shouldRepaint(covariant PosePainter oldDelegate) {
    return oldDelegate.pose != pose ||
        oldDelegate.imageSize != imageSize ||
        oldDelegate.rotation != rotation;
  }
}
