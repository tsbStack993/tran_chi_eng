import os
import subprocess
import yt_dlp
import whisper
from googletrans import Translator
import vlc
import tkinter as tk
from tkinter import messagebox
import torch

# --- Folders --- https://www.youtube.com/watch?v=4sjsBdPSZss
DOWNLOAD_DIR = "downloads"
SUB_DIR = "subtitles"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(SUB_DIR, exist_ok=True)

# --- Device selection ---
def get_device():
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0).lower()
        print("GPU detected:", gpu_name)
        # GTX cards (older architecture) → safer in FP32
        if "gtx" in gpu_name:
            print("Using GPU in FP32 (safe mode for GTX)")
            return "cuda-fp32"
        else:
            print("Using GPU in FP16 (fast mode for RTX/modern cards)")
            return "cuda"
    else:
        print("No GPU detected, using CPU")
        return "cpu"

# --- Functions ---
def download_video(url):
    """Download YouTube video and return the saved path"""
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def extract_audio(video_path):
    """Extract WAV audio from video"""
    base, _ = os.path.splitext(video_path)
    audio_path = base + ".wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", audio_path
    ], check=True)
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not created: {audio_path}")
    return audio_path

def generate_subtitles(audio_path, video_path):
    """Transcribe Chinese audio and translate to English subtitles"""

    # pick device
    # device_mode = get_device()
    # if device_mode == "cuda-fp32":
    #     model = whisper.load_model("base", device="cuda")
    #     model = model.to(dtype=torch.float32)
    # elif device_mode == "cuda":
    #     model = whisper.load_model("base", device="cuda")
    # else:
    #     model = whisper.load_model("base", device="cpu")

    device_mode = get_device()
    if device_mode.startswith("cuda"):
        model = whisper.load_model("base", device="cuda")
        model = model.to(dtype=torch.float32)   # 🔥 force FP32
    else:
        model = whisper.load_model("base", device="cpu")


    result = model.transcribe(audio_path, language="zh", fp16=False)

    translator = Translator()
    srt_content = ""
    for i, seg in enumerate(result['segments']):
        start = seg['start']
        end = seg['end']
        text_zh = seg['text']
        try:
            text_en = translator.translate(text_zh, src='zh-cn', dest='en').text
        except Exception:
            text_en = text_zh  # fallback if translation fa

        srt_content += f"{i+1}\n"
        srt_content += f"{format_time(start)} --> {format_time(end)}\n"
        srt_content += f"{text_en}\n\n"

    srt_path = os.path.join(
        SUB_DIR, os.path.basename(video_path).rsplit('.', 1)[0] + ".srt"
    )
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return srt_path

def format_time(seconds):
    h, m = divmod(seconds, 3600)
    m, s = divmod(m, 60)
    ms = int((s - int(s)) * 1000)
    return f"{int(h):02}:{int(m):02}:{int(s):02},{ms:03}"

def play_video(video_path, srt_path):
    """Play video with subtitles using VLC"""
    instance = vlc.Instance()
    player = instance.media_player_new()
    media = instance.media_new(video_path)
    media.add_option(f"sub-file={srt_path}")
    player.set_media(media)
    player.play()

def run():
    url = entry.get().strip()
    if not url:
        messagebox.showerror("Error", "Please enter a YouTube URL")
        return

    try:
        status_label.config(text="Downloading video...")
        root.update_idletasks()
        video_path = download_video(url)

        status_label.config(text="Extracting audio...")
        root.update_idletasks()
        audio_path = extract_audio(video_path)

        status_label.config(text="Generating subtitles (may take time)...")
        root.update_idletasks()
        srt_path = generate_subtitles(audio_path, video_path)

        status_label.config(text="Playing video...")
        root.update_idletasks()
        play_video(video_path, srt_path)

        messagebox.showinfo("Done", f"Subtitles saved at: {srt_path}")

    except Exception as e:
        messagebox.showerror("Error", str(e))
        status_label.config(text="Error occurred!")

# --- GUI ---
root = tk.Tk()
root.title("YouTube Chinese → English Subtitles")
root.geometry("500x220")

tk.Label(root, text="Enter YouTube URL:").pack(pady=10)
entry = tk.Entry(root, width=55)
entry.pack()

tk.Button(root, text="Generate & Play", command=run).pack(pady=20)

status_label = tk.Label(root, text="Ready", fg="blue")
status_label.pack(pady=10)

root.mainloop()
