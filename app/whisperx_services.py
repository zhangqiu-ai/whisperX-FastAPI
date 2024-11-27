"""This module provides services for transcribing, diarizing, and aligning audio using Whisper and other models."""

import gc
from datetime import datetime

import torch
from whisperx import (
    DiarizationPipeline,
    align,
    assign_word_speakers,
    load_align_model,
    load_model,
)

from .config import Config
from .logger import logger  # Import the logger from the new module
from .schemas import AlignedTranscription, SpeechToTextProcessingParams
from .tasks import update_task_status_in_db
from .transcript import filter_aligned_transcription

LANG = Config.LANG
HF_TOKEN = Config.HF_TOKEN
WHISPER_MODEL = Config.WHISPER_MODEL
device = Config.DEVICE
compute_type = Config.COMPUTE_TYPE


def transcribe_with_whisper(
    audio,
    task,
    asr_options,
    vad_options,
    language,
    batch_size: int = 16,
    model: str = WHISPER_MODEL,
    device: str = device,
    device_index: int = 0,
    compute_type: str = compute_type,
    threads: int = 0,
):
    """
    Transcribe an audio file using the Whisper model.

    Args:
       audio (Audio): The audio to transcribe.
       batch_size (int): Batch size for transcription (default 16).
       model (str): Name of the Whisper model to use.
       device (str): Device to use for PyTorch inference.
       device_index (int): Device index to use for FasterWhisper inference.
       compute_type (str): Compute type for computation.

    Returns:
       Transcript: The transcription result.
    """
    logger.debug(
        "Starting transcription with Whisper model: %s on device: %s",
        WHISPER_MODEL,
        device,
    )
    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )
    faster_whisper_threads = 4
    if (threads := threads) > 0:
        torch.set_num_threads(threads)
        faster_whisper_threads = threads

    logger.debug(
        "Loading model with config - model: %s, device: %s, compute_type: %s, threads: %d, task: %s, language: %s",
        model,
        device,
        compute_type,
        faster_whisper_threads,
        task,
        language,
    )
    model = load_model(
        model,
        device,
        device_index=device_index,
        compute_type=compute_type,
        asr_options=asr_options,
        vad_options=vad_options,
        language=language,
        task=task,
        threads=faster_whisper_threads,
    )
    logger.debug("Transcription model loaded successfully")
    result = model.transcribe(audio=audio, batch_size=batch_size, language=language)

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    logger.debug("Completed transcription")
    return result


def diarize(audio, device: str = device, min_speakers=None, max_speakers=None):
    """
    Diarize an audio file using the PyAnnotate model.

    Args:
       audio (Audio): The audio to diarize.

    Returns:
       Diarizartion: The diarization result.
    """
    logger.debug("Starting diarization with device: %s", device)

    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    model = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
    result = model(audio=audio, min_speakers=min_speakers, max_speakers=max_speakers)

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del model

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    logger.debug("Completed diarization with device: %s", device)
    return result


def align_whisper_output(
    transcript,
    audio,
    language_code,
    device: str = device,
    align_model: str = None,
    interpolate_method: str = "nearest",
    return_char_alignments: bool = False,
):
    """
    Align the transcript to the original audio.

    Args:
       transcript: The text transcript.
       audio: The original audio.
       language_code: The language code.
       align_model: Name of phoneme-level ASR model to do alignment.
       interpolate_method: For word .srt, method to assign timestamps to non-aligned words, or merge them into neighboring.
       return_char_alignments: Whether to return character-level alignments in the output json file.

    Returns:
       The aligned transcript.
    """
    logger.debug(
        "Starting alignment for language code: %s on device: %s",
        language_code,
        device,
    )

    # Log GPU memory before loading model
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before loading model - used: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    logger.debug(
        "Loading align model with config - language_code: %s, device: %s, interpolate_method: %s, return_char_alignments: %s",
        language_code,
        device,
        interpolate_method,
        return_char_alignments,
    )
    align_model, align_metadata = load_align_model(
        language_code=language_code, device=device, model_name=align_model
    )

    result = align(
        transcript,
        align_model,
        align_metadata,
        audio,
        device,
        interpolate_method=interpolate_method,
        return_char_alignments=return_char_alignments,
    )

    # Log GPU memory before cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory before cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    # delete model
    gc.collect()
    torch.cuda.empty_cache()
    del align_model
    del align_metadata

    # Log GPU memory after cleanup
    if torch.cuda.is_available():
        logger.debug(
            f"GPU memory after cleanup: {torch.cuda.memory_allocated()/1024**2:.2f} MB, available: {torch.cuda.get_device_properties(0).total_memory/1024**2:.2f} MB"
        )

    logger.debug("Completed alignment")
    return result


def process_audio_common(params: SpeechToTextProcessingParams, session):
    try:
        start_time = datetime.now()
        logger.info(
            "Starting speech-to-text processing for identifier: %s",
            params.identifier,
        )

        # 第一步：语音转文字
        segments_before_alignment = transcribe_with_whisper(
            audio=params.audio,
            task=params.whisper_model_params.task,
            asr_options=params.asr_options,
            vad_options=params.vad_options,
            language=params.whisper_model_params.language,
            batch_size=params.whisper_model_params.batch_size,
            model=params.whisper_model_params.model,
            device=params.whisper_model_params.device,
            device_index=params.whisper_model_params.device_index,
            compute_type=params.whisper_model_params.compute_type,
            threads=params.whisper_model_params.threads,
        )

        # 第二步：音频对齐
        segments_transcript = align_whisper_output(
            transcript=segments_before_alignment["segments"],
            audio=params.audio,
            language_code=segments_before_alignment["language"],
            align_model=params.alignment_params.align_model,
            interpolate_method=params.alignment_params.interpolate_method,
            return_char_alignments=params.alignment_params.return_char_alignments,
        )
        transcript = AlignedTranscription(**segments_transcript)
        transcript = filter_aligned_transcription(transcript).model_dump()

        # 直接使用转录结果，跳过说话人分离
        result = transcript

        # 不再删除 words 信息，保留完整的时间戳
        # 只添加默认说话人标签
        for segment in result["segments"]:
            segment["speaker"] = "SPEAKER_01"
            if "words" in segment:
                for word in segment["words"]:
                    word["speaker"] = "SPEAKER_01"

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(
            "Completed speech-to-text processing for identifier: %s. Duration: %ss",
            params.identifier,
            duration,
        )

        update_task_status_in_db(
            identifier=params.identifier,
            update_data={
                "status": "completed",
                "result": result,
                "duration": duration,
                "start_time": start_time,
                "end_time": end_time,
            },
            session=session,
        )
    except (RuntimeError, ValueError, KeyError) as e:
        logger.error(
            "Speech-to-text processing failed for identifier: %s. Error: %s",
            params.identifier,
            str(e),
        )
        update_task_status_in_db(
            identifier=params.identifier,
            update_data={
                "status": "failed",
                "error": str(e),
            },
            session=session,
        )
    except MemoryError as e:
        logger.error(
            f"Task failed for identifier {params.identifier} due to out of memory. Error: {str(e)}"
        )
        update_task_status_in_db(
            identifier=params.identifier,
            update_data={"status": "failed", "error": str(e)},
            session=session,
        )
