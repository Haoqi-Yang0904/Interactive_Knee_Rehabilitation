import 'dart:math' as math;
import 'dart:ui';

class AngleCalculator {
  const AngleCalculator._();

  static double calculateKneeAngle({
    required Offset hip,
    required Offset knee,
    required Offset ankle,
  }) {
    // 以膝关节作为顶点，分别构造两条向量：
    // BA = A - B（膝 -> 髋）
    // BC = C - B（膝 -> 踝）
    // 然后通过 arctan2 计算两条向量的方向角，再求差值。
    final radiansBA = math.atan2(hip.dy - knee.dy, hip.dx - knee.dx);
    final radiansBC = math.atan2(ankle.dy - knee.dy, ankle.dx - knee.dx);

    var degrees = (radiansBC - radiansBA).abs() * 180 / math.pi;

    // 两个方向角的差值理论上会落在 [0, 360)。
    // 对膝关节分析来说，我们需要取最小内角，
    // 所以如果超过 180 度，就用 360 - θ 折回。
    if (degrees > 180) {
      degrees = 360 - degrees;
    }

    return degrees;
  }

  static double toClinicalFlexion(double interiorAngle) {
    // 当前实时计算结果是膝关节“内角”：
    // 站直时接近 180 度，屈膝越深则越接近 90 度。
    // 如果业务上要展示“屈曲角度”，可用 180 - 内角 来换算。
    return 180 - interiorAngle;
  }
}
