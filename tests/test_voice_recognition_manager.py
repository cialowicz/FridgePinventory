import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch

from pi_inventory_system.voice_recognition_manager import VoiceRecognitionManager, sr


def _fake_pocketsphinx(hypstr):
    """Install a fake pocketsphinx 5 module; returns (module, Decoder cls, decoder)."""
    decoder = MagicMock(name="ps5_decoder")
    decoder.hyp.return_value = (
        SimpleNamespace(hypstr=hypstr) if hypstr is not None else None
    )
    decoder_cls = MagicMock(name="Decoder", return_value=decoder)
    module = ModuleType("pocketsphinx")
    module.Decoder = decoder_cls
    return module, decoder_cls, decoder


def _config(cooldown):
    cfg = MagicMock()
    cfg.get_audio_config.return_value = {
        'voice_recognition': {
            'initialization_retry_cooldown': cooldown,
            'timeout': 5,
            'phrase_time_limit': 10,
            'engine': 'sphinx',
        }
    }
    return cfg


def _microphone():
    mic = MagicMock()
    mic.__enter__.return_value = MagicMock()
    mic.__exit__.return_value = False
    return mic


def _fake_pyaudio(devices):
    """Fake PyAudio instance exposing a device list for enumeration."""
    pa = MagicMock()
    pa.get_device_count.return_value = len(devices)
    pa.get_device_info_by_index.side_effect = lambda i: devices[i]
    return pa


# Device list mirroring the appliance Pi after the asound.conf change:
# HDMI outputs first, then the USB mic and USB speaker.
_PI_DEVICES = [
    {'name': 'vc4hdmi0', 'maxInputChannels': 0},
    {'name': 'UACDemoV1.0: USB Audio (hw:3,0)', 'maxInputChannels': 0},
    {'name': 'USB PnP Sound Device: Audio (hw:2,0)', 'maxInputChannels': 1},
]


def test_device_name_match_wins_over_stale_index():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES)

    index = manager._resolve_input_device_index(
        {'device_name': 'usb pnp', 'device_index': 1})

    assert index == 2


def test_stale_index_falls_back_to_input_capable_device():
    # Configured index points at an output-only device (indices shifted)
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES)

    assert manager._resolve_input_device_index({'device_index': 1}) == 2


def test_valid_configured_index_is_kept():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES + [
        {'name': 'Built-in Microphone', 'maxInputChannels': 2},
    ])

    assert manager._resolve_input_device_index({'device_index': 3}) == 3


def test_out_of_range_index_falls_back():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES)

    assert manager._resolve_input_device_index({'device_index': 7}) == 2


def test_unmatched_name_falls_back_to_usb_input():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio([
        {'name': 'Built-in Microphone', 'maxInputChannels': 2},
        {'name': 'USB PnP Sound Device: Audio (hw:2,0)', 'maxInputChannels': 1},
    ])

    assert manager._resolve_input_device_index({'device_name': 'blue yeti'}) == 1


def test_no_pyaudio_uses_configured_index_verbatim():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = None

    assert manager._resolve_input_device_index({'device_index': 1}) == 1


def test_nothing_configured_uses_system_default():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES)

    assert manager._resolve_input_device_index({}) is None


def test_cleanup_default_does_not_terminate_pyaudio():
    # Pa_Terminate while another (orphaned) voice thread is blocked in an
    # ALSA capture corrupts the heap — observed SIGABRT on the Pi. Retired
    # managers must drop the reference without terminating.
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    pa = MagicMock()
    manager._pyaudio_instance = pa

    manager.cleanup()

    pa.terminate.assert_not_called()
    assert manager._pyaudio_instance is None


def test_cleanup_terminates_pyaudio_when_requested():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    pa = MagicMock()
    manager._pyaudio_instance = pa

    manager.cleanup(terminate_pyaudio=True)

    pa.terminate.assert_called_once()
    assert manager._pyaudio_instance is None


def test_microphone_uses_resolved_index():
    cfg = MagicMock()
    cfg.get_audio_config.return_value = {
        'voice_recognition': {'device_name': 'USB PnP', 'device_index': 1},
    }
    mic = _microphone()

    with patch('pi_inventory_system.voice_recognition_manager.sr.Microphone',
               return_value=mic) as microphone_cls:
        manager = VoiceRecognitionManager(config_manager=cfg)
        manager._recognizer = MagicMock()
        manager._pyaudio_instance = _fake_pyaudio(_PI_DEVICES)

        assert manager._initialize_microphone() is True

    microphone_cls.assert_called_once_with(device_index=2)


def test_initialization_retries_after_cooldown():
    cfg = _config(cooldown=0)
    recognizer = MagicMock()
    mic = _microphone()

    with patch('pi_inventory_system.voice_recognition_manager.sr.Recognizer',
               return_value=recognizer), \
         patch('pi_inventory_system.voice_recognition_manager.sr.Microphone',
               side_effect=[OSError("missing"), OSError("missing"), OSError("missing"), mic]):
        manager = VoiceRecognitionManager(config_manager=cfg)

        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager._initialization_failed is True

        assert manager.initialize() is True
        assert manager._initialization_failed is False
        assert manager._retry_count == 0


def test_initialization_failure_respects_retry_cooldown():
    cfg = _config(cooldown=60)

    with patch('pi_inventory_system.voice_recognition_manager.sr.Microphone',
               side_effect=OSError("missing")) as microphone:
        manager = VoiceRecognitionManager(config_manager=cfg)

        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager.initialize() is False
        assert manager._initialization_failed is True

        assert manager.initialize() is False
        assert microphone.call_count == 3


def test_recognition_falls_back_from_sphinx_to_google():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.side_effect = sr.UnknownValueError()
    manager._recognizer.recognize_google.return_value = "Add One Salmon"

    result = manager._recognize_with_fallback(
        object(),
        {'engine': 'sphinx', 'enable_google_fallback': True},
    )

    assert result == "add one salmon"


def test_recognition_returns_none_when_all_engines_fail():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.side_effect = sr.UnknownValueError()
    manager._recognizer.recognize_google.side_effect = sr.RequestError("offline")

    result = manager._recognize_with_fallback(
        object(),
        {'engine': 'google', 'enable_sphinx_fallback': True},
    )

    assert result is None


def test_sphinx_uses_pocketsphinx5_grammar_decoder(monkeypatch):
    # speech_recognition's grammar= plumbing targets the pre-5.0 pocketsphinx
    # API and raises TypeError on modern installs; the manager must drive the
    # pocketsphinx 5 Decoder directly instead.
    module, decoder_cls, decoder = _fake_pocketsphinx("add chicken")
    monkeypatch.setitem(sys.modules, 'pocketsphinx', module)

    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    audio = MagicMock()
    audio.get_raw_data.return_value = b'\x00\x01'

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf'):
        result = manager._recognize_with_fallback(audio, {'engine': 'sphinx'})

    assert result == "add chicken"
    decoder_cls.assert_called_once_with(
        jsgf='/tmp/fridge_commands.jsgf', lm=None, samprate=16000)
    audio.get_raw_data.assert_called_once_with(convert_rate=16000,
                                               convert_width=2)
    decoder.start_utt.assert_called_once()
    decoder.process_raw.assert_called_once_with(b'\x00\x01', full_utt=True)
    decoder.end_utt.assert_called_once()
    manager._recognizer.recognize_sphinx.assert_not_called()


def test_sphinx_grammar_decoder_is_cached_across_commands(monkeypatch):
    module, decoder_cls, _ = _fake_pocketsphinx("add chicken")
    monkeypatch.setitem(sys.modules, 'pocketsphinx', module)

    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    audio = MagicMock()
    audio.get_raw_data.return_value = b'\x00'

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf'):
        manager._recognize_with_fallback(audio, {'engine': 'sphinx'})
        manager._recognize_with_fallback(audio, {'engine': 'sphinx'})

    decoder_cls.assert_called_once()


def test_sphinx_grammar_empty_hypothesis_is_unknown_value(monkeypatch):
    module, _, _ = _fake_pocketsphinx(None)
    monkeypatch.setitem(sys.modules, 'pocketsphinx', module)

    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    audio = MagicMock()
    audio.get_raw_data.return_value = b'\x00'

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf'):
        result = manager._recognize_with_fallback(audio, {'engine': 'sphinx'})

    # No grammar match -> UnknownValueError -> all engines exhausted -> None
    assert result is None
    manager._recognizer.recognize_sphinx.assert_not_called()


def test_sphinx_falls_back_to_open_model_when_decoder_unavailable(monkeypatch):
    module = ModuleType("pocketsphinx")
    module.Decoder = MagicMock(side_effect=TypeError(
        "__init__() takes exactly 4 positional arguments (3 given)"))
    monkeypatch.setitem(sys.modules, 'pocketsphinx', module)

    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.return_value = "add chicken"
    audio = MagicMock()
    audio.get_raw_data.return_value = b'\x00'

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf'):
        result = manager._recognize_with_fallback(audio, {'engine': 'sphinx'})
        # Second command: the failure latched, no new Decoder attempt
        manager._recognize_with_fallback(audio, {'engine': 'sphinx'})

    assert result == "add chicken"
    # Fallback uses the plain open-model decode, never grammar kwargs
    manager._recognizer.recognize_sphinx.assert_called_with(audio)
    module.Decoder.assert_called_once()


def test_sphinx_grammar_disabled_via_config():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.return_value = "add chicken"
    audio = object()

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf') as grammar_path:
        result = manager._recognize_with_fallback(
            audio, {'engine': 'sphinx', 'sphinx_grammar': False})

    assert result == "add chicken"
    grammar_path.assert_not_called()
    manager._recognizer.recognize_sphinx.assert_called_once_with(audio)


def test_sphinx_runs_without_grammar_when_unavailable():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.return_value = "add chicken"
    audio = object()

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value=None):
        result = manager._recognize_with_fallback(audio, {'engine': 'sphinx'})

    assert result == "add chicken"
    manager._recognizer.recognize_sphinx.assert_called_once_with(audio)


def test_google_engine_never_receives_grammar_kwarg():
    manager = VoiceRecognitionManager(config_manager=_config(cooldown=0))
    manager._recognizer = MagicMock()
    manager._recognizer.recognize_sphinx.side_effect = sr.UnknownValueError()
    manager._recognizer.recognize_google.return_value = "add beef"
    audio = object()

    with patch('pi_inventory_system.voice_recognition_manager.get_grammar_path',
               return_value='/tmp/fridge_commands.jsgf'):
        result = manager._recognize_with_fallback(
            audio, {'engine': 'sphinx', 'enable_google_fallback': True})

    assert result == "add beef"
    manager._recognizer.recognize_google.assert_called_once_with(audio)
