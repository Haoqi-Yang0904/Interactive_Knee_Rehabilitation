# Interactive Knee Rehabilitation

临床科技实践小队（第三组，主题为：膝关节交互式康复指导）的 GitHub 仓库。

当前仓库包含两部分：

- `mobile/`：Flutter 移动端源码
- `backend/`：FastAPI 后端源码
- `rehab_web/`、`step*.py`：交互式康复原型、网页 demo 和实验脚本

## 移动端和后端 MVP

### 1. 先测后端

```bash
cd /path/to/Interactive_Knee_Rehabilitation/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

打开：

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

### 2. 再测 Flutter

当前这台机器还没有安装 `flutter` / `dart`，所以我已经把 Flutter 源码放进 `mobile/lib/` 了，但还不能在这里直接编译。

等你装好 Flutter 后，在 `mobile/` 目录执行：

```bash
cd /path/to/Interactive_Knee_Rehabilitation/mobile
flutter create .
flutter pub get
flutter run
```

然后根据运行设备调整 `mobile/lib/core/constants/app_constants.dart` 里的后端地址。

### 3. Android / iOS 原生配置

`flutter create .` 生成原生工程后，请补上：

- Android：`android/app/src/main/AndroidManifest.xml`
- iOS：`ios/Runner/Info.plist`

需要加入的权限配置我已经写在下面：

```xml
<uses-permission android:name="android.permission.CAMERA" />

<queries>
    <intent>
        <action android:name="android.intent.action.TTS_SERVICE" />
    </intent>
</queries>
```

```xml
<key>NSCameraUsageDescription</key>
<string>需要访问摄像头以进行膝关节康复动作识别</string>
```

## 膝关节术后康复训练范式

当前已在后端建立膝关节动作库：

- `backend/app/services/knee_rehab_library.py`：动作库、计划生成、训练完成量评估
- `backend/app/schemas/prescription.py`：处方响应中的 `rehab_plan` 结构
- `/api/prescription/{user_id}`：继续兼容原有单动作字段，同时返回完整 `rehab_plan`

`rehab_plan` 目前包含两部分：

- 控水肿、预防血栓：主动踝泵、股四头肌等长收缩、腘绳肌等长收缩
- 肌力练习：仰卧位直抬腿、侧抬腿、后抬腿、内收抬腿

每个动作都包含动作标准、执行步骤、剂量、评估方式、语音提示、禁忌和停止规则。股四头肌和腘绳肌等长收缩暂按语音引导与自评计数处理，不做强视觉识别。

## 膝关节原型更新记录

### 2026/5/7 更新

1、目前最新版本的测量屈膝原型代码已合并为一个跨平台版本：step1_knee_bending_v1.py。该文件可在 Windows 和 macOS 上运行，运行时会根据系统自动选择摄像头、窗口显示和语音播放相关逻辑；

2、原先在屏幕上显示的加载摄像头内容的窗口 在窗口放大以后图像尺寸仍然不变，现在可以主动调节窗口尺寸，并自适应调整图像尺寸；

3、edge-tts语音生成时间较长，有一定的延迟，代码运行前会先检查是否已经生成了对应的语音文件，如果有的话会检查其hash码，没有的话会生成对应的文件，然后在运行过程中直接调用对应的文件；

4、原先在判定屈膝角度是否达到目标角度的时候用的是MediaPipe的三维坐标，由于电脑和手机的摄像头并不能够获取准确的深度信息，这里计算的三维坐标并不准确，经过实测，用三维坐标计算的角度和用二维坐标计算的角度最多能差20多度，二维坐标计算的角度准确性更高、鲁棒性更强，故而选择使用二维坐标计算角度。在假定摄像头正对人体侧面（或者说拍摄平面平行于人体矢状面）的前提下，可以用量角器来测量一下实际屈膝角度，与程序计算的屈膝角度之间比对一下，看看识别是否准确。当拍摄平面与人体矢状面之间有一定夹角的时候，可以针对（倾斜屈膝角度-正面屈膝角度）这个差值 与 拍摄平面与人体矢状面之间的夹角 做一定的理论计算。这个夹角带来的视角偏差是使用2D坐标的固有缺陷，与程序的测量精度无关，故而上述两种偏差可以分开来测量讨论。误差分析参见error_map.py

5、运行程序时会自动在工作目录下新建test_pose文件夹，里面会新建一个以当前时间戳命名的子文件夹，以5s为周期截一次图，每帧记录角度信息，方便后续分析、绘图；

6、新建requirements.txt，运行程序前可以用conda建一个独立环境，运行

```
pip install -r requirements.txt
```

以安装必要的依赖。如果复用 `backend/.venv` 来运行根目录下的 `step*.py` 原型脚本，请在项目根目录运行：

```
backend/.venv/bin/python -m pip install -r requirements.txt
```

`backend/requirements.txt` 只包含 FastAPI 后端依赖，不包含 OpenCV、MediaPipe、pygame 等动作识别原型脚本依赖。

## MacBook 电脑端完整膝关节训练测试

如果暂时不测试手机端，可以直接运行电脑端完整训练脚本：

```bash
cd /path/to/Interactive_Knee_Rehabilitation
backend/.venv/bin/python knee_rehab_desktop_session.py
```

默认顺序为：

```
踝泵 -> 股四头肌等长 -> 腘绳肌等长 -> 仰卧直抬腿 -> 侧抬腿 -> 后抬腿 -> 内收抬腿 -> 总结
```

默认每个动作 10 次。第一次只是快速试跑时，可以改成每个动作 3 次：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3
```

摄像头默认会根据 macOS 检测到的设备数选择序号：如果只检测到一个摄像头，默认直接用 `index 0`；如果检测到多个摄像头，才会优先尝试 `index 1`、`index 2`，再回退到 `index 0`，目的是避开连续互通相机里常见的 iPhone 摄像头。先查看系统识别到的摄像头：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --list-cameras
```

如果终端出现 `out device of bound (0-0): 1`，说明当前只有一个 AVFoundation 摄像头，必须用：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --camera 0
```

如果检测到多个摄像头，并且 `index 0` 连到手机，再试：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --camera 1
```

如果需要实际探测 OpenCV 能打开哪些序号，可以运行 `--probe-cameras`，但这可能触发 macOS 摄像头权限提示。

macOS 上脚本会强制使用 OpenCV 的 `AVFOUNDATION` 摄像头后端，不再回退到 `CAP_ANY`，避免误触发 `OBSENSOR/Orbbec` 后端导致 `No device found` 异常。

脚本默认使用 `edge-tts` 生成本地神经语音缓存，训练时优先播放本地 mp3；如果缓存不可用，才回退到 macOS `say`。可以先单独生成语音库：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 10 --prepare-voice-cache
```

缓存目录默认是 `feedback_audio/knee_desktop_session/`。当前桌面脚本只缓存短句提示，例如“准备，开始。”“抬起。”“保持。”“放下。”，避免长句播报拖慢动作节奏。

每个动作会先等待起始位稳定，再播报“准备，开始。”。股四头肌等长和腘绳肌等长现在也会通过画面识别髋、膝、踝和膝伸直状态，起始位稳定后自动开始，不需要按键。播报完成后默认额外等待 2 秒，给用户反应和开始动作的时间。可以调整这个反应时间：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --reaction-seconds 2.5
```

默认神经语音音色是 `zh-CN-XiaoxiaoNeural`，语速是 `-10%`。如果想换音色或语速：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --edge-voice zh-CN-XiaoyiNeural --edge-rate -15%
```

如果不想用神经语音缓存，也可以强制使用 macOS 系统语音：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --tts-engine say --voice Tingting --voice-rate 135
```

视觉识别动作采用“起始位稳定 -> 抬到标准位 -> 标准位保持达标 -> 控制放回起始位 -> 计 1 次”的流程，不再只靠抬起/放下瞬间计数。程序会锁定同一侧腿，短时保留上一帧有效骨架，平滑膝角和脚踝位移，减少左右腿切换和关键点跳变。

画面中会显示骨架线、起始位辅助圈、目标位辅助圈和当前移动箭头。抬腿动作现在按“脚踝相对髋部”的位移判断，降低身体整体晃动造成的误判。踝泵练习也会做视觉辅助评估：脚跟和脚尖需要进入画面，程序会对膝、踝、脚跟、脚尖关键点做平滑，并对突然跳变的踝角做滤波，减少足部线条突变导致的误判。

电脑端动作定义已拆到：

```text
rehab_actions/knee_desktop_library.py
```

后端处方动作库仍在：

```text
backend/app/services/knee_rehab_library.py
```

只查看动作列表、不打开摄像头：

```bash
backend/.venv/bin/python knee_rehab_desktop_session.py --list
```

运行时按键：

```
q 退出
n 跳过当前动作
r 重置视觉计数起始位
```

按 `q`、关闭训练窗口或在终端按 `Ctrl+C` 会立即停止当前语音并退出，不再等待整段播报结束。

运行结果会保存到 `test_pose/knee_desktop_session_*/summary.json`。

## 相较本地版本的最新改动说明

本次工作目录已更新为队友保存在 `therapy_proj` 中的最新版本，并保留当前仓库的 Git 历史。相较于原本以 Python 原型、网页 demo 和若干实验脚本为主的本地版本，队友版本主要做了以下扩展和调整：

### 1. 新增 FastAPI 后端 MVP

新增 `backend/` 目录，提供智能骨科康复伴侣的后端服务：

- `backend/app/main.py` 创建 FastAPI 应用，启动时初始化数据库，并挂载处方和训练记录接口。
- `backend/app/api/routes/prescription.py` 新增 `/api/prescription/{user_id}`，会读取用户最近一次训练记录中的疼痛评分，并生成当日训练处方。
- `backend/app/api/routes/daily_record.py` 新增 `/api/daily_record`，用于保存训练后的疼痛评分、达标率、最大角度和完成组数。
- `backend/app/models/`、`backend/app/schemas/`、`backend/app/db/` 新增 SQLAlchemy 异步数据库模型、Pydantic 数据结构和 SQLite 连接初始化。
- `backend/app/services/prescription_engine.py` 新增规则处方引擎，会根据疼痛评分粗略调整训练强度。
- `backend/app/services/knee_rehab_library.py` 新增膝关节术后康复动作库，包含踝泵、股四头肌等长、腘绳肌等长、直抬腿、侧抬腿、后抬腿、内收抬腿等动作的目的、剂量、动作标准、执行步骤、评估方式、语音提示和停止规则。
- 新增 `backend/requirements.txt`，后端依赖与根目录 OpenCV/MediaPipe 原型依赖分离。

### 2. 新增 Flutter 移动端 MVP

新增 `mobile/` 目录，提供移动端训练流程源码：

- `mobile/lib/app/app.dart` 和 `mobile/lib/main.dart` 搭建 Flutter Material 3 应用入口。
- `mobile/lib/features/home/` 新增首页，展示后端返回的今日处方、完整康复计划和疼痛评分滑条。
- `mobile/lib/features/training/` 新增摄像头训练页，接入相机预览、姿态识别、训练进度、当前角度、动作计数和语音反馈。
- `mobile/lib/features/summary/` 新增训练总结页，展示达标率、完成动作数、最大角度、疼痛评分和各动作结果，并可提交到后端。
- `mobile/lib/core/services/` 新增摄像头、ML Kit Pose 姿态识别和 Flutter TTS 服务。
- `mobile/lib/core/utils/angle_calculator.dart` 新增膝关节 2D 内角计算与临床屈曲角转换逻辑。
- `mobile/lib/data/` 新增处方、训练结果、训练记录请求模型和后端 API client。
- `mobile/pubspec.yaml` 新增 Flutter 依赖，包括 `camera`、`google_mlkit_pose_detection`、`flutter_tts`、`permission_handler`、`http` 和 Riverpod。

### 3. 新增电脑端完整膝关节训练脚本

新增 `knee_rehab_desktop_session.py`，不再只是单一屈膝角度检测，而是一个 MacBook 电脑端完整训练 session：

- 默认训练顺序包括踝泵、股四头肌等长、腘绳肌等长、仰卧直抬腿、侧抬腿、后抬腿、内收抬腿等动作。
- 支持 `--list` 查看动作列表、`--target` 调整每个动作目标次数、`--list-cameras` 查看摄像头、`--probe-cameras` 实际探测可打开的摄像头。
- macOS 上强制使用 OpenCV `AVFOUNDATION` 摄像头后端，避免误触发 `OBSENSOR/Orbbec` 后端造成无设备异常。
- 训练流程从“检测瞬间抬起/放下”升级为“起始位稳定 -> 达到目标位 -> 保持达标 -> 控制回到起始位 -> 计 1 次”。
- 支持短句 edge-tts 本地语音缓存，训练时优先播放本地 mp3，缓存不可用时才回退到 macOS `say`。
- 支持按 `q` 退出、`n` 跳过当前动作、`r` 重置视觉计数起始位；退出时会立即停止当前语音。
- 训练结果会保存到 `test_pose/knee_desktop_session_*/summary.json`。

### 4. 新增电脑端动作定义库

新增 `rehab_actions/` 目录，把电脑端训练动作从主脚本中拆出：

- `rehab_actions/knee_desktop_library.py` 定义电脑端可执行动作、计时阶段、目标次数、视觉阈值、保持时间和短语音提示。
- 动作模式区分为踝泵混合评估、计时器动作、视觉动作和屈膝视觉动作，方便后续继续扩展。
- 后端处方动作库仍保留在 `backend/app/services/knee_rehab_library.py`，电脑端动作库与后端处方库各自承担不同职责。

### 5. 原有原型和网页 demo 也被同步更新

队友版本替换了原有 `rehab_web/`、`serve_rehab_web.py`、`step1_knee_bending_v1.py`、`step2_shoulder_rehab.py`、`step3_VLM_Prompt.py`、`error_map.py` 和 `TTS_SETUP.md`：

- `rehab_web/` 仍作为网页 demo 保留，但页面结构、样式和前端逻辑已与队友版本对齐。
- 根目录 `requirements.txt` 更新了 Python 原型脚本依赖版本，新增 `urllib3<2` 和 `matplotlib`，并继续保留 OpenCV、MediaPipe、edge-tts、pygame 等运行依赖。
- `TTS_SETUP.md` 和 README 中补充了 edge-tts 缓存、电脑端训练脚本、后端环境和 Flutter 运行方式。

### 6. 忽略规则和本地生成物处理

`.gitignore` 已扩展以覆盖更多本地生成物：

- Python 缓存、虚拟环境、测试/类型检查缓存、覆盖率文件。
- SQLite 数据库文件和 journal 文件。
- Flutter/Dart 生成目录。
- 姿态截图目录 `test_pose/`、语音缓存目录 `feedback_audio/`、临时测试音频。
- IDE 配置、日志、临时文件和 `.DS_Store`。

当前合并后不再保留 `therapy_proj/` 目录，根目录就是队友版本本身；本地额外文档 `动作规范.md` 按要求继续保留。
