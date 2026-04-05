#!/bin/bash
#
# Flash & Configure Heltec WiFi LoRa 32 V3 with Meshtastic
#
# Automates the complete flash + configure workflow for a Heltec V3
# as a gate sensor LoRa node.
#
# The gate sensor Heltec receives UART from an Arduino Nano (9600 baud,
# GPIO47 RX) and broadcasts gate/door events over the LoRa mesh.
#
# Requires .env file with MESH_PSK (see .env.example).
#
# Usage:
#   ./scripts/flash-heltec-meshtastic.sh                    # defaults
#   ./scripts/flash-heltec-meshtastic.sh -p /dev/ttyUSB1    # specific port
#   ./scripts/flash-heltec-meshtastic.sh -r US              # US region
#   ./scripts/flash-heltec-meshtastic.sh -v v2.7.15.567b8ea # specific version
#   ./scripts/flash-heltec-meshtastic.sh --flash-only       # skip config
#   ./scripts/flash-heltec-meshtastic.sh --config-only      # skip flash, config only
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Flash addresses for Heltec V3 (BIGDB_8MB layout)
ADDR_FIRMWARE="0x00"
ADDR_BLEOTA="0x340000"
ADDR_LITTLEFS="0x670000"

# Load secrets from .env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    log_error ".env file not found at $ENV_FILE"
    echo ""
    echo "  Create it from the example:"
    echo "    cp .env.example .env"
    echo "    # Edit .env and set your MESH_PSK"
    echo ""
    exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

if [ -z "$MESH_PSK" ] || [ "$MESH_PSK" = "base64:REPLACE_WITH_YOUR_256BIT_PSK" ]; then
    log_error "MESH_PSK not set or still contains placeholder"
    echo "  Edit .env and set your 256-bit PSK"
    exit 1
fi

# Defaults
PORT=""
REGION="EU_868"
VERSION=""
FLASH_ONLY=false
CONFIG_ONLY=false
CONFIRM_CONFIG=false
TMPDIR=""

# Cleanup temp files on exit
cleanup() {
    if [ -n "$TMPDIR" ] && [ -d "$TMPDIR" ]; then
        rm -rf "$TMPDIR"
    fi
}
trap cleanup EXIT

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Flash and configure a Heltec WiFi LoRa 32 V3 with Meshtastic firmware
for use as a gate sensor LoRa node.

The gate sensor Heltec receives UART from an Arduino Nano at 9600 baud
on GPIO47 and broadcasts gate/door alerts over the LoRa mesh.

Requires .env file with MESH_PSK (see .env.example).

Options:
  -p PORT       Serial port (default: auto-detect CP210x)
  -r REGION     LoRa region (default: EU_868)
                Common values: EU_868, US, AS_923
  -v VERSION    Firmware version tag (default: latest stable release)
                Example: v2.7.15.567b8ea
  --flash-only     Flash firmware but skip Meshtastic serial configuration
  --config-only    Configure an already-flashed device (skip firmware flash)
  --confirm-config Verify settings and close serial port (no flash, no config)
  -h, --help       Show this help message

Uses stock Meshtastic firmware (no custom build required).

Examples:
  $(basename "$0")                           # Auto-detect, EU_868, latest
  $(basename "$0") -p /dev/ttyUSB1 -r US     # Specific port, US region
  $(basename "$0") -v v2.7.15.567b8ea        # Specific firmware version
  $(basename "$0") --flash-only              # Flash only, no config
  $(basename "$0") --config-only             # Configure already-flashed device
  $(basename "$0") --confirm-config          # Verify settings + close serial port
EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p)       PORT="$2"; shift 2 ;;
        -r)       REGION="$2"; shift 2 ;;
        -v)       VERSION="$2"; shift 2 ;;
        --flash-only) FLASH_ONLY=true; shift ;;
        --config-only) CONFIG_ONLY=true; shift ;;
        --confirm-config) CONFIRM_CONFIG=true; shift ;;
        -h|--help) usage ;;
        *)
            log_error "Unknown option: $1"
            echo "Use -h for help."
            exit 1
            ;;
    esac
done

# Mutual exclusion
if [ "$FLASH_ONLY" = true ] && [ "$CONFIG_ONLY" = true ]; then
    log_error "--flash-only and --config-only are mutually exclusive"
    exit 1
fi
if [ "$CONFIRM_CONFIG" = true ] && { [ "$FLASH_ONLY" = true ] || [ "$CONFIG_ONLY" = true ]; }; then
    log_error "--confirm-config cannot be combined with --flash-only or --config-only"
    exit 1
fi

# Banner
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "     Heltec V3 Meshtastic — Gate Sensor Node"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Region:        $REGION"
echo "  Serial baud:   9600 (Nano SoftwareSerial)"
echo "  Serial RXD:    GPIO47"
echo "  Flash only:    $FLASH_ONLY"
echo "  Config only:   $CONFIG_ONLY"
echo "  Confirm config: $CONFIRM_CONFIG"
echo ""

################################################################################
# Step 1: Check dependencies
################################################################################
log_step "Step 1: Checking Dependencies"

MISSING=()

if [ "$CONFIG_ONLY" = true ] || [ "$CONFIRM_CONFIG" = true ]; then
    if ! command -v meshtastic &>/dev/null; then
        MISSING+=("meshtastic (pip install meshtastic)")
    fi
else
    if ! command -v esptool.py &>/dev/null; then
        MISSING+=("esptool.py (pip install esptool)")
    fi

    if [ "$FLASH_ONLY" = false ] && ! command -v meshtastic &>/dev/null; then
        MISSING+=("meshtastic (pip install meshtastic)")
    fi
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    log_error "Missing required tools:"
    for dep in "${MISSING[@]}"; do
        echo "  - $dep"
    done
    exit 1
fi

log_info "All dependencies found"

################################################################################
# Step 2: Detect serial port
################################################################################
log_step "Step 2: Detecting Serial Port"

if [ -z "$PORT" ]; then
    # Auto-detect CP210x (Silicon Labs 10c4:ea60)
    if ! lsusb 2>/dev/null | grep -qi "10c4:ea60"; then
        log_error "No CP210x USB device found (vendor 10c4:ea60)"
        echo ""
        echo "  - Is the Heltec V3 plugged in with a data cable?"
        echo "  - Try: lsusb | grep -i silicon"
        echo "  - Specify port manually with: -p /dev/ttyUSB0"
        exit 1
    fi

    for dev in /dev/ttyUSB*; do
        if [ -e "$dev" ]; then
            PORT="$dev"
            break
        fi
    done

    if [ -z "$PORT" ]; then
        log_error "CP210x detected via lsusb but no /dev/ttyUSB* device found"
        echo "  Check: dmesg | grep -i cp210"
        exit 1
    fi

    log_info "Auto-detected port: $PORT"
else
    log_info "Using specified port: $PORT"
fi

################################################################################
# Step 3: Check port access
################################################################################
log_step "Step 3: Checking Port Access"

if [ ! -e "$PORT" ]; then
    log_error "Port $PORT does not exist"
    exit 1
fi

if [ ! -r "$PORT" ] || [ ! -w "$PORT" ]; then
    log_warn "Cannot access $PORT — attempting chmod 666"
    sudo chmod 666 "$PORT"
    if [ ! -r "$PORT" ] || [ ! -w "$PORT" ]; then
        log_error "Still cannot access $PORT after chmod"
        echo "  Try: sudo usermod -aG dialout \$USER (then re-login)"
        exit 1
    fi
    log_info "Port permissions fixed"
else
    log_info "Port $PORT is accessible"
fi

################################################################################
# Step 4–6: Firmware (skipped in --config-only mode)
################################################################################
if [ "$CONFIG_ONLY" = true ] || [ "$CONFIRM_CONFIG" = true ]; then
    log_info "Skipping firmware steps"
else

################################################################################
# Step 4: Verify chip
################################################################################
log_step "Step 4: Verifying ESP32-S3 Chip"

CHIP_OUTPUT=$(esptool.py --port "$PORT" chip_id 2>&1) || {
    log_error "esptool chip_id failed — is the device in boot mode?"
    echo ""
    echo "  Put the Heltec in boot mode:"
    echo "    1. Hold the BOOT button"
    echo "    2. Press and release the RST button"
    echo "    3. Release the BOOT button"
    echo "    4. Re-run this script"
    exit 1
}

if echo "$CHIP_OUTPUT" | grep -qi "ESP32-S3"; then
    log_info "Confirmed ESP32-S3 chip"
else
    log_warn "Chip identification did not confirm ESP32-S3"
    echo "  Output: $(echo "$CHIP_OUTPUT" | grep -i "chip" | head -1)"
    echo "  Continuing anyway..."
fi

################################################################################
# Step 5: Obtain firmware (stock Meshtastic release)
################################################################################
TMPDIR=$(mktemp -d)

log_step "Step 5: Downloading Firmware"

if [ -z "$VERSION" ]; then
    VERSION=$(gh release list --repo meshtastic/firmware --exclude-pre-releases --limit 1 --json tagName --jq '.[0].tagName')
fi
log_info "Version: $VERSION"

ASSET_VERSION="${VERSION#v}"
ASSET_NAME="firmware-esp32s3-${ASSET_VERSION}.zip"
ZIP_PATH="$TMPDIR/$ASSET_NAME"

gh release download "$VERSION" \
    --repo meshtastic/firmware \
    --pattern "$ASSET_NAME" \
    --dir "$TMPDIR" || {
    log_error "Failed to download $ASSET_NAME"
    exit 1
}

unzip -q "$ZIP_PATH" -d "$TMPDIR/fw"

FW_BIN=$(find "$TMPDIR/fw" -name "firmware-heltec-v3-*.factory.bin" | head -1)
BLEOTA_BIN=$(find "$TMPDIR/fw" -name "bleota-s3.bin" | head -1)
LITTLEFS_BIN=$(find "$TMPDIR/fw" -name "littlefs-heltec-v3-*.bin" | head -1)

if [ -z "$FW_BIN" ] || [ ! -f "$BLEOTA_BIN" ] || [ -z "$LITTLEFS_BIN" ]; then
    log_error "Could not find required firmware files in download"
    echo "  Looking for: firmware-heltec-v3-*.factory.bin, bleota-s3.bin, littlefs-heltec-v3-*.bin"
    exit 1
fi

log_info "Firmware:  $(basename "$FW_BIN")"
log_info "BLE OTA:   $(basename "$BLEOTA_BIN")"
log_info "LittleFS:  $(basename "$LITTLEFS_BIN")"

################################################################################
# Step 6: Flash firmware
################################################################################
log_step "Step 6: Flashing Firmware"

echo -e "${CYAN}[1/4]${NC} Erasing flash..."
esptool.py --port "$PORT" erase_flash
echo ""

echo -e "${CYAN}[2/4]${NC} Writing firmware at $ADDR_FIRMWARE..."
esptool.py --port "$PORT" write_flash "$ADDR_FIRMWARE" "$FW_BIN"
echo ""

echo -e "${CYAN}[3/4]${NC} Writing BLE OTA at $ADDR_BLEOTA..."
esptool.py --port "$PORT" write_flash "$ADDR_BLEOTA" "$BLEOTA_BIN"
echo ""

echo -e "${CYAN}[4/4]${NC} Writing LittleFS at $ADDR_LITTLEFS..."
esptool.py --port "$PORT" write_flash "$ADDR_LITTLEFS" "$LITTLEFS_BIN"
echo ""

log_info "Flash complete — device is rebooting"

fi  # end of CONFIG_ONLY skip

################################################################################
# Step 7: Wait for device to be ready
################################################################################

wait_for_device() {
    while true; do
        echo -en "${YELLOW}[WAIT]${NC} Press ENTER when the device OLED is active (or type 'abort'): "
        read -r response
        if [ "$response" = "abort" ]; then
            log_error "Aborted by operator"
            exit 1
        fi
        if meshtastic --port "$PORT" --info &>/dev/null 2>&1; then
            log_info "Device ready"
            return 0
        fi
        log_warn "Device not responding — wait for the OLED and try again"
    done
}

mesh_cmd() {
    local description="$1"
    shift
    log_info "$description"
    if ! meshtastic --port "$PORT" "$@" 2>&1; then
        log_warn "Command may have failed — device may be rebooting"
    fi
    wait_for_device
}

wait_for_device

################################################################################
# Step 8: Configure Meshtastic (unless --flash-only)
################################################################################
if [ "$FLASH_ONLY" = true ] && [ "$CONFIG_ONLY" = false ]; then
    log_info "Skipping Meshtastic configuration (--flash-only)"
elif [ "$CONFIRM_CONFIG" = true ]; then
    log_info "Skipping config commands (--confirm-config, verification only)"

    log_step "Verifying Configuration"

    echo -en "${YELLOW}[WAIT]${NC} Press ENTER to start config verification (or type 'abort'): "
    read -r response
    if [ "$response" = "abort" ]; then
        log_error "Aborted by operator"
        exit 1
    fi

    log_info "Reading back all settings for verification..."
    VERIFY_FAIL=0

    verify_get() {
        local key="$1"
        local expected="$2"
        local output
        output=$(meshtastic --port "$PORT" --get "$key" 2>&1) || {
            log_error "  FAIL  $key — could not read from device"
            return 1
        }
        local actual
        actual=$(echo "$output" | grep -i "$key" | sed 's/.*= *//')
        if [ -z "$actual" ]; then
            log_error "  FAIL  $key — no value in output"
            return 1
        fi
        if echo "$actual" | grep -qi "$expected"; then
            log_info "  OK    $key = $actual"
            return 0
        else
            log_error "  FAIL  $key = $actual (expected: $expected)"
            return 1
        fi
    }

    verify_get "lora.region" "EU_868\|3"                    || VERIFY_FAIL=1
    verify_get "position.gps_mode" "NOT_PRESENT\|2"         || VERIFY_FAIL=1
    verify_get "serial.enabled" "true\|True"                || VERIFY_FAIL=1
    verify_get "serial.rxd" "47"                            || VERIFY_FAIL=1
    verify_get "serial.baud" "BAUD_9600\|1"                 || VERIFY_FAIL=1
    verify_get "serial.mode" "TEXTMSG\|3"                   || VERIFY_FAIL=1
    verify_get "bluetooth.enabled" "false\|False"           || VERIFY_FAIL=1

    CH_OUTPUT=$(meshtastic --port "$PORT" --info 2>&1) || true
    if echo "$CH_OUTPUT" | grep -q "psk.*AQ=="; then
        log_error "  FAIL  Channel PSK is still default (AQ==)"
        VERIFY_FAIL=1
    elif echo "$CH_OUTPUT" | grep -q "psk"; then
        log_info "  OK    Channel PSK is set (non-default)"
    else
        log_warn "  WARN  Could not verify channel PSK"
    fi

    if [ "$VERIFY_FAIL" -ne 0 ]; then
        echo ""
        log_error "Configuration verification FAILED"
        echo ""
        echo "  Fix settings with: meshtastic --port $PORT --info"
        echo "  Then re-run with --confirm-config"
        echo ""
        exit 1
    fi

    log_info "All settings verified"
else
    log_step "Step 7: Configuring Meshtastic"

    mesh_cmd "Setting LoRa region to $REGION..." \
        --set lora.region "$REGION"

    mesh_cmd "Setting private channel PSK..." \
        --ch-set psk "$MESH_PSK" --ch-index 0

    mesh_cmd "Disabling internal GPS (gate sensor has no GPS)..." \
        --set position.gps_mode NOT_PRESENT

    mesh_cmd "Setting telemetry broadcast interval to 30 min..." \
        --set telemetry.device_update_interval 1800

    # Gate sensor serial config:
    #   rxd=47 (GPIO47, avoids CP2102 conflict on GPIO44)
    #   txd=0  (disabled — Nano does not receive from Heltec)
    #   baud=BAUD_9600 (matches Arduino Nano SoftwareSerial)
    mesh_cmd "Setting serial module for gate sensor (GPIO47 RX, 9600 baud)..." \
        --set serial.enabled true \
        --set serial.echo false \
        --set serial.rxd 47 \
        --set serial.txd 0 \
        --set serial.baud BAUD_9600 \
        --set serial.timeout 0 \
        --set serial.mode TEXTMSG

    mesh_cmd "Disabling Bluetooth..." \
        --set bluetooth.enabled false

    ############################################################################
    # Verification
    ############################################################################
    log_step "Step 7b: Verifying Configuration"

    echo -en "${YELLOW}[WAIT]${NC} Press ENTER to start config verification (or type 'abort'): "
    read -r response
    if [ "$response" = "abort" ]; then
        log_error "Aborted by operator"
        exit 1
    fi

    log_info "Reading back all settings for verification..."
    VERIFY_FAIL=0

    verify_get() {
        local key="$1"
        local expected="$2"
        local output
        output=$(meshtastic --port "$PORT" --get "$key" 2>&1) || {
            log_error "  FAIL  $key — could not read from device"
            return 1
        }
        local actual
        actual=$(echo "$output" | grep -i "$key" | sed 's/.*= *//')
        if [ -z "$actual" ]; then
            log_error "  FAIL  $key — no value in output"
            return 1
        fi
        if echo "$actual" | grep -qi "$expected"; then
            log_info "  OK    $key = $actual"
            return 0
        else
            log_error "  FAIL  $key = $actual (expected: $expected)"
            return 1
        fi
    }

    verify_get "lora.region" "EU_868\|3"                    || VERIFY_FAIL=1
    verify_get "position.gps_mode" "NOT_PRESENT\|2"         || VERIFY_FAIL=1
    verify_get "serial.enabled" "true\|True"                || VERIFY_FAIL=1
    verify_get "serial.rxd" "47"                            || VERIFY_FAIL=1
    verify_get "serial.baud" "BAUD_9600\|1"                 || VERIFY_FAIL=1
    verify_get "serial.mode" "TEXTMSG\|3"                   || VERIFY_FAIL=1
    verify_get "bluetooth.enabled" "false\|False"           || VERIFY_FAIL=1

    CH_OUTPUT=$(meshtastic --port "$PORT" --info 2>&1) || true
    if echo "$CH_OUTPUT" | grep -q "psk.*AQ=="; then
        log_error "  FAIL  Channel PSK is still default (AQ==)"
        VERIFY_FAIL=1
    elif echo "$CH_OUTPUT" | grep -q "psk"; then
        log_info "  OK    Channel PSK is set (non-default)"
    else
        log_warn "  WARN  Could not verify channel PSK"
    fi

    if [ "$VERIFY_FAIL" -ne 0 ]; then
        echo ""
        log_error "Configuration verification FAILED — fix the above issues and re-run"
        echo ""
        echo "  meshtastic --port $PORT --info"
        echo ""
        exit 1
    fi

    log_info "All settings verified"
    log_info "Configuration complete"
fi

################################################################################
# Step 9: Verify
################################################################################
log_step "Step 8: Verification"

if [ "$FLASH_ONLY" = false ]; then
    log_info "Querying device info..."
    INFO_OUTPUT=$(meshtastic --port "$PORT" --info 2>&1) || {
        log_warn "Could not query device info"
        INFO_OUTPUT=""
    }

    if [ -n "$INFO_OUTPUT" ]; then
        HW_MODEL=$(echo "$INFO_OUTPUT" | grep -i "hwModel" | head -1 || true)
        MAC_ADDR=$(echo "$INFO_OUTPUT" | grep -i "macaddr\|mac_address" | head -1 || true)
        FW_VER=$(echo "$INFO_OUTPUT" | grep -i "firmware_version" | head -1 || true)

        if [ -n "$HW_MODEL" ]; then log_info "$HW_MODEL"; fi
        if [ -n "$FW_VER" ]; then log_info "$FW_VER"; fi
        if [ -n "$MAC_ADDR" ]; then log_info "$MAC_ADDR"; fi

        if echo "$INFO_OUTPUT" | grep -qi "HELTEC_V3"; then
            log_info "Confirmed: Heltec V3 hardware model"
        fi
    fi
else
    log_info "Flash-only mode — skipping device verification"
    echo "  Run 'meshtastic --port $PORT --info' to verify manually."
fi

################################################################################
# Summary
################################################################################
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
if [ "$CONFIRM_CONFIG" = true ]; then
    echo -e "${GREEN}  Gate Sensor Heltec V3 — Config Verified${NC}"
elif [ "$CONFIG_ONLY" = true ]; then
    echo -e "${GREEN}  Gate Sensor Heltec V3 — Configuration Complete${NC}"
else
    echo -e "${GREEN}  Gate Sensor Heltec V3 — Flash Complete${NC}"
fi
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Port:         $PORT"
echo "  Firmware:     stock Meshtastic ${VERSION}"
echo "  Region:       $REGION"
echo "  Serial RXD:   GPIO47 (from Arduino Nano via voltage divider)"
echo "  Serial baud:  9600 (SoftwareSerial)"
echo "  Serial mode:  TEXTMSG"
echo "  Channel:      PSK configured (256-bit)"
echo "  Configured:   $([ "$FLASH_ONLY" = true ] && echo "no (flash-only)" || echo "yes")"
echo ""
if [ "$FLASH_ONLY" = true ]; then
    echo "  Run this script again without --flash-only to configure."
else
    echo "  The Heltec is ready for use as a gate sensor LoRa node."
    echo "  Install it on the gate sensor carrier PCB and connect the"
    echo "  Arduino Nano's D3 (TX) to the Heltec's GPIO47 via the"
    echo "  2.2k/3.3k voltage divider."
fi
echo ""
