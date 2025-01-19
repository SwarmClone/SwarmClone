import os
import requests

from pathlib import Path

import pywrapfst

from tqdm import tqdm

from kalpy.utterance import  Segment
from kalpy.feat.cmvn import CmvnComputer
from kalpy.fstext.lexicon import LexiconCompiler
from kalpy.fstext.lexicon import HierarchicalCtm
from kalpy.utterance import Utterance as KalpyUtterance

from . import tts_config
from montreal_forced_aligner import config
from montreal_forced_aligner.alignment import PretrainedAligner
from montreal_forced_aligner.models import AcousticModel
from montreal_forced_aligner.tokenization.spacy import generate_language_tokenizer
from montreal_forced_aligner.corpus.classes import FileData
from montreal_forced_aligner.online.alignment import align_utterance_online

def download_file(url, dest_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get('content-length', 0))

    with open(dest_path, "wb") as file, tqdm(
        desc=f"Downloading {os.path.basename(dest_path)}",
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024
    ) as progress_bar:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:  # Filter out keep-alive chunks
                file.write(chunk)
                progress_bar.update(len(chunk))
    print(f" * 下载完毕: {dest_path}")


def download_model_and_dict(tts_config):
    mfa_model_path = os.path.expanduser(os.path.join(tts_config.MODELPATH, "mfa"))
    os.makedirs(mfa_model_path, exist_ok=True)
    files = [["https://github.com/MontrealCorpusTools/mfa-models/releases/download/acoustic-mandarin_mfa-v3.0.0/mandarin_mfa.zip", 
              os.path.join(mfa_model_path, "mandarin_mfa.zip")], 
            ["https://github.com/MontrealCorpusTools/mfa-models/releases/download/dictionary-mandarin_china_mfa-v3.0.0/mandarin_china_mfa.dict", 
              os.path.join(mfa_model_path, "mandarin_china_mfa.dict")]]
    for file in files:
        if not os.path.exists(file[1]):
            download_file(file[0], file[1])
    
    
def init_mfa_models(tts_config):
    mfa_dict_path       = os.path.expanduser(os.path.join(tts_config.MODELPATH, "mfa", "mandarin_china_mfa.dict"))
    mfa_model_path      = os.path.expanduser(os.path.join(tts_config.MODELPATH, "mfa", "mandarin_mfa.zip"))
    dictionary_path     = Path(mfa_dict_path)
    acoustic_model_path = Path(mfa_model_path)

    acoustic_model = AcousticModel(acoustic_model_path)
    c = PretrainedAligner.parse_args(None, None)
    extracted_models_dir = dictionary_path.parent.joinpath("extracted_models", "dictionary")
    dictionary_directory = extracted_models_dir.joinpath(dictionary_path.stem)
    dictionary_directory.mkdir(parents=True, exist_ok=True)
    lexicon_compiler = LexiconCompiler(
        disambiguation=False,
        silence_probability=acoustic_model.parameters["silence_probability"],
        initial_silence_probability=acoustic_model.parameters["initial_silence_probability"],
        final_silence_correction=acoustic_model.parameters["final_silence_correction"],
        final_non_silence_correction=acoustic_model.parameters["final_non_silence_correction"],
        silence_phone=acoustic_model.parameters["optional_silence_phone"],
        oov_phone=acoustic_model.parameters["oov_phone"],
        position_dependent_phones=acoustic_model.parameters["position_dependent_phones"],
        phones=acoustic_model.parameters["non_silence_phones"],
        ignore_case=c.get("ignore_case", True),
    )

    l_fst_path = dictionary_directory.joinpath("L.fst")
    l_align_fst_path = dictionary_directory.joinpath("L_align.fst")
    words_path = dictionary_directory.joinpath("words.txt")
    phones_path = dictionary_directory.joinpath("phones.txt")
    if l_fst_path.exists() and not config.CLEAN:
        lexicon_compiler.load_l_from_file(l_fst_path)
        lexicon_compiler.load_l_align_from_file(l_align_fst_path)
        lexicon_compiler.word_table = pywrapfst.SymbolTable.read_text(words_path)
        lexicon_compiler.phone_table = pywrapfst.SymbolTable.read_text(phones_path)
    else:
        lexicon_compiler.load_pronunciations(dictionary_path)
        lexicon_compiler.fst.write(str(l_fst_path))
        lexicon_compiler.align_fst.write(str(l_align_fst_path))
        lexicon_compiler.word_table.write_text(words_path)
        lexicon_compiler.phone_table.write_text(phones_path)
        lexicon_compiler.clear()

    tokenizer = generate_language_tokenizer(acoustic_model.language)
    return acoustic_model, lexicon_compiler, tokenizer, c

def align(sound_file_path, text_file_path, acoustic_model, lexicon_compiler, tokenizer, pretrained_aligner):
    sound_file_path     = sound_file_path if isinstance(sound_file_path, Path) else Path(sound_file_path)
    text_file_path      = text_file_path if isinstance(text_file_path, Path) else Path(text_file_path)
    output_path         = sound_file_path.parent
    output_path         = output_path.joinpath(sound_file_path.stem + ".TextGrid")
    output_format       = "long_textgrid"

    file_name = sound_file_path.stem
    file = FileData.parse_file(file_name, sound_file_path, text_file_path, "", 0)
    file_ctm = HierarchicalCtm([])
    utterances = []
    cmvn_computer = CmvnComputer()

    for utterance in file.utterances:
        seg = Segment(sound_file_path, utterance.begin, utterance.end, utterance.channel)
        utt = KalpyUtterance(seg, utterance.text)
        utt.generate_mfccs(acoustic_model.mfcc_computer)
        utterances.append(utt)

    cmvn = cmvn_computer.compute_cmvn_from_features([utt.mfccs for utt in utterances])
    align_options = {
        k: v
        for k, v in pretrained_aligner.items()
        if k
        in [
            "beam",
            "retry_beam",
            "acoustic_scale",
            "transition_scale",
            "self_loop_scale",
            "boost_silence",
        ]
    }
    for utt in utterances:
        utt.apply_cmvn(cmvn)
        ctm = align_utterance_online(
            acoustic_model,
            utt,
            lexicon_compiler,
            tokenizer=tokenizer,
            g2p_model=None,
            **align_options,
        )
        file_ctm.word_intervals.extend(ctm.word_intervals)    

    if str(output_path) != "-":
        output_path.parent.mkdir(parents=True, exist_ok=True)
    file_ctm.export_textgrid(output_path, file_duration=file.wav_info.duration, output_format=output_format)
    