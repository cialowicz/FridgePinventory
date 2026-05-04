"""Smoke tests for the diagnostic CLI."""

from unittest.mock import MagicMock, patch

from pi_inventory_system import diagnostic_cli


def _cfg():
    cfg = MagicMock()
    cfg.get_platform_config.return_value = {}
    cfg.get_audio_config.return_value = {
        'feedback_sounds': {'success_sound': 'sounds/success.wav'},
        'voice_recognition': {'engine': 'sphinx'},
        'text_to_speech': {'rate': 150, 'volume': 0.9, 'voice_id': None},
    }
    cfg.get_hardware_config.return_value = {'motion_sensor': {'enabled': True, 'pin': 4}}
    cfg.get_nlp_config.return_value = {'enable_spacy': False}
    return cfg


def test_run_diagnostic_returns_nonzero_when_no_hardware(capsys):
    """On a non-Pi dev box every hardware check fails; exit code is 1."""
    cfg = _cfg()
    with patch('pi_inventory_system.diagnostic_cli.is_raspberry_pi', return_value=False), \
         patch('pi_inventory_system.diagnostic_cli.is_raspberry_pi_5', return_value=False), \
         patch('pi_inventory_system.diagnostic_cli.initialize_display', return_value=None), \
         patch('pi_inventory_system.diagnostic_cli.is_display_supported', return_value=False), \
         patch('pi_inventory_system.diagnostic_cli.MotionSensorManager') as motion_cls, \
         patch('pi_inventory_system.diagnostic_cli.AudioFeedbackManager') as audio_cls, \
         patch('pi_inventory_system.diagnostic_cli.VoiceRecognitionManager') as voice_cls:
        motion = MagicMock()
        motion.is_supported.return_value = False
        motion_cls.return_value = motion
        audio = MagicMock()
        audio.play_sound.return_value = False
        audio_cls.return_value = audio
        voice = MagicMock()
        voice.initialize.return_value = False
        voice_cls.return_value = voice

        rc = diagnostic_cli.run_diagnostic(cfg)
    assert rc == 1
    captured = capsys.readouterr()
    assert "Platform" in captured.out
    assert "Overall: FAIL" in captured.out


def test_run_diagnostic_returns_zero_on_full_pass(capsys):
    cfg = _cfg()
    with patch('pi_inventory_system.diagnostic_cli.is_raspberry_pi', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli.is_raspberry_pi_5', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli._check_spi', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli._check_i2c', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli._check_aplay', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli._check_arecord', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli.is_display_supported', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli.initialize_display') as init_disp, \
         patch('pi_inventory_system.diagnostic_cli.display_text', return_value=True), \
         patch('pi_inventory_system.diagnostic_cli.MotionSensorManager') as motion_cls, \
         patch('pi_inventory_system.diagnostic_cli.AudioFeedbackManager') as audio_cls, \
         patch('pi_inventory_system.diagnostic_cli.VoiceRecognitionManager') as voice_cls:
        display = MagicMock(WIDTH=800, HEIGHT=480); init_disp.return_value = display
        motion = MagicMock(); motion.is_supported.return_value = True
        motion.detect_motion.return_value = False; motion.is_healthy.return_value = True
        motion_cls.return_value = motion
        audio = MagicMock(); audio.play_sound.return_value = True; audio_cls.return_value = audio
        voice = MagicMock(); voice.initialize.return_value = True; voice_cls.return_value = voice

        rc = diagnostic_cli.run_diagnostic(cfg)
    assert rc == 0
    assert "Overall: OK" in capsys.readouterr().out
