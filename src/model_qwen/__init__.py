from .config_qwen2 import Qwen2Config
import os
from transformers import ( # type: ignore
    AutoModelForCausalLM,
    AutoTokenizer
)

qwen2_config = Qwen2Config()

successful = False
abs_model_path = os.path.expanduser(qwen2_config.MODEL_PATH)
while not successful:
    try:
        print(f"正在从{abs_model_path}加载模型……")
        model = AutoModelForCausalLM.from_pretrained(abs_model_path, torch_dtype="auto", device_map="auto")
        tokenizer = AutoTokenizer.from_pretrained(abs_model_path, padding_side="left")
        successful = True
    except Exception as e:
        print(e)
        choice = input("加载模型失败，是否下载模型？(Y/n)")
        if choice.lower() != "n":
            import huggingface_hub # type: ignore
            huggingface_hub.snapshot_download(
                repo_id=qwen2_config.MODEL_ID,
                repo_type="model",
                local_dir=abs_model_path,
                endpoint="https://hf-mirror.com"
            )
