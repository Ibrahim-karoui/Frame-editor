# Video Frame Editor

Video Frame Editor is a Python desktop application for frame-by-frame video editing using OpenCV and Tkinter.

It allows users to load videos, navigate through frames, remove or keep specific frames, apply custom sampling, and preview results in real time. The final edited video can be exported in high quality using FFmpeg.

It can be used for preparation of videos for labeling and annotation workflows.


## Features

- Frame-by-frame navigation
- Remove or keep individual frames
- Custom frame sampling (1/n mode)
- Real-time preview of edited video
- Go to specific frame
- Keyboard shortcuts for fast editing
- Playback speed control
- High-quality export using FFmpeg (H.264)


## Install dependencies

```bash
pip install -r requirements.txt
```

## FFmpeg installation

Download FFmpeg from:
https://www.gyan.dev/ffmpeg/builds/

Steps:
- Download `ffmpeg-release-essentials.zip`
- Extract the archive
- Go to `bin/` folder
- Copy `ffmpeg.exe`
- Paste it into `assets/` folder of the project

## Build executable (Windows)

To generate the executable using PyInstaller:

```bash
pyinstaller --onefile --windowed --add-binary "assets/ffmpeg.exe;." src/main.py
```