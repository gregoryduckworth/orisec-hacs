"""Constants for the Orisec local protocol."""

DOMAIN = "orisec"
DEFAULT_PORT = 20202
DEFAULT_TIMEOUT = 2.0

CMD_LOGIN = 0x0001
CMD_SESSION_INFO = 0x0002
CMD_PANEL_STATUS = 0x0003
CMD_KEEPALIVE = 0x0006
CMD_INFO_REQUEST = 0x0014
CMD_INFO_RESPONSE = 0x0063
CMD_SERIAL_NUMBER = 0x0262
CMD_MAX_ZONES = 0x045A
CMD_ZONE_NAMES = 0x0460
CMD_AREA_NAMES = 0x083E
CMD_AREA_COUNT = 0x0842
CMD_ZONE_COUNT = 0x2462
CMD_ZONE_STATUS = 0x2850
CMD_MOTION_EVENTS = 0x277E

KEEPALIVE_PAYLOAD = b"\x01\x00\x02\x04"

# Network scan defaults. The scan sends one datagram per address and then waits
# once, so the timeout is how long the whole scan takes, not how long one
# address gets. A /22 is the largest network worth sweeping in front of a form.
DISCOVERY_TIMEOUT = 2.0
MAX_DISCOVERY_NETWORK_SIZE = 1024

# Home Assistant integration defaults.
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

MANUFACTURER = "Orisec"
