from .constants import *
from .utils import *
from .modules import *
from .messages import *
from dataclasses import dataclass, field
import live2d.v2 as live2d_v2
import live2d.v3 as live2d_v3
from PySide6.QtWidgets import *
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import *
from PySide6.QtCore import QTimerEvent, Qt
from OpenGL.GL import *

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
        self.setFixedHeight(100)
    
    def paintEvent(self, event: QPaintEvent, /) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        brush = QBrush(QColor(0, 0, 0, 200))
        painter.setBrush(brush)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(self.rect(), 12, 12)
        return super().paintEvent(event)

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
        self.model.Draw()
    
    def timerEvent(self, event: QTimerEvent, /) -> None:
        self.update()

class FrontendWindow(QMainWindow):
    def __init__(self, model_path: str):
        super().__init__()
        self.setWindowTitle("Live2D")
        self.resize(500, 900)
        # 【Live2D形象】(500, 800)
        # ------------
        # 【此处字幕】(500, 100)
        widget = QWidget()
        self.setCentralWidget(widget)

        layout = QVBoxLayout(widget)
        
        self.live2d_widget = Live2DWidget(model_path)
        layout.addWidget(self.live2d_widget)

        self.label = ModelLabel("Hello, Live2D!")
        layout.addWidget(self.label)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet("background: transparent;")
    
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() & Qt.MouseButton.LeftButton:
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
        self.model_path = self.config.model
        self.app = QApplication([])
        self.window = FrontendWindow(self.model_path)
    
    async def run(self):
        self.window.show()
        asyncio.create_task(qt_poller(self.app))
        i = 0
        while True:
            try:
                await asyncio.sleep(1)
                self.window.label.setText(str(i := i + 1))
            except asyncio.CancelledError:
                self.window.live2d_widget.live2d.dispose()
                self.app.quit()
                return

"""
若你使用的是 NVIDIA GPU 且出现了着色器编译失败的情况，请通过Zink来使用 Vulkan 代替 OpenGL ，此处以 Arch Linux 为例子：
env __GLX_VENDOR_LIBRARY_NAME=mesa __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink python -m swarmclone
若你使用的是 Wayland ，且出现了无法拖动窗口的情况，请通过 XWayland 来使用 X11 代替 Wayland：
QT_QPA_PLATFORM="xcb" python -m swarmclone
若你同时出现以上两种情况，则请将两种方法结合使用：
env __GLX_VENDOR_LIBRARY_NAME=mesa __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json MESA_LOADER_DRIVER_OVERRIDE=zink GALLIUM_DRIVER=zink QT_QPA_PLATFORM="xcb" python -m swarmclone
"""