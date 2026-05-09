"""
Compatibility adapter for mediapipe >= 0.10.30 (new tasks API).

Maps the old mp.solutions.pose interface to the new PoseLandmarker API,
so step1_knee_bending_v1.py and step2_shoulder_rehab.py can work without
rewriting their main logic.
"""

import numpy as np
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions, RunningMode
from mediapipe.tasks.python.core.base_options import BaseOptions
from mediapipe import Image as MPImage, ImageFormat

# Standard landmark indices (same as old mp.solutions.pose.PoseLandmark)
class PoseLandmark:
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


class PoseResults:
    """Mimics the old results object with pose_landmarks.landmark list."""
    def __init__(self, pose_landmarks_list):
        if pose_landmarks_list:
            # Wrap the first pose's landmarks
            self.pose_landmarks = PoseLandmarksWrapper(pose_landmarks_list[0])
        else:
            self.pose_landmarks = None


class PoseLandmarksWrapper:
    """Wraps a single pose's landmarks to provide .landmark access."""
    def __init__(self, pose_landmark):
        self.landmark = pose_landmark.landmark


class Pose:
    """
    Drop-in replacement for mp.solutions.pose.Pose.

    Usage is identical to the old API:
        with Pose(model_complexity=1, ...) as pose:
            results = pose.process(rgb_image)
    """
    def __init__(
        self,
        static_image_mode=False,
        model_complexity=1,
        smooth_landmarks=True,
        enable_segmentation=False,
        smooth_segmentation=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ):
        self._model_path = _get_model_path(model_complexity)

        # Map model_complexity to the right .task file
        running_mode = RunningMode.IMAGE if static_image_mode else RunningMode.VIDEO

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=self._model_path),
            running_mode=running_mode,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

        self._landmarker = PoseLandmarker.create_from_options(options)
        self._frame_timestamp_ms = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self._landmarker:
            self._landmarker.close()

    def process(self, rgb_image):
        """
        Process a single RGB image (numpy array, HxWx3, uint8).
        Returns a PoseResults object compatible with the old API.
        """
        # Create MPImage from numpy array
        mp_image = MPImage(image_format=ImageFormat.SRGB, data=rgb_image)

        # Use detect for IMAGE mode, detect_for_video for VIDEO mode
        try:
            result = self._landmarker.detect(mp_image)
        except Exception:
            # Fallback for VIDEO mode
            self._frame_timestamp_ms += 33  # ~30fps
            result = self._landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        return PoseResults(result.pose_landmarks)


def _get_model_path(model_complexity):
    """Get the .task model file path based on complexity level."""
    import os

    # Look for the model in the project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if model_complexity == 0:
        candidates = ["pose_landmarker_lite.task"]
    elif model_complexity == 2:
        candidates = ["pose_landmarker_heavy.task"]
    else:  # model_complexity == 1 (default)
        candidates = ["pose_landmarker.task", "pose_landmarker_heavy.task"]

    for name in candidates:
        path = os.path.join(script_dir, name)
        if os.path.exists(path):
            return path

    # If not found, try heavy as fallback
    heavy_path = os.path.join(script_dir, "pose_landmarker_heavy.task")
    if os.path.exists(heavy_path):
        return heavy_path

    raise FileNotFoundError(
        f"找不到姿态识别模型文件。请将 pose_landmarker_heavy.task 放到 {script_dir} 目录下。\n"
        f"下载地址: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task"
    )


# Drawing utilities (replaces mp.solutions.drawing_utils)
class DrawingSpec:
    """Drawing specification for landmarks and connections."""
    def __init__(self, color=(224, 224, 224), thickness=2, circle_radius=2):
        self.color = color
        self.thickness = thickness
        self.circle_radius = circle_radius


# Standard pose connections (same as old mp.solutions.pose.POSE_CONNECTIONS)
POSE_CONNECTIONS = [
    # Face
    (PoseLandmark.LEFT_EYE_INNER, PoseLandmark.LEFT_EYE),
    (PoseLandmark.LEFT_EYE, PoseLandmark.LEFT_EYE_OUTER),
    (PoseLandmark.LEFT_EYE_OUTER, PoseLandmark.LEFT_EAR),
    (PoseLandmark.RIGHT_EYE_INNER, PoseLandmark.RIGHT_EYE),
    (PoseLandmark.RIGHT_EYE, PoseLandmark.RIGHT_EYE_OUTER),
    (PoseLandmark.RIGHT_EYE_OUTER, PoseLandmark.RIGHT_EAR),
    (PoseLandmark.MOUTH_LEFT, PoseLandmark.MOUTH_RIGHT),
    (PoseLandmark.LEFT_EYE_INNER, PoseLandmark.RIGHT_EYE_INNER),
    # Upper body
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.RIGHT_SHOULDER),
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_ELBOW),
    (PoseLandmark.LEFT_ELBOW, PoseLandmark.LEFT_WRIST),
    (PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_ELBOW),
    (PoseLandmark.RIGHT_ELBOW, PoseLandmark.RIGHT_WRIST),
    # Torso
    (PoseLandmark.LEFT_SHOULDER, PoseLandmark.LEFT_HIP),
    (PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_HIP),
    (PoseLandmark.LEFT_HIP, PoseLandmark.RIGHT_HIP),
    # Lower body
    (PoseLandmark.LEFT_HIP, PoseLandmark.LEFT_KNEE),
    (PoseLandmark.LEFT_KNEE, PoseLandmark.LEFT_ANKLE),
    (PoseLandmark.LEFT_ANKLE, PoseLandmark.LEFT_HEEL),
    (PoseLandmark.LEFT_HEEL, PoseLandmark.LEFT_FOOT_INDEX),
    (PoseLandmark.LEFT_ANKLE, PoseLandmark.LEFT_FOOT_INDEX),
    (PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE),
    (PoseLandmark.RIGHT_KNEE, PoseLandmark.RIGHT_ANKLE),
    (PoseLandmark.RIGHT_ANKLE, PoseLandmark.RIGHT_HEEL),
    (PoseLandmark.RIGHT_HEEL, PoseLandmark.RIGHT_FOOT_INDEX),
    (PoseLandmark.RIGHT_ANKLE, PoseLandmark.RIGHT_FOOT_INDEX),
]


def draw_landmarks(
    image,
    landmark_list,
    connections=None,
    landmark_drawing_spec=None,
    connection_drawing_spec=None,
):
    """
    Draw landmarks and connections on an image.
    Drop-in replacement for mp.solutions.drawing_utils.draw_landmarks.
    """
    import cv2

    if connections is None:
        connections = POSE_CONNECTIONS

    if landmark_drawing_spec is None:
        landmark_drawing_spec = DrawingSpec(color=(224, 224, 224), thickness=2, circle_radius=2)

    if connection_drawing_spec is None:
        connection_drawing_spec = DrawingSpec(color=(224, 224, 224), thickness=2)

    h, w = image.shape[:2]
    landmarks = landmark_list.landmark

    # Draw connections
    for start_idx, end_idx in connections:
        start = landmarks[start_idx]
        end = landmarks[end_idx]

        # Skip if either landmark is not visible
        if start.visibility < 0.2 or end.visibility < 0.2:
            continue

        start_pt = (int(start.x * w), int(start.y * h))
        end_pt = (int(end.x * w), int(end.y * h))

        cv2.line(image, start_pt, end_pt, connection_drawing_spec.color,
                 connection_drawing_spec.thickness, cv2.LINE_AA)

    # Draw landmarks
    for lm in landmarks:
        if lm.visibility < 0.2:
            continue

        pt = (int(lm.x * w), int(lm.y * h))
        cv2.circle(image, pt, landmark_drawing_spec.circle_radius,
                   landmark_drawing_spec.color, -1, cv2.LINE_AA)
        cv2.circle(image, pt, landmark_drawing_spec.circle_radius,
                   (0, 0, 0), 1, cv2.LINE_AA)


# Convenience: provide the same namespace as old API
def create_pose_module():
    """Return objects that match mp.solutions.pose namespace."""
    class PoseModule:
        Pose = Pose
        PoseLandmark = PoseLandmark
        POSE_CONNECTIONS = POSE_CONNECTIONS

        @staticmethod
        def get_pose_landmarks_connections():
            return POSE_CONNECTIONS

    return PoseModule()


# Drawing module compatibility
class DrawingUtils:
    draw_landmarks = staticmethod(draw_landmarks)
    DrawingSpec = DrawingSpec
