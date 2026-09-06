# Test Suites

A Test Suite is the list of tests for a [Design](designs.md). It has two parts: **Test Steps**
and **Manual Checks**. A Test Step is an automated action, such as reading a voltage or uploading
firmware. A Manual Check is a plain checklist item for a human operator, such as "Confirm LED
lights up green".

A tester system, such as a Testomatic chassis, runs the Test Steps and shows the Manual Checks to
the operator. The Register does not run the tests itself. It only stores the definition. See
[Test Suite Package Format](../api/test-suite-package.md) for how a tester reads this data.

Only staff users can create or edit a Test Suite.

## Opening a Test Suite

1. Open the [Design](designs.md) detail page for the board.
2. Click the **Test Suite** tab.

The tab shows two cards: **Test Steps** and **Manual Checks**, plus a **Testing** section further
down for firmware and other test-related files.

## Draft and saved versions

Each Test Suite has a version number. A version is either a **draft** or a **saved** version.

- A saved version is locked. It never changes after you save it.
- A draft is the version you are working on now. You can add, edit, reorder, and delete items in
  it freely.

A Design starts with no Test Suite. When you add the first Test Step or Manual Check, the
Register creates version 1 as a draft.

Once you save that draft, it becomes the current saved version. If you then add, edit, reorder,
or delete a step or check, the Register automatically creates a new draft, one version number
higher, and copies the saved version's steps and checks into it first. Your change applies to
this new draft, not to the saved version.

### Saving a draft

Click **Save as New Version** to lock the draft. It becomes the current saved version. This is
the version a tester downloads and runs.

### Discarding a draft

Click **Discard Draft** to delete the draft. This undoes every change made since the last saved
version.

### Version history

If a design has more than one version, click **Version History** to see every past version, with
its step count, check count, and creation date. Click a version to view it. A past version is
read-only. You cannot edit it.

## Test Steps

The Test Steps card lists every step in the current draft or saved version, in the order the
tester runs them. Each step shows its type, its name, and a short summary of its configuration.

### Adding a step

1. In the Test Steps card, select a step type from the dropdown.
2. Click **Add**.
3. Fill in the fields for that step type. See [Test Step types](#test-step-types) below.
4. Click **Save**.

### Editing a step

1. Click the step in the list.
2. Change the fields you need.
3. Click **Save**.

### Reordering steps

Drag a step by the grip handle (⠿) on the left to move it up or down.

### Removing a step

Click the trash icon on a step's row.

### Abort on fail

Each step has an **Abort On Fail** checkbox. When checked, a failed reading on this step stops
the tester from running the remaining steps.

## Test Step types

Every step type is listed below, with its configuration fields as they appear on the edit page.
A field marked **Required** must have a value. A field marked **Optional** can be left blank.

### Delay

Waits before running the next step.

| Field | Required | Description |
|---|---|---|
| Delay (ms) | Yes | How long to wait, in milliseconds |

### Upload Firmware

Uploads a firmware image to the device under test.

| Field | Required | Description |
|---|---|---|
| Upload Tool | Yes | The tool that writes the firmware: avrdude, esptool.py, OpenOCD, or STM32CubeProgrammer |
| Serial Port / Device | Yes | The serial port or device identifier to upload through |
| Firmware Binary Image | Yes | The firmware file name, matched against a file in the Test Suite Package |

### Beep

Sounds a beep, or a sequence of beeps.

| Field | Required | Description |
|---|---|---|
| Duration (ms) | Yes | How long each beep lasts, in milliseconds |
| Count | No | Number of beeps. Leave blank for one beep |

### Read Rail Voltage

Reads a power rail's voltage and checks it falls within a range.

| Field | Required | Description |
|---|---|---|
| Power Rail | Yes | 3.3V, 5V, or 12V |
| Min V | Yes | Lowest acceptable voltage |
| Max V | Yes | Highest acceptable voltage |

### Read Rail Current

Reads a power rail's current draw and checks it falls within a range.

| Field | Required | Description |
|---|---|---|
| Power Rail | Yes | 3.3V, 5V, or 12V |
| Min mA | Yes | Lowest acceptable current |
| Max mA | Yes | Highest acceptable current |

### Control Power Rail

Turns a power rail on or off.

| Field | Required | Description |
|---|---|---|
| Power Rail | Yes | 3.3V, 5V, or 12V |
| Action | Yes | ON or OFF |

### Python

Runs a block of Python code as the step. The Register checks that the code is valid Python. It
does not run the code itself. A tester system runs it.

| Field | Required | Description |
|---|---|---|
| Python Code | Yes | The Python source code to run |

### IOMOD Analog Read

Reads an analog value from an IOMOD pin, and can check it falls within a range.

| Field | Required | Description |
|---|---|---|
| IOMOD | Yes | IOMOD identifier, A through G |
| Pin | Yes | Pin number, 0 through 7 |
| Expect Min | No | Lowest acceptable reading |
| Expect Max | No | Highest acceptable reading |

### IOMOD Digital Read

Reads a digital value from an IOMOD pin and checks it against an expected value.

| Field | Required | Description |
|---|---|---|
| IOMOD | Yes | IOMOD identifier, A through G |
| Pin | Yes | Pin number, 0 through 7 |
| Expect | Yes | Expected value, 0 or 1 |

### IOMOD Digital Write

Writes a digital value to an IOMOD pin.

| Field | Required | Description |
|---|---|---|
| IOMOD | Yes | IOMOD identifier, A through G |
| Pin | Yes | Pin number, 0 through 7 |
| Write | Yes | Value to write, 0 or 1 |

### IOMOD Analog Write

Writes an analog value to an IOMOD pin.

| Field | Required | Description |
|---|---|---|
| IOMOD | Yes | IOMOD identifier, A through G |
| Pin | Yes | Pin number, 0 through 7 |
| Write | Yes | Value to write |

### LED Spectral Reading

Reads color and light values from an I2C spectral sensor. The sensor can connect directly, or
through a MUX.

| Field | Required | Description |
|---|---|---|
| I2C Addr | Yes | The sensor's I2C address, as hex text, for example `0x29` |
| MUX Chan | Yes | MUX channel, 0 through 7 |
| MUX Addr | No | The MUX's I2C address, as hex text, for example `0x71`. Leave blank if the board has no MUX |
| RMin / RMax | No | Acceptable range for the red channel |
| GMin / GMax | No | Acceptable range for the green channel |
| BMin / BMax | No | Acceptable range for the blue channel |
| LuxMin / LuxMax | No | Acceptable range for brightness (lux) |
| IRMin / IRMax | No | Acceptable range for the infrared channel |

### Operator Intervention

Shows an instruction to a human operator and waits for the operator to act. Unlike the other
step types, it does not take an automated reading.

| Field | Required | Description |
|---|---|---|
| Message | Yes | The instruction text to show the operator |

## Manual Checks

The Manual Checks card lists plain checklist items, shown to the operator alongside the Test
Steps above. A Manual Check has no configuration. It is a single line of text, for example
"Confirm LED lights up green".

### Adding a manual check

1. Type the check's text into the box at the bottom of the Manual Checks card.
2. Click **Add**.

### Editing, reordering, and removing a manual check

- Click a check to edit its text.
- Drag a check by the grip handle (⠿) to reorder it.
- Click the trash icon on a check's row to remove it.

Manual Checks share the same draft and saved version as Test Steps. Adding, editing, reordering,
or deleting a check follows the same draft rules described in
[Draft and saved versions](#draft-and-saved-versions) above.

## Copying a Test Suite from another design

If another design already has a Test Suite, you can copy it instead of building one from scratch.

1. In the **Copy Test Suite from** box, select the source design.
2. Click **Copy Test Suite**.

This appends the source design's current saved Test Steps and Manual Checks to the end of this
design's own lists. It copies each step's full configuration. It does not copy an unsaved draft
from the source design.

## Downloading a Test Suite Package

Click **Download** to download the version shown on the tab as a **Test Suite Package**, a ZIP
file a tester system can read. See [Test Suite Package Format](../api/test-suite-package.md) for
the file layout and field definitions.
