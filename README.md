# Fridge Pi Inventory Management System

An inventory management system for a chest freezer, built using a Raspberry Pi 5. It features a voice interface for managing inventory items with smart item name recognition and visual feedback via an eInk display.

## Components
- Raspberry Pi 5
- HC-SR501 PIR motion sensor (for automatic activation)
- Inky wHAT 7" eInk Display (for persistent inventory display)
- USB speaker (for audio feedback)
- USB microphone (for voice commands)

## Features
- Voice command recognition with Google Speech-to-Text
- Smart item name recognition (handles variations like "chicken wings" vs "wings")
- Visual feedback via eInk display with a grid layout
- Audio feedback for command success/failure
- Motion detection to trigger listening mode
- SQLite database for persistent storage
- Command history with undo support

## Setup Instructions

1. Install system dependencies:
   ```bash
   # For Raspberry Pi OS / Debian / Ubuntu
   sudo apt-get update
   sudo apt-get install -y portaudio19-dev python3-dev

   # For macOS
   brew install portaudio
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the project and its dependencies:
   ```bash
   # Install in development mode
   pip install -e .
   # Install test dependencies
   pip install -e ".[test]"
   ```

4. Connect the hardware components to the Raspberry Pi:
   - Connect the PIR sensor to GPIO pin 4
   - Connect the Inky wHAT display via SPI
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
python -m pytest

# Run tests with verbose output
python -m pytest -v

# Run tests in a specific file
python -m pytest tests/test_inventory_controller.py

# Run tests matching a specific pattern
python -m pytest -k "test_add"

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
