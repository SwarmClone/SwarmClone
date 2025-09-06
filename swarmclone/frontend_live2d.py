from swarmclone.constants import *
from swarmclone.utils import *
from swarmclone.modules import *
from swarmclone.messages import *
from dataclasses import dataclass, field
import live2d.v2 as live2d_v2
import live2d.v3 as live2d_v3
from live2d.utils.lipsync import WavHandler
from PySide6.QtWidgets import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import *
from PySide6.QtCore import QPoint, QTimerEvent, Qt
from OpenGL.GL import *
import pygame
from markdown import markdown
import time
from tempfile import NamedTemporaryFile
from typing import Any
import torchaudio
from io import BytesIO

available_models = get_live2d_models()

async def qt_poller(app: QApplication):
    while not app.closingDown():
        app.processEvents()
        await asyncio.sleep(1 / 120)

class ModelLabel(QLabel):
    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setStyleSheet("background: transparent; color: white; font: 20px; padding: 20px;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setFixedHeight(100)
    
    def paintEvent(self, event: QPaintEvent, /) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        brush = QBrush(QColor(0, 0, 0, 200))
        painter.setBrush(brush)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(self.rect(), 12, 12)
        
        # Custom text painting with bottom-up overflow
        text_rect = self.rect().adjusted(20, 20, -20, -20)  # Account for padding
        
        # Use QTextDocument for proper word wrapping with rich text support
        doc = QTextDocument()
        doc.setHtml(self.text())  # Support rich text
        doc.setDefaultFont(self.font())
        doc.setTextWidth(text_rect.width())
        doc.setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignHCenter))
        doc.setDocumentMargin(0)  # Remove internal margins
        
        # Calculate total height
        total_height = doc.size().height()
        
        # Calculate starting Y position to align from bottom
        if total_height > text_rect.height():
            # Overflow case: show bottom portion (upward overflow)
            start_y = text_rect.bottom() - total_height
        else:
            # Normal case: center vertically
            start_y = text_rect.top() + (text_rect.height() - total_height) / 2
        
        # Draw the document
        painter.save()
        painter.setClipRect(text_rect)  # Clip to visible area
        painter.translate(text_rect.left(), start_y)
        doc.drawContents(painter)
        painter.restore()

class ChatRecordWidget(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background: transparent; color: white; font: 20px; padding: 20px;")
        self.setAcceptRichText(True)
        self.setReadOnly(True)
        self.appendRecord("系统", "开始")

    def paintEvent(self, event): # By: Kimi-K2
        # 1. 在 viewport 上绘制背景
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        brush = QBrush(QColor(0, 0, 0, 200))
        painter.setBrush(brush)
        painter.setPen(QPen(Qt.PenStyle.NoPen))

        # 2. 用 viewport 的 rect（可减去滚动条的 margin）
        rect = self.viewport().rect()
        painter.drawRoundedRect(rect, 12, 12)

        # 3. 继续让父类完成文本本身的绘制
        super().paintEvent(event)
    
    def appendRecord(self, name: str, content: str):
        processed_content = markdown(content).strip()
        # Remove <p> tags that markdown might add, as they cause line breaks
        if processed_content.startswith('<p>') and processed_content.endswith('</p>'):
            processed_content = processed_content[3:-4]
        self.append(f"<b>{name}</b>: {processed_content}")
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

class Live2DWidget(QOpenGLWidget):
    def __init__(self, model_path: str):
        super().__init__()
        self.model: live2d_v2.LAppModel | live2d_v3.LAppModel
        self.model_path = model_path
        # 根据模型文件后缀推断版本
        if model_path.endswith(".model.json"): # v2
            self.live2d = live2d_v2
        elif model_path.endswith(".model3.json"): # v3
            self.live2d = live2d_v3
        else:
            raise ValueError(f"模型文件后缀名错误，必须为 .model.json 或 .model3.json")
        self.live2d.init()
        self.wav_hander = WavHandler()
        self.lip_sync_n = 3
    
    def initializeGL(self, /) -> None:
        if self.live2d.LIVE2D_VERSION == 2:
            self.live2d.glewInit()
        else:
            self.live2d.glInit()
        print(f"加载模型：{self.model_path}")
        self.model = self.live2d.LAppModel()
        self.model.LoadModelJson(self.model_path)
        self.startTimer(1000 // 120)
    
    def resizeGL(self, w: int, h: int, /) -> None:
        glViewport(0, 0, w, h)
        self.model.Resize(w, h)
    
    def paintGL(self, /) -> None:
        self.live2d.clearBuffer()
        self.model.Update()
        if self.wav_hander.Update():
            self.model.SetParameterValue("ParamMouthOpenY", self.wav_hander.currentRms * self.lip_sync_n)
        self.model.Draw()
    
    def timerEvent(self, event: QTimerEvent, /) -> None:
        self.update()
    
    def speak(self, fname: str):
        self.wav_hander.Start(fname)
        print(self.wav_hander.pcmData)

class FrontendWindow(QMainWindow):
    def __init__(self, model_path: str):
        super().__init__()
        self.setWindowTitle("Live2D")
        self.resize(800, 900)
        # 【Live2D形象】(400, 800) | 此处是
        # -----------------------+ 聊天 (400, 900)
        # 【此处字幕】(400, 100)   | 记录
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QHBoxLayout(widget)

        # 左侧：Live2D 与字幕
        left = QWidget()
        left.setFixedWidth(400)
        layout.addWidget(left)
        layout_left = QVBoxLayout(left)
        # 左上：Live2D
        self.live2d_widget = Live2DWidget(model_path)
        layout_left.addWidget(self.live2d_widget)
        # 左下：字幕
        self.label = ModelLabel("")
        layout_left.addWidget(self.label)

        # 右侧：聊天记录
        self.chat_record_widget = ChatRecordWidget()
        layout.addWidget(self.chat_record_widget)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background: transparent;")

        self._drag_pos: QPoint | None = None
    
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            delta = e.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = e.globalPosition().toPoint()

@dataclass
class FrontendLive2DConfig(ModuleConfig):
    model: str = field(default=[*available_models.values()][0], metadata={
        "required": True,
        "desc": "Live2D模型",
        "selection": True,
        "options": [
            {"key": k, "value": v} for k, v in available_models.items()
        ]
    })

class FrontendLive2D(ModuleBase):
    """使用 live2d-py 和 PySide6 驱动的 Live2D 前端"""
    role: ModuleRoles = ModuleRoles.FRONTEND
    config_class = FrontendLive2DConfig
    config: config_class
    def __init__(self, config: config_class | None = None, **kwargs):
        super().__init__(config, **kwargs)
        pygame.mixer.init()
        self.model_path = self.config.model
        self.app = QApplication([])
        self.window = FrontendWindow(self.model_path)
        self.align_t0: float = float("inf")
        self.song_info: dict[str, dict[str, str]] = {}
        self.singing = False
        self.label_buffer = ""
        self.message_queue: list[Any] = []
        """
        [
            {
                "id": 【消息ID】,
                "message": 【消息内容】,
                "aligned_audio": {
                    "data": 【音频字节串】,
                    "align_data": [
                        {
                            "token": 【这一段对应的文本】,
                            "duration": 【这一段的持续时间】
                        }, ...
                    ]
                }
            }, ...
        ]
        """
    
    async def run(self):
        self.window.show()
        asyncio.create_task(qt_poller(self.app))
        try:
            while True:
                await asyncio.sleep(1 / 60)
                try:
                    task = self.task_queue.get_nowait()
                except asyncio.QueueEmpty:
                    task = None
                
                # 处理消息部分
                if isinstance(task, ASRActivated) and not self.singing:
                    # 如果收到了 ASR 激活信息，则马上清空当前消息
                    for message in self.message_queue:
                        self.label_buffer += message["message"]
                    self.message_queue.clear()
                    if self.label_buffer.strip():
                        self.window.chat_record_widget.appendRecord("Model", self.label_buffer)
                        self.label_buffer = ""
                
                elif isinstance(task, ASRMessage):
                    # 若接收到 ASR 信息，则马上加入聊天记录
                    data = task.get_value(self)
                    self.window.chat_record_widget.appendRecord(data["speaker_name"], data["message"])
                
                elif isinstance(task, LLMMessage):
                    # 若接收到 LLM 信息，接受进新消息中并标注为未生成音频
                    data = task.get_value(self)
                    self.message_queue.append({"id": data["id"], "message": data["content"], "aligned_audio": None})
                
                elif isinstance(task, LLMEOS):
                    # 若接收到 LLM 停止信息，则加入停止标记进队列中
                    self.message_queue.append({"id": None, "aligned_audio": None})
                
                elif isinstance(task, TTSAlignedAudio):
                    # 若接收到 TTS 对齐信息，将对应消息标注为已生成音频
                    data = task.get_value(self)
                    data_index: int | None = None
                    for data_index, message in enumerate(self.message_queue):
                        if message["id"] == data["id"] and message["aligned_audio"] is None:
                            message["aligned_audio"] = {
                                "data": data["data"],
                                "align_data": data["align_data"]
                            }
                            break
                    # 若后面的信息先收到了生成音频，则将前面的消息缺失的音频信息用缺省值代替
                    if data_index is not None:
                        for i in range(data_index):
                            if self.message_queue[i]["aligned_audio"] is None:
                                self.message_queue[i]["aligned_audio"] = b""
                
                elif isinstance(task, SongInfo):
                    # 接收歌曲相关信息
                    data = task.get_value(self)
                    self.song_info[data["song_id"]] = {
                        "song_path": data["song_path"],
                        "subtitle_path": data["subtitle_path"],
                        "vocal_path": data["vocal_path"]
                    }
                
                elif isinstance(task, ReadyToSing):
                    # 准备好播放歌曲时直接开始播放
                    self.message_queue.clear()
                    data = task.get_value(self)
                    song_id = data["song_id"]
                    if not song_id in self.song_info:
                        await self.results_queue.put(FinishedSinging(self)) # 歌曲不存在，直接当作播放完成
                    else:
                        self.singing = True
                        self.align_t0 = time.time()
                        align_data = parse_srt_to_list(open(self.song_info[song_id]["subtitle_path"]).read())
                        self.message_queue.append({
                            "id": f"SONG_{song_id}",
                            "message": f"Model 唱了 {song_id}",
                            "aligned_audio": {
                                "data": open(self.song_info[song_id]["vocal_path"], "rb").read(),
                                "song_data": open(self.song_info[song_id]["song_path"], "rb").read(),
                                "align_data": align_data
                            }
                        })
                        self.message_queue.append({
                            "id": f"SONG_{song_id}_END",
                            "message": None,
                            "aligned_audio": None
                        })
                
                # 更新字幕部分
                if self.message_queue:
                    if self.message_queue[0]["aligned_audio"] is not None:
                        # 如果已经生成了音频，则进行对齐展示
                        if self.message_queue[0]["aligned_audio"]["data"] is not None:
                            # 如果还没有播放音频（音频项还有数据）则播放音频并清空其数据，同时开始计时
                            if self.message_queue[0]["aligned_audio"]["data"]: # 可能存有缺省值，只在确定有音频时播放
                                with NamedTemporaryFile() as f:
                                    audio_bytesio = BytesIO(self.message_queue[0]["aligned_audio"]["data"])
                                    data = torchaudio.load(audio_bytesio)
                                    audio_bytesio.seek(0)
                                    info = torchaudio.info(audio_bytesio)
                                    audio_bytesio.seek(0)
                                    torchaudio.save(
                                        f.name,
                                        data[0],
                                        sample_rate=info.sample_rate,
                                        format="wav",
                                        encoding="PCM_S",
                                        bits_per_sample=16,
                                    ) # 保存为 16 bit wave 格式以便 live2d 进行口型对齐
                                    f.seek(0)
                                    if "song_data" not in self.message_queue[0]["aligned_audio"]: # 是纯人声，直接播放
                                        pygame.mixer.music.stop()
                                        pygame.mixer.music.load(audio_bytesio)
                                        pygame.mixer.music.play()
                                    self.window.live2d_widget.speak(f.name) # 只使用纯人声进行口型对齐
                            if "song_data" in self.message_queue[0]["aligned_audio"]: # 不是纯人声则播放歌曲
                                pygame.mixer.music.stop()
                                pygame.mixer.music.load(BytesIO(self.message_queue[0]["aligned_audio"]["song_data"]))
                                pygame.mixer.music.play()
                            self.message_queue[0]["aligned_audio"]["data"] = None
                            self.align_t0 = time.time()
                        if time.time() - self.align_t0 > self.message_queue[0]["aligned_audio"]["align_data"][0]["duration"]:
                            # 如果计时时间达到了最近一项对齐数据的时间，则展示这条数据并清除这条数据
                            self.label_buffer += self.message_queue[0]["aligned_audio"]["align_data"][0]["token"]
                            self.align_t0 += self.message_queue[0]["aligned_audio"]["align_data"][0]["duration"]
                            self.message_queue[0]["aligned_audio"]["align_data"].pop(0)
                            if not self.message_queue[0]["aligned_audio"]["align_data"]:
                                # 如果已经将所有对齐数据播放完毕，则清除这条数据
                                self.message_queue.pop(0)
                            # 展示字幕
                            self.window.label.setText(markdown(self.label_buffer))
                    if self.message_queue and self.message_queue[0]["id"] is None:
                        # 遇到停止生成标记，说明一段完整信息已经播放完毕
                        self.message_queue.pop(0)
                        self.window.chat_record_widget.appendRecord("Model", self.label_buffer)
                        self.label_buffer = ""
                        self.window.label.setText("")
                        if self.singing:
                            await self.results_queue.put(FinishedSinging(self))
                            self.singing = False
                        else:
                            await self.results_queue.put(AudioFinished(self))
        except:
            import traceback; traceback.print_exc()
        finally:
            self.window.live2d_widget.live2d.dispose()
            self.app.quit()

"""
若你使用的是 NVIDIA GPU 且出现了着色器编译失败的情况，请通过 Zink 来使用 Vulkan 代替 OpenGL ，此处以 Arch Linux 为例子：
env __GLX_VENDOR_LIBRARY_NAME=mesa __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink python -m swarmclone
若你使用的是 Wayland ，且出现了无法拖动窗口的情况，请通过 XWayland 来使用 X11 代替 Wayland：
QT_QPA_PLATFORM="xcb" python -m swarmclone
若你同时出现以上两种情况，则请将两种方法结合使用：
env __GLX_VENDOR_LIBRARY_NAME=mesa __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink QT_QPA_PLATFORM="xcb" python -m swarmclone
"""