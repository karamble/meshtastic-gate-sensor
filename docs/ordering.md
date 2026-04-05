# JLCPCB Ordering Guide


## Generate Fabrication Files

```bash
make fab    # exports Gerbers + drill files to pcb/output/
```

Then zip the contents of `pcb/output/`:

```bash
cd pcb/output && zip -r ../../gate_sensor_gerbers.zip . && cd ../..
```

## Upload to JLCPCB

1. Go to https://www.jlcpcb.com and click **Order now**
2. Click **Add gerber file** and upload `gate_sensor_gerbers.zip`
3. JLCPCB auto-detects board dimensions (75 x 66 mm) and layer count (2)

## Order Form Settings

### Base Options

| Setting | Value | Notes |
|---------|-------|-------|
| Base Material | FR-4 | Default, no change needed |
| Layers | 2 | Auto-detected |
| Dimensions | 75 x 66 mm | Auto-detected |
| PCB Qty | 5 | Minimum order. 5 and 10 are usually the same price. |
| Product Type | Industrial/Consumer electronics | Default |

### Board Specs

| Setting | Value | Notes |
|---------|-------|-------|
| Different Design | 1 | Single design per panel |
| Delivery Format | Single PCB | Not panelized |
| PCB Thickness | 1.6 mm | Standard thickness, default |
| PCB Color | Green | Cheapest and fastest. Other colors may add 1-2 days. |
| Silkscreen | White | Default for green boards |
| Surface Finish | **LeadFree HASL-RoHS** | Select this instead of regular HASL |
| Outer Copper Weight | 1 oz | Default |
| Via Covering | Tented | Default, covers via holes with solder mask |

### Advanced Options

| Setting | Value | Notes |
|---------|-------|-------|
| Board Outline Tolerance | +/- 0.2mm | Default |
| Confirm Production File | Yes | Recommended for first order. JLCPCB engineer reviews your files before production. |
| Remove Order Number | **Yes** | Prevents JLCPCB from placing their order number on your board. May cost ~$1 extra. Alternatively, select "Specify a location" if you added a JLCJLCJLCJLC text placeholder. |
| Flying Probe Test | Fully Test | Default |
| Gold Fingers | No | Not used |
| Castellated Holes | No | Not used |
| Edge Plating | No | Not used |

### Leave as Default

These settings should already be correct at their defaults:

- Mark on PCB: default
- Electrical Test: default (Flying Probe - Fully Test)
- Paper between PCBs: default (No)
- Appearance Quality: default (IPC Class 2)
- Silkscreen Technology: default (Ink-jet printing)

## Checkout

1. Review the auto-generated PCB preview — verify it matches your board outline and drill holes
2. Save to Cart
3. At checkout, select shipping (economy is usually fine for prototype boards)
4. Typical turnaround: 2-5 days production + shipping

## What You Receive

- 5x bare PCBs (no components soldered)
- All through-hole components must be hand-soldered — see [assembly.md](assembly.md)
- The boards arrive in a vacuum-sealed bag

## Reorder

For repeat orders, JLCPCB saves your Gerber files. You can reorder from your order history without re-uploading.
