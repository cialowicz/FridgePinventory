# Pi Inventory Management System

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
   ```

2. Install the project and its dependencies:
   ```bash
   # Install in development mode
   pip install -e .
   # Install test dependencies
   pip install -e ".[test]"
   ```

3. Connect the hardware components to the Raspberry Pi:
   - Connect the PIR sensor to GPIO pin 4
   - Connect the Inky wHAT display via SPI
   - Connect USB speaker and microphone

4. Create the sounds directory and add audio files:
   ```bash
   mkdir sounds
   # Add success.wav and error.wav for audio feedback
   ```

5. Run the application:
   ```bash
   python src/main.py
   ```

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
- Tests can be run using: `python -m pytest`
- New items can be added in `src/item_normalizer.py`
- Audio feedback sounds can be customized by replacing files in the `sounds` directory
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
