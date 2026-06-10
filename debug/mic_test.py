"""Microphone debug: signal-level survey and end-to-end recognition test.

Two modes:

  Survey (no args) — record ~3s from each real capture device (hardware
  devices, plus ALSA default/sysdefault) while you TALK CONTINUOUSLY, then
  report peak/RMS levels in the same int16 units speech_recognition uses
  for its energy threshold. Shows which device actually hears you and how
  loudly. Each recording is saved to /tmp/mic_<index>.wav for playback
  (aplay /tmp/mic_<index>.wav).

  Deep test (one arg: device index) — run the app's actual pipeline on that
  device: sr.Microphone + adjust_for_ambient_noise + listen + Sphinx,
  printing the energy threshold before/after calibration and timing each
  stage. Say "add chicken" when it prints LISTENING.

Stop the service first (it holds the microphone):

    sudo systemctl stop fridgepinventory.service
    ~/.epaper_venv/bin/python debug/mic_test.py          # survey
    ~/.epaper_venv/bin/python debug/mic_test.py 0        # deep test device 0

Interpretation: speech at normal volume should peak in the thousands.
If every device shows peak < ~200 while you talk, the capture gain is the
problem: run `alsamixer -c <card>`, press F4 (capture), raise the level,
then `sudo alsactl store`.
"""

import audioop
import sys
import time
import wave

import pyaudio
import speech_recognition as sr

RECORD_SECONDS = 3
CHUNK = 1024


def record_levels(pa, index, seconds=RECORD_SECONDS):
    """Record from one device; return (peak, rms, rate) and save a WAV."""
    info = pa.get_device_info_by_index(index)
    rate = int(info.get("defaultSampleRate", 44100))
    stream = pa.open(format=pyaudio.paInt16, channels=1, rate=rate,
                     input=True, input_device_index=index,
                     frames_per_buffer=CHUNK)
    frames = []
    peak = 0
    rms_total = 0
    chunks = max(1, int(rate / CHUNK * seconds))
    try:
        for _ in range(chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            peak = max(peak, audioop.max(data, 2))
            rms_total += audioop.rms(data, 2)
    finally:
        stream.stop_stream()
        stream.close()

    path = f"/tmp/mic_{index}.wav"
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(frames))
    return peak, rms_total // chunks, rate, path


def survey(pa):
    try:
        default_info = pa.get_default_input_device_info()
        default_index = default_info["index"]
        print(f"ALSA default input device: index {default_index} "
              f"({default_info['name']})")
    except OSError:
        default_index = None
        print("No default input device reported!")
    print(f"TALK CONTINUOUSLY for the next ~{RECORD_SECONDS}s per device.\n")

    candidates = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) <= 0:
            continue
        name = info.get("name", "")
        # Real hardware shows up as "... (hw:X,Y)"; also test the ALSA
        # routing devices the app might end up on. Skip rate-converter and
        # effect plugins (lavrate, speex, upmix, ...).
        if "hw:" in name or name in ("default", "sysdefault") \
                or i == default_index:
            candidates.append((i, name))

    results = []
    for i, name in candidates:
        print(f"Recording from device {i}: {name} ...")
        try:
            peak, rms, rate, path = record_levels(pa, i)
        except Exception as e:
            print(f"  ERROR: {e}\n")
            continue
        verdict = ("strong signal" if peak > 2000
                   else "weak — check capture gain" if peak > 200
                   else "near silence")
        print(f"  peak={peak} rms={rms} rate={rate} -> {verdict}")
        print(f"  saved {path}\n")
        results.append((peak, i, name))

    if results:
        results.sort(reverse=True)
        peak, i, name = results[0]
        if peak > 2000:
            print(f"Best device: index {i} ({name}). If this is not the "
                  f"app's device, set audio.voice_recognition.device_index: "
                  f"{i} in config.yaml.")
            print(f"Next: deep test it ->  mic_test.py {i}")
        else:
            print("No device heard you clearly. Raise the capture volume:")
            print("  alsamixer -c <card>  (F4 for capture view), then")
            print("  sudo alsactl store")


def deep_test(index):
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 4000  # same starting point as the app
    print(f"energy_threshold before calibration: "
          f"{recognizer.energy_threshold:.0f}")

    mic = sr.Microphone(device_index=index)
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    print(f"energy_threshold after calibration:  "
          f"{recognizer.energy_threshold:.0f} "
          f"(dynamic={recognizer.dynamic_energy_threshold})")

    print('\nLISTENING — say "add chicken" now...')
    t = time.time()
    try:
        with mic as source:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
    except sr.WaitTimeoutError:
        print(f"WaitTimeoutError after {time.time() - t:.1f}s — speech never "
              f"crossed the energy threshold.")
        print("Either this is the wrong device (run the survey) or the "
              "threshold is far above your signal level (compare survey "
              "peak/rms numbers to the threshold above).")
        return
    print(f"Captured {len(audio.frame_data)} bytes in {time.time() - t:.1f}s")

    with open("/tmp/mic_capture.wav", "wb") as f:
        f.write(audio.get_wav_data())
    print("Saved capture to /tmp/mic_capture.wav (aplay it to verify)")

    t = time.time()
    try:
        text = recognizer.recognize_sphinx(audio)
        print(f'Sphinx heard: "{text}" ({time.time() - t:.1f}s)')
    except sr.UnknownValueError:
        print(f"Sphinx could not understand the audio "
              f"({time.time() - t:.1f}s) — play /tmp/mic_capture.wav: if "
              f"your voice is clear there, it's a recognition problem, not "
              f"a capture problem.")
    except Exception as e:
        print(f"Sphinx failed: {e}")


def main() -> None:
    if len(sys.argv) > 1:
        deep_test(int(sys.argv[1]))
    else:
        pa = pyaudio.PyAudio()
        try:
            survey(pa)
        finally:
            pa.terminate()


if __name__ == "__main__":
    main()
