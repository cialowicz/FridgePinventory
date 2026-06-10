"""Shared product limits and mode names."""

MAX_COMMAND_LEN = 500
# Also enforced as a literal 10000 in the DB triggers
# (migrations/004_inventory_quantity_constraints.sql); changing this constant
# requires a new migration updating those triggers.
MAX_QUANTITY = 10_000

ACTIVATION_AUTO = "auto"
ACTIVATION_MOTION = "motion"
ACTIVATION_SIMULATION = "simulation"
ACTIVATION_ALWAYS_LISTEN = "always_listen"
ACTIVATION_MANUAL = "manual"

VALID_ACTIVATION_MODES = {
    ACTIVATION_AUTO,
    ACTIVATION_MOTION,
    ACTIVATION_SIMULATION,
    ACTIVATION_ALWAYS_LISTEN,
    ACTIVATION_MANUAL,
}
