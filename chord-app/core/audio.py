import subprocess
import os

def convert_to_wav(input_file):
    if input_file.endswith(".wav"):
        return input_file

    output_file = input_file.replace(".mp3", ".wav")

    subprocess.call(["ffmpeg", "-y", "-i", input_file, output_file])

    return output_file