from ..config import config
import os
from transformers import ( # type: ignore
    AutoModelForCausalLM,
    AutoTokenizer
)

successful = False
abs_model_path = os.path.expanduser(config.llm.minilm2.model_path)
while not successful:
    try:
        print(f"正在从{abs_model_path}加载模型……")
        model = AutoModelForCausalLM.from_pretrained(
            abs_model_path,
            torch_dtype="auto",
            trust_remote_code=True
        ).to(config.llm.device)
        tokenizer = AutoTokenizer.from_pretrained(
            abs_model_path,
            padding_side="left",
            trust_remote_code=True
        )
        successful = True
    except Exception as e:
        print(e)
        choice = input("加载模型失败，是否下载模型？(Y/n)")
        if choice.lower() != "n":
            from modelscope.hub.snapshot_download import snapshot_download # type: ignore
            snapshot_download(
                repo_id=config.llm.minilm2.model_id,
                repo_type="model",
                local_dir=abs_model_path
            )

