# Fridge Pi Inventory Management System

An inventory management system for a chest freezer, built using a Raspberry Pi 5. It features a voice interface for managing inventory items with smart item name recognition and visual feedback via an eInk display.

## Components
- Raspberry Pi 5
- HC-SR501 PIR motion sensor (for automatic activation)
- Waveshare 3.97" e-Paper HAT+ (800x480, 4-grayscale, for persistent inventory display)
- USB speaker (for audio feedback)
- USB microphone (for voice commands)

## Features
- Voice command recognition with Google Speech-to-Text
- Smart item name recognition (handles variations like "chicken wings" vs "wings")
- Visual feedback via high-resolution e-Paper display (800x480) with optimized grid layout
- Fast display refresh (3.5s) with 4-level grayscale support
- Audio feedback for command success/failure
- Motion detection to trigger listening mode
- SQLite database for persistent storage
- Command history with undo support

## Setup Instructions

### For Raspberry Pi (Recommended)

The easiest and recommended way to set up the FridgePinventory system on a Raspberry Pi is by using the provided deployment script. This script automates the installation of all system packages, Python dependencies within a dedicated virtual environment (`~/.epaper_venv`), and configures the application to run as a systemd service.

1.  Ensure you have `git` installed on your Raspberry Pi:
    ```bash
    sudo apt update && sudo apt install -y git
    ```
2.  Clone the repository (replace `<your-repository-url>` with the actual URL if needed):
    ```bash
    git clone <your-repository-url> FridgePinventory
    cd FridgePinventory
    ```
3.  Make the deployment script executable:
    ```bash
    chmod +x deploy.sh
    ```
4.  Run the deployment script **as your regular user (e.g., `admin` or `pi`), not with `sudo`**:
    ```bash
    ./deploy.sh
    ```
    The script uses `sudo` internally for commands that require root privileges.
5.  Follow any prompts from the script. A reboot is typically recommended after the script finishes to ensure all changes (like group memberships for hardware access) take effect. After rebooting, the `fridgepinventory` service should start automatically.

The `deploy.sh` script handles the installation of numerous dependencies, including but not limited to: `python3-dev`, `portaudio19-dev`, `espeak-ng`, `swig` (for PocketSphinx), `libpulse-dev`, `raspi-gpio`, `python3-pil`, `python3-spidev`, and Python libraries such as the Waveshare e-Paper library, `SpeechRecognition`, `pocketsphinx`, `spacy`, `RPi.GPIO`, `spidev`, `Pillow`, etc., into the `~/.epaper_venv` virtual environment.

### For macOS / Other Development Environments (Manual Setup)

These instructions are for setting up a development environment on macOS or other non-Raspberry Pi systems. The application will run in a simulated mode without actual hardware interaction.

1.  **Install System Dependencies:**
    *   **macOS:**
        ```bash
        brew install portaudio
        ```
        *(Note: If you intend to install and use `pocketsphinx` locally for offline speech recognition, you might also need `swig` and `flac`: `brew install swig flac`. Currently, `pocketsphinx` is primarily configured for the Raspberry Pi via `deploy.sh`.)*
    *   **Debian/Ubuntu (Manual for Pi or other Linux):**
        If you are manually setting up on a Raspberry Pi (i.e., not using `deploy.sh`) or another Debian-based system, you'll need a comprehensive list of packages. Refer to the contents of `deploy.sh` for the most up-to-date list. Key packages include:
        ```bash
        sudo apt-get update
        sudo apt-get install -y python3-dev python3-venv python3-pip portaudio19-dev libasound2-dev espeak-ng swig libpulse-dev flac libjack-jackd2-dev git libopenjp2-7 libtiff6 fonts-dejavu raspi-gpio python3-pil python3-pil.imagetk python3-spidev
        ```

2.  **Create and Activate Virtual Environment:**
    It's highly recommended to use a virtual environment for managing project dependencies. For manual setups, you can create one in the project directory:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install Project Dependencies:**
    The project's core Python dependencies are listed in `pyproject.toml`.
    ```bash
    # Install in development mode (includes runtime dependencies)
    pip install -e .
    # Install test dependencies (optional)
    pip install -e ".[test]"
    ```
    *(Note: `pocketsphinx` is not listed in `pyproject.toml`'s default dependencies. For the Raspberry Pi, it's installed by `deploy.sh`. If you need offline speech recognition in your manual development environment, ensure its system dependencies (like `swig`, `flac`) are present and then install it: `pip install pocketsphinx`.)*

4. Connect the hardware components to the Raspberry Pi:
   - Connect the PIR sensor to GPIO pin 4
   - Connect the Waveshare 3.97" e-Paper HAT+ via SPI (make sure SPI is enabled in raspi-config)
   - Connect USB speaker and microphone

## Running the Application

### On Raspberry Pi (with hardware)
```bash
# Make sure you're in the virtual environment
source .venv/bin/activate

# Run the application
python -m src.pi_inventory_system.main
```

### On Development Machine (simulation mode)
```bash
# Make sure you're in the virtual environment
source .venv/bin/activate

# Run the application
python -m src.pi_inventory_system.main
```

The application will:
1. Initialize the database and run any pending migrations
2. Start the display manager
3. Begin listening for motion detection
4. When motion is detected, it will:
   - Listen for voice commands
   - Process the commands
   - Update the inventory
   - Provide audio and visual feedback

To exit the application, press Ctrl+C.

## Voice Commands
- "Add X" - Add one of item X
- "Add N of X" - Add N quantity of item X
- "Remove X" - Remove one of item X
- "Remove N of X" - Remove N quantity of item X
- "Set X to N" - Set quantity of item X to N
- "Undo" - Undo the last change

## Supported Items
The system recognizes various forms of these items:
- Ground beef (beef, ground meat)
- Chicken breast (breast, chicken breasts)
- Chicken tenders (tenders, chicken strips)
- Chicken nuggets
- White fish (includes tilapia)
- Salmon
- Ground turkey (turkey meat)
- Ice cream (various flavors)
- Beef short rib (ribs)
- Steak (various cuts)

## Development
### Running Tests
The project uses pytest for testing. To run the tests:

```bash
# Run all tests
python -m pytest -v

# Run tests with coverage report
python -m pytest --cov=pi_inventory_system

# Run tests with coverage report and HTML output
python -m pytest --cov=pi_inventory_system --cov-report=html
```

The test suite includes:
- Unit tests for all major components
- Integration tests for database operations
- Hardware simulation tests for display and motion sensor
- Voice recognition tests with mocked audio input

Some tests are marked with `@pytest.mark.skip` if they require specific hardware or are known to be flaky. These can be run with:
```bash
python -m pytest -m "not skip"
```

### Adding New Tests
- Tests are located in the `tests` directory
- Each module has a corresponding test file (e.g., `test_inventory_controller.py`)
- Common test fixtures are defined in `conftest.py`
- Use pytest fixtures for shared test setup
- Mock hardware dependencies using `unittest.mock`

### Adding New Items
- New items can be added in `src/pi_inventory_system/item_normalizer.py`

## Audio Feedback
- Audio feedback sounds can be customized by replacing files in the `sounds` directory

## Database Migrations
- Database migrations are stored in the `migrations` directory
  - Each migration is a SQL file named with a number prefix (e.g., `000_migrations_tracking.sql`)
  - Migrations run automatically on startup in numerical order
  - The system tracks which migrations have been run to prevent duplicates

## Fallback Behavior
- If text-to-speech is unavailable, falls back to console output
- If audio playback is unavailable, falls back to console output
- If running on non-Raspberry Pi hardware, simulates hardware interactions for testing

## License
MIT License - Feel free to use and modify as needed.
