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
	@echo "    make assembly      Generate assembly PCB with 3D models"
	@echo "    make assembly-step Export 3D STEP file (requires AppImage)"
	@echo "    make kicad-version Show KiCad Docker version"
	@echo ""
	@echo "  Firmware (PlatformIO):"
	@echo "    make build         Compile firmware"
	@echo "    make upload        Flash to Arduino Nano"
	@echo "    make monitor       Serial monitor (115200 baud)"
	@echo "    make clean         Clean build artifacts"

# --- KiCad targets ---

.PHONY: kicad-version drc gerbers drill svg pdf pcb-stats pcb-upgrade assembly assembly-step

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

# Assembly PCB with 3D models
# 3D models extracted from KiCad AppImage to /tmp/kicad-3dmodels
APPIMAGE     := $(HOME)/Downloads/kicad-10.0.0-x86_64.AppImage
ASSEMBLY_PCB := pcb/gate_sensor_v2_assembly.kicad_pcb
MODELS_DIR   := /tmp/kicad-3dmodels

assembly:
	python3 pcb/generate_assembly.py

# Extract 3D models from AppImage (only needed once)
extract-3dmodels:
	@echo "Extracting 3D models from AppImage..."
	@$(APPIMAGE) --appimage-mount & \
	MOUNT_PID=$$!; sleep 2; \
	MOUNT_DIR=$$(find /tmp -maxdepth 1 -name '.mount_*' -type d | head -1); \
	mkdir -p $(MODELS_DIR); \
	for lib in Connector_PinSocket_2.54mm Connector_PinHeader_2.54mm Connector_JST Resistor_THT Capacitor_THT; do \
		cp -r "$$MOUNT_DIR/share/kicad/3dmodels/$$lib.3dshapes" $(MODELS_DIR)/; \
	done; \
	kill $$MOUNT_PID 2>/dev/null; \
	echo "3D models extracted to $(MODELS_DIR)"

assembly-step: assembly
	@mkdir -p pcb/output
	@test -d $(MODELS_DIR) || $(MAKE) extract-3dmodels
	docker run --rm \
		-v $(CURDIR)/pcb:/pcb \
		-v $(MODELS_DIR):/usr/share/kicad/3dmodels \
		-e KICAD8_3DMODEL_DIR=/usr/share/kicad/3dmodels \
		$(KICAD_IMAGE) kicad-cli pcb export step --force \
		--include-tracks --include-pads --include-silkscreen --include-soldermask \
		-o /pcb/output/assembly_3d.step /pcb/gate_sensor_v2_assembly.kicad_pcb
	@echo "3D STEP file: pcb/output/assembly_3d.step"

# --- Test targets ---

.PHONY: test-netlist

test-netlist:
	python3 pcb/test_netlist.py

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
