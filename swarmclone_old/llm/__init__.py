from ..config import config
import os
from transformers import ( # type: ignore
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer
)

successful = False
abs_model_path = os.path.expanduser(config.llm.minilm2.model_path)
abs_classifier_path = os.path.expanduser(config.llm.emotionclassification.model_path)
while not successful: # 加载大语言模型
    try:
        print(f"正在从{abs_model_path}加载语言模型……")
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

successful = False
while not successful: # 加载情感分类模型
    try:
        print(f"正在从{abs_classifier_path}加载情感分类模型……")
        classifier_model = AutoModelForSequenceClassification.from_pretrained(
            abs_classifier_path,
            torch_dtype="auto",
            trust_remote_code=True
        ).to(config.llm.device)
        classifier_tokenizer = AutoTokenizer.from_pretrained(
            abs_classifier_path,
            padding_side="left",
            trust_remote_code=True
        )
        successful = True
    except Exception as e:
        print(e)
        choice = input("加载模型失败，是否下载模型？(Y/n)")
        if choice.lower() != "n":
            from huggingface_hub import snapshot_download # type: ignore
            snapshot_download(
                repo_id=config.llm.emotionclassification.model_id,
                repo_type="model",
                local_dir=abs_classifier_path
            )

