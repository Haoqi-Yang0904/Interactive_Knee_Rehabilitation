# 本地语音模型接入说明

当前程序默认优先使用 `edge-tts` 的中文神经网络音色，失败时回退到 macOS 自带的 `say`。

```bash
python3 step1_MediaPipe.py
```

可以手动切换音色和语速：

```bash
EDGE_VOICE=zh-CN-XiaoyiNeural EDGE_RATE=-10% python3 step1_MediaPipe.py
```

常用中文音色可以先试：

- `zh-CN-XiaoxiaoNeural`
- `zh-CN-XiaoyiNeural`
- `zh-CN-YunjianNeural`
- `zh-CN-YunxiNeural`

注意：`edge-tts` 的 Python 包是免费的，但它使用在线语音服务，不是本地开源模型；需要网络。

MeloTTS 也已经接成可选后端；如果要改用本地开源中文语音模型：

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

如果 MeloTTS 没装好或加载失败，程序会自动回退到系统语音，不影响姿态识别功能。

注意：在这台机器上，MeloTTS 的 CPU 合成可能比较慢。建议先用下面的命令单独试跑：

```bash
TTS_ENGINE=melo MELO_DEVICE=cpu MELO_SPEED=0.95 python3 step1_MediaPipe.py
```

如果运行时第一次语音很久才出来，说明模型加载/合成较慢；这时可以继续用默认 `say`，或者后续改接云端 TTS。
