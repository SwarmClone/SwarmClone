import os
import sys
import base64
import warnings
import shutil
import socket
import threading

from swarmclone_old.config import config
from swarmclone.modules import ModuleRoles, ModuleBase
from swarmclone.messages import Message, TTSFinished, TTSAlignment, LLMMessage

from cosyvoice.cli.cosyvoice import CosyVoice   # type: ignore
from .align import download_model_and_dict, init_mfa_models, align, match_textgrid
from .funcs import tts_generate

# 忽略警告
warnings.filterwarnings("ignore", message=".*LoRACompatibleLinear.*")
warnings.filterwarnings("ignore", message=".*torch.nn.utils.weight_norm.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_only=False.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=r".*weights_norm.*")

is_linux = sys.platform.startswith("linux")
def init_tts():
    # TTS Model 初始化
    try:
        model_path = os.path.expanduser(config.tts.cosyvoice.model_path)
        if is_linux:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} & {config.tts.cosyvoice.sft_model} 进行生成。")
            cosyvoice_sft = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.sft_model), fp16=config.tts.cosyvoice.float16)
            cosyvoice_ins = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.ins_model), fp16=config.tts.cosyvoice.float16)
        else:
            print(f" * 将使用 {config.tts.cosyvoice.ins_model} 进行生成。")
            cosyvoice_sft = None
            cosyvoice_ins = CosyVoice(os.path.join(model_path, config.tts.cosyvoice.ins_model), fp16=config.tts.cosyvoice.float16)
    except Exception as e:
        err_msg = str(e).lower()
        if ("file" in err_msg) and ("doesn't" in err_msg) and ("exist" in err_msg):
            catch = input(" * CosyVoice TTS 发生了错误，这可能是由于模型下载不完全导致的，是否清理缓存TTS模型？[y/n] ")
            if catch.strip().lower() == "y":
                shutil.rmtree(os.path.expanduser(config.tts.cosyvoice.model_path), ignore_errors=True)
                print(" * 清理完成，请重新运行该模块。")
                sys.exit(0)
            else:
                raise
        else:
            raise

    # MFA MODEL 初始化
    mfa_dir = os.path.expanduser(os.path.join(config.tts.cosyvoice.model_path, "mfa"))
    if not (
        os.path.exists(mfa_dir) and
        os.path.exists(os.path.join(mfa_dir, "mandarin_china_mfa.dict")) and
        os.path.exists(os.path.join(mfa_dir, "mandarin_mfa.zip"))
        # os.path.exists(os.path.join(mfa_dir, "english_mfa.zip")) and
        # os.path.exists(os.path.join(mfa_dir, "english_mfa.dict"))
        ):
        print(" * SwarmClone 使用 Montreal Forced Aligner 进行对齐，开始下载: ")
        download_model_and_dict(config.tts.cosyvoice)
    zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner = init_mfa_models(config.tts.cosyvoice, lang="zh-CN")
    # TODO: 英文还需要检查其他一些依赖问题
    # en_acoustic, en_lexicon, en_tokenizer, en_aligner = init_mfa_models(tts_config, lang="en-US")

    return {"tts": (cosyvoice_sft, cosyvoice_ins), "mfa": (zh_acoustic, zh_lexicon, zh_tokenizer, zh_aligner)}


class TTSNetworkServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = ('localhost', config.tts.port)
        print(" * TTS Server Start...")
        self.server.bind(address)
        self.server.listen(1)
        
        self.client_conn = None
        self.client_addr = None
        self.running = True

        self.thread = threading.Thread(target=self.run)
        self.thread.start() 

        self.connected = False

    def accpet_client(self):
        while self.running:
            try:
                client_conn, client_addr = self.server.accept()
                print(f" * TTS Server Connected by {client_addr}")
                if self.client_conn:
                    self.client_conn.close()
                self.client_conn = client_conn
                self.client_addr = client_addr
                self.connected = True
            except:
                if self.running:
                    print(" * TTS Server Accept Error")

    def send(self, audio_name):
        if self.client_conn:
            try:
                with open(audio_name, "rb") as f:
                    data = f.read()
                data = base64.b64encode(data).decode("utf-8")
                length = len(data).to_bytes(4, byteorder='big')
                self.client_conn.sendall(length + data.encode("utf-8"))
            except:
                print(" * TTS Server Send Error")
                self.client_conn.close()
                self.client_conn = None
                self.connected = False
                
    def close(self):
        if self.client_conn:
            self.client_conn.close()
            self.client_conn = None
        self.server.close()
        self.running = False
        self.connected = False
        print(" * TTS Server Closed")
        
        
class TTSCosyvoice(ModuleBase):
    def __init__(self, tts_server: TTSNetworkServer):
        super().__init__(ModuleRoles.TTS, "TTSCosyvoice")
        init = init_tts()
        self.cosyvoice_sft, self.cosyvoice_ins = init["tts"]
        self.zh_acoustic, self.zh_lexicon, self.zh_tokenizer, self.zh_aligner = init["mfa"]
        del init
        
        self.tts_server = tts_server
        assert self.tts_server.connected, " * TTS Server have not connected yet."

    async def process_task(self, task: Message | None) -> Message | None:
        assert task is LLMMessage
        id = task.get_value(self).get("id", None)
        content = task.get_value(self).get("content", None)
        emotions = task.get_value(self).get("emotion", None)

        try:
            output = tts_generate(
                tts=[self.cosyvoice_ins] if not is_linux else [self.cosyvoice_sft, self.cosyvoice_ins],
                s=content.strip(),
                tune=config.tts.cosyvoice.tune,
                emotions=emotions,
                is_linux=is_linux
            )
        except:
            print(f" * 生成时出错，跳过了 '{content}'。")
            self.results_queue.put(TTSFinished(self))
            return None
            
        # 音频文件
        audio_name = os.path.join(temp_dir, f"voice{time()}.wav")
        torchaudio.save(audio_name, output, 22050)
        # 字幕文件
        txt_name = audio_name.replace(".wav", ".txt")
        open(txt_name, "w", encoding="utf-8").write(str(content))
        # 对齐文件
        align_name = audio_name.replace(".wav", ".TextGrid")
        try:
            align(audio_name, txt_name, self.zh_acoustic, self.zh_lexicon, self.zh_tokenizer, self.zh_aligner)
        except:
            print(f" * MFA 在处理 '{content}' 产生了对齐错误。")
            align_name = "err"

        if align_name != "err":
            intervals = match_textgrid(align_name, txt_name)
        else:
            intervals = [{"token": open(txt_name, "r", encoding="utf-8").read() + " ",
                          "duration": pygame_mixer.Sound(audio_name).get_length()}]
        for interval in intervals:
            await self.results_queue.put(TTSAlignment(self,
                                                id=id,
                                                token=interval["token"],
                                                duration=interval["duration"]))
        await self.results_queue.put(TTSFinished(self))
        self.tts_server.send(audio_name)
        
        return None


            
            
            