# Main entry point for the application
from .inventory_controller import InventoryController


def main():
    """Main function to run the inventory system."""
    controller = InventoryController()
    controller.run_loop()


if __name__ == "__main__":
    main()
