# README.md Snippet for Wayland Support

## Suggested Additions to Main README.md

---

### 1. In "Requirements" or "System Requirements" Section

Add:

```markdown
### Display Server Support

- **X11**: Fully supported (no additional setup)
- **Wayland**: Supported (requires additional setup, see below)

The application automatically detects your session type and uses the appropriate backend.
```

---

### 2. In "Installation" Section

Update dependencies section:

```markdown
### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/aka-NameRec/tap_launcher.git
   cd tap_launcher
   ```

2. Install dependencies:
   ```bash
   # Basic installation (works on X11)
   uv pip install -e .
   
   # For Wayland support, install additional dependencies:
   uv pip install -e ".[wayland]"
   ```

3. **Wayland users only**: Configure permissions:
   ```bash
   sudo usermod -a -G input $USER
   # Logout and login for changes to take effect
   ```

4. Verify installation:
   ```bash
   # Check that applications start
   uv run tap-detector --help
   uv run tap-launcher --help
   ```
```

---

### 3. Add New Section: "Wayland Support"

Insert after installation:

```markdown
## Wayland Support

Starting from version 2.0, both `tap_detector` and `tap_launcher` natively support Wayland display servers.

### Quick Setup for Wayland

1. **Install Wayland dependencies:**
   ```bash
   uv pip install -e ".[wayland]"
   ```

2. **Grant input device access:**
   ```bash
   sudo usermod -a -G input $USER
   ```

3. **Logout and login** (required for group changes to take effect)

4. **Verify setup:**
   ```bash
   groups  # Should show "input" in the list
   echo $XDG_SESSION_TYPE  # Should show "wayland"
   ```

### Troubleshooting

**Permission Error on Wayland?**
- Verify you're in the `input` group: `groups`
- Ensure you logged out and back in after adding the group
- Test with: `python docs/20251024-052851-proposal-wayland_support/poc-evdev-test.py`

**X11 Users**
- No setup required - everything works out of the box
- No need to install `[wayland]` dependencies

For detailed information, see [Wayland Deployment Guide](docs/20251024-052851-proposal-wayland_support/WAYLAND-DEPLOYMENT.md).
```

---

### 4. In "Usage" Section

Add note about automatic backend detection:

```markdown
### Backend Detection

The applications automatically detect your display server:
- **X11 session** → Uses `pynput` backend
- **Wayland session** → Uses `evdev` backend

Check your session type:
```bash
echo $XDG_SESSION_TYPE
```

No configuration needed - it just works!
```

---

### 5. Update "Architecture" or "Technical Details" (Optional)

```markdown
### Keyboard Input Handling

The project uses a **backend abstraction layer** to support multiple display servers:

- **Common Module** (`src/common/`): Shared code for both applications
  - `KeyboardBackend` Protocol: Abstract interface for keyboard input
  - `PynputBackend`: X11 implementation using pynput library
  - `EvdevBackend`: Wayland implementation using evdev library
  - Auto-detection logic based on `XDG_SESSION_TYPE`

Both backends provide identical interfaces, making the codebase session-agnostic.
```

---

## Minimal Version (If Space is Limited)

If README needs to stay concise:

```markdown
## Wayland Support

**Wayland users**: Install additional dependencies and configure permissions:

```bash
uv pip install -e ".[wayland]"
sudo usermod -a -G input $USER
# Logout/login required
```

**X11 users**: No additional setup needed.

See [Wayland Guide](docs/20251024-052851-proposal-wayland_support/WAYLAND-DEPLOYMENT.md) for details.
```

---

## Alternative: Dedicated Section with Collapsible Details

```markdown
## Platform Support

### Display Servers

<details>
<summary><b>X11</b> - Fully supported (click to expand)</summary>

No additional configuration needed. Works out of the box.

**Dependencies**: `pynput` (automatically installed)

</details>

<details>
<summary><b>Wayland</b> - Fully supported (click to expand)</summary>

Requires additional setup:

1. Install dependencies:
   ```bash
   uv pip install -e ".[wayland]"
   ```

2. Configure permissions:
   ```bash
   sudo usermod -a -G input $USER
   # Logout and login
   ```

3. Verify:
   ```bash
   groups  # Should include "input"
   ```

**Dependencies**: `evdev>=1.9.2`

See [full guide](docs/20251024-052851-proposal-wayland_support/WAYLAND-DEPLOYMENT.md).

</details>
```

---

## Badge Suggestion (Optional)

Add to top of README:

```markdown
![X11](https://img.shields.io/badge/X11-supported-brightgreen)
![Wayland](https://img.shields.io/badge/Wayland-supported-brightgreen)
![Platform](https://img.shields.io/badge/platform-linux-blue)
```

