from modelscope import snapshot_download as modelscope_snapshot_download
from huggingface_hub import snapshot_download as huggingface_snapshot_download

def download_model(model_id: str, model_source: str, local_dir: str):
    match model_source:
        case "modelscope":
            modelscope_snapshot_download(model_id, local_dir=local_dir, repo_type="model")
        case "huggingface":
            huggingface_snapshot_download(model_id, local_dir=local_dir, repo_type="model")
        case x if x.startswith("openai+"):
            raise ValueError((
                f"OpenAI API模型不能被下载。"
                "如果你在使用`LLMTransformers`（默认选项）时遇到了这个问题，"
                "请转而使用`LLMOpenAI`。"
            ))
        case _:
            raise ValueError(f"Invalid model source: {model_source}")
