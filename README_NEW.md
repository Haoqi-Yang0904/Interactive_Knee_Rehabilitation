# Interactive Knee Rehabilitation (桌面端 + Web)

## 项目概览
这是一个基于 MediaPipe 姿态估计的膝关节/肩关节交互式康复指导系统，包含桌面端与 Web 端两种形态。

- 桌面端：Python + OpenCV + MediaPipe，支持实时骨骼识别、角度计算、分阶段语音反馈、自动截图与角度日志。
- Web 端：浏览器内 MediaPipe Pose，支持实时识别与语音播报，适合快速体验与演示。

## 平台支持
- macOS：桌面端与 Web 端均可启动。
- Windows：桌面端可启动（Web 端同样可用）。

## 桌面端 vs Web 端

| 对比项 | 桌面端 | Web 端 |
| --- | --- | --- |
| 技术栈 | Python + OpenCV + MediaPipe | 浏览器 + MediaPipe Pose |
| 摄像头 | OpenCV 访问 | 浏览器权限访问 |
| 语音反馈 | edge-tts / macOS say / MeloTTS | 浏览器 SpeechSynthesis |
| 日志 | 自动截图 + 角度日志 | 页面内训练记录（不落地文件） |
| 肩关节动作 | 4 种动作，全量提示 | 4 种动作，界面交互切换 |
| 适合场景 | 正式训练与记录 | 轻量演示与快速体验 |

## 功能清单

- 膝关节屈膝训练（目标 120°）：分阶段反馈（远 → 近 → 达标 → 保持 → 休息）。
- 肩关节康复训练（4 动作）：前屈 / 外展 / 外旋 / 后伸，动作约束检测（躯干倾斜、手臂伸直、动作平面）。
- 角度计算：默认使用 2D 角度，适配侧面拍摄，稳定性更好。
- 语音反馈：跨平台 TTS，桌面端支持 edge-tts 缓存或系统语音。
- 自动截图与日志：桌面端每 5 秒自动截图，并记录角度日志。
- 误差分析：误差可视化工具用于分析 2D vs 3D 角度偏差。
- VLM 视觉大模型提示：基于截图生成理疗师语音建议（需 API Key）。
- Web 前端：浏览器端实时姿态识别与训练提示。

## 使用说明

### 1) 安装依赖
在项目根目录执行：

```bash
pip install -r requirements.txt
```

> TTS 可选说明见 [Interactive_Knee_Rehabilitation/TTS_SETUP.md](Interactive_Knee_Rehabilitation/TTS_SETUP.md)。

### 2) 桌面端启动

- 膝关节训练：
  ```bash
  python step1_knee_bending_v1.py
  ```

- 肩关节训练：
  ```bash
  python step2_shoulder_rehab.py
  ```

- 误差分析（无需摄像头）：
  ```bash
  python error_map.py
  ```

- VLM 提示（需 API Key 与 test_pose.jpg）：
  ```bash
  API_KEY=你的KEY python step3_VLM_Prompt.py
  ```

### 3) Web 端启动

```bash
python serve_rehab_web.py
```

浏览器访问：

```
http://127.0.0.1:8000/
```

> 建议使用 Chrome/Edge 以保证 MediaPipe 与摄像头权限稳定。

## 目前效果（简述）

- 膝关节训练：侧身视角下角度稳定，达标后进入保持计时，自动截图与角度日志正常写入。
- 肩关节训练：四动作切换正常，能识别躯干倾斜/手臂未伸直/动作平面偏离并给出修正提示。
- Web 端：膝关节与肩关节模块可用，语音提示与训练记录同步更新，适合快速体验。

## 目录说明

- [Interactive_Knee_Rehabilitation/step1_knee_bending_v1.py](Interactive_Knee_Rehabilitation/step1_knee_bending_v1.py)：膝关节训练（桌面端）
- [Interactive_Knee_Rehabilitation/step2_shoulder_rehab.py](Interactive_Knee_Rehabilitation/step2_shoulder_rehab.py)：肩关节训练（桌面端）
- [Interactive_Knee_Rehabilitation/step3_VLM_Prompt.py](Interactive_Knee_Rehabilitation/step3_VLM_Prompt.py)：VLM 提示演示
- [Interactive_Knee_Rehabilitation/error_map.py](Interactive_Knee_Rehabilitation/error_map.py)：误差可视化
- [Interactive_Knee_Rehabilitation/serve_rehab_web.py](Interactive_Knee_Rehabilitation/serve_rehab_web.py)：Web 服务启动器
- [Interactive_Knee_Rehabilitation/rehab_web/app.js](Interactive_Knee_Rehabilitation/rehab_web/app.js)：Web 端核心逻辑
