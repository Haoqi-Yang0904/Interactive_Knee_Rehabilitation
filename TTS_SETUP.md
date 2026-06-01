# 本地语音模型接入说明

当前电脑端膝关节训练程序默认优先使用 `edge-tts` 的中文神经网络音色，并把短语音缓存成 mp3；失败时回退到 macOS 自带的 `say`。

```bash
cd /Users/xieluxiang/therapy_proj
/Users/xieluxiang/therapy_proj/backend/.venv/bin/python knee_rehab_desktop_session.py --target 3
```

可以手动切换音色和语速：

```bash
/Users/xieluxiang/therapy_proj/backend/.venv/bin/python knee_rehab_desktop_session.py --target 3 --edge-voice zh-CN-XiaoyiNeural --edge-rate -10%
```

先单独生成或补齐本地语音缓存：

```bash
/Users/xieluxiang/therapy_proj/backend/.venv/bin/python knee_rehab_desktop_session.py --target 10 --prepare-voice-cache
```

当前脚本使用短句提示，例如“准备，开始。”“勾脚。”“抬起。”“保持。”“放下。”，并且计时会等语音播完后再开始。动作开始前默认额外等待 2 秒，可用 `--reaction-seconds 2.5` 调整。股四头肌等长和腘绳肌等长会识别起始位稳定后自动开始。

常用中文音色可以先试：

- `zh-CN-XiaoxiaoNeural`
- `zh-CN-XiaoyiNeural`
- `zh-CN-YunjianNeural`
- `zh-CN-YunxiNeural`

注意：`edge-tts` 的 Python 包是免费的，但生成缓存时使用在线语音服务，不是本地开源模型；需要网络。缓存生成后，训练过程中优先播放本地 mp3。

下面是早期屈膝原型脚本的 MeloTTS 试验说明；当前完整膝关节桌面训练脚本还没有接入 MeloTTS，只使用 edge-tts 生成本地 mp3 缓存。

如果要在旧原型里改用本地开源中文语音模型：

```bash
git clone https://github.com/myshell-ai/MeloTTS.git
cd MeloTTS
python3 -m pip install -e .
python3 -m unidic download
```

回到本项目后，用 MeloTTS 启动：

```bash
TTS_ENGINE=melo python3 step1_MediaPipe.py
```

可选参数：

```bash
TTS_ENGINE=melo MELO_SPEED=0.9 MELO_DEVICE=cpu python3 step1_MediaPipe.py
```

如果 MeloTTS 没装好或加载失败，旧原型程序会自动回退到系统语音，不影响姿态识别功能。

注意：在这台机器上，MeloTTS 的 CPU 合成可能比较慢。建议先用下面的命令单独试跑：

```bash
TTS_ENGINE=melo MELO_DEVICE=cpu MELO_SPEED=0.95 python3 step1_MediaPipe.py
```

如果运行时第一次语音很久才出来，说明模型加载/合成较慢；这时可以继续用默认 `say`，或者后续改接云端 TTS。
