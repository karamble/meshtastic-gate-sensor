# Gate Sensor — Meshtastic LoRa Bridge
# KiCad 10 Docker + PlatformIO targets

KICAD_IMAGE := kicad/kicad:10.0
KICAD_RUN   := docker run --rm -v $(CURDIR):/work $(KICAD_IMAGE) kicad-cli
PCB_FILE    := /work/pcb/gate_sensor_v2.kicad_pcb
OUTPUT_DIR  := /work/pcb/output

.PHONY: help
help:
	@echo "Gate Sensor Carrier PCB v2.2 — Build Targets"
	@echo ""
	@echo "  PCB (KiCad via Docker):"
	@echo "    make drc           Run design rule check"
	@echo "    make gerbers       Export Gerber files"
	@echo "    make drill         Export drill files"
	@echo "    make fab           Export Gerbers + drill (JLCPCB ready)"
	@echo "    make svg           Export board SVG"
	@echo "    make pdf           Export board PDF"
	@echo "    make pcb-stats     Board statistics"
	@echo "    make pcb-upgrade   Upgrade PCB to KiCad 10 format"
	@echo "    make kicad-version Show KiCad Docker version"
	@echo ""
	@echo "  Firmware (PlatformIO):"
	@echo "    make build         Compile firmware"
	@echo "    make upload        Flash to Arduino Nano"
	@echo "    make monitor       Serial monitor (115200 baud)"
	@echo "    make clean         Clean build artifacts"

# --- KiCad targets ---

.PHONY: kicad-version drc gerbers drill svg pdf pcb-stats pcb-upgrade

kicad-version:
	$(KICAD_RUN) version

drc:
	@mkdir -p pcb/output
	$(KICAD_RUN) pcb drc --severity-all -o $(OUTPUT_DIR)/drc_report.json $(PCB_FILE)

gerbers:
	@mkdir -p pcb/output
	$(KICAD_RUN) pcb export gerbers -o $(OUTPUT_DIR)/ $(PCB_FILE)

drill:
	@mkdir -p pcb/output
	$(KICAD_RUN) pcb export drill -o $(OUTPUT_DIR)/ $(PCB_FILE)

svg:
	@mkdir -p pcb/output
	$(KICAD_RUN) pcb export svg --layers F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,Edge.Cuts -o $(OUTPUT_DIR)/board.svg $(PCB_FILE)

pdf:
	@mkdir -p pcb/output
	$(KICAD_RUN) pcb export pdf -o $(OUTPUT_DIR)/board.pdf $(PCB_FILE)

pcb-stats:
	$(KICAD_RUN) pcb export stats $(PCB_FILE)

pcb-upgrade:
	$(KICAD_RUN) pcb upgrade $(PCB_FILE)

# Export everything for JLCPCB fabrication
fab: gerbers drill
	@echo "Fabrication files ready in pcb/output/"

# --- PlatformIO targets ---

.PHONY: build upload monitor clean

build:
	cd firmware && pio run

upload:
	cd firmware && pio run -t upload

monitor:
	cd firmware && pio device monitor -b 115200

clean:
	cd firmware && pio run -t clean
