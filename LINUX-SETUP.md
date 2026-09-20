# Linux setup notes (EndeavourOS · KDE Plasma 6 Wayland · Ghostty · zsh)

What was configured when moving from Windows (pwsh / Windows Terminal) to Linux,
why, and how to undo it. Set up with Claude Code on 2026-09-18/19.

Machine: EndeavourOS (Arch), KDE Plasma 6.7 on Wayland, two monitors —
DP-1 portrait 1080×1920 (left, "thin") and HDMI-A-2 landscape 1920×1080 (right, "wide").
Spanish keyboard layout.

---

## 1. File map

| What | File |
|---|---|
| Ghostty main config | `~/.config/ghostty/config` |
| Ghostty drop-down-only config | `~/.config/ghostty/dropdown` |
| Ghostty Velvet colour theme (unused, kept) | `~/.config/ghostty/themes/velvet` |
| Drop-down how-it-works + rollback | `~/.config/ghostty/DROPDOWN-ROLLBACK.md` |
| Drop-down KWin script | `~/.local/share/kwin/scripts/ghostty-dropdown/contents/code/main.js` |
| Drop-down service | `~/.config/systemd/user/ghostty-dropdown.service` |
| KWin window rule (drop-down) | `~/.config/kwinrulesrc` |
| zsh config | `~/.zshrc` |
| zsh extra plugins | `~/.oh-my-zsh/custom/plugins/{fzf-tab,you-should-use}` |
| Prompt (in use) | `~/.config/oh-my-posh/tokyonight.omp.json` |
| Prompt (Velvet, fixed but unused) | `~/.config/oh-my-posh/velvet.omp.json` |
| Claude Code settings | `~/.claude/settings.json` |
| Claude Code theme (in use) | `~/.claude/themes/tokyonight.json` |
| Claude Code status line layout | `~/.claude/claude.omp.json` |
| Claude Code status line wrapper | `~/.claude/statusline.sh` |
| Passwordless sudo | `/etc/sudoers.d/zz-pablo-nopasswd` |
| Update notifier config | `~/.config/arch-update/arch-update.conf` |
| Own builds: clones / PKGBUILDs | `~/Projects/<name>` / `~/Projects/pkgbuilds/<name>-local/` |
| RGB scripts (monitor, theme, fan test) | `~/personalization/openrgb/` (section 8) |
| RGB services (symlinks into the folder above) | `~/.config/systemd/user/{openrgb,rgb-monitor}.service` |
| OpenRGB settings (zone sizes, segments) / profile | `~/.config/OpenRGB/Configuration.json` / `profiles/Synthwave.json` |
| CoolerControl fan curve | `/etc/coolercontrol/config.toml` (backup `config.toml.before-fan-curve`) |

Backups from this session: `~/.zshrc.bak`, `~/.zshrc.bak2`, `~/.config/ghostty/config.bak`,
`~/.config/ghostty/config.bak2`, `~/.claude/backups/settings.json.pre-velvet`.

Reload after editing:
- Ghostty (all windows, incl. drop-down): `pkill -USR2 -x ghostty`
  (Ctrl+Shift+, doesn't work on the Spanish layout — Shift+, is `;`)
- zsh: open a new tab (or `exec zsh`)
- KWin script: `qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript ghostty-dropdown && qdbus6 org.kde.KWin /KWin reconfigure`

---

## 2. Ghostty

`~/.config/ghostty/config` highlights:

- **Theme:** `TokyoNight Night`, `background-opacity = 0.8`, `background-blur = true`.
- **Windows-style copy/paste:**
  - `performable:ctrl+c=copy_to_clipboard` — copies only when text is selected, otherwise Ctrl+C still interrupts.
  - `ctrl+v=paste_from_clipboard`
  - `right-click-action = copy-or-paste`
  - Ctrl+Shift+C/V still work. In vim use Ctrl+Q for block select (Ctrl+V is taken).
- **Stray `^[[200~` on paste** came from zsh's Ctrl+V ("insert next key literally"); binding Ctrl+V to paste fixed it.
- `cursor-style = bar`, `mouse-hide-while-typing`, padding 8×6 with `window-padding-balance = true`.
- `shell-integration-features = cursor,sudo,title,ssh-env,ssh-terminfo,path` — ssh-env/ssh-terminfo avoid "unknown terminal type" on servers.
- The old `global:super+º=toggle_quick_terminal` line is commented out (replaced by the drop-down below).

Ghostty runs as a single background instance (`app-com.mitchellh.ghostty.service`), so config
changes need a reload (see above) — a new window alone doesn't re-read the config.

### Known issue: blur doesn't work on Wayland (yet)
KDE Plasma 6.7 dropped the old `org_kde_kwin_blur` protocol; Ghostty 1.3.1 only knows that one, so it
gets plain transparency. Fixed in Ghostty's next release (PR #10727, uses `ext-background-effect-v1`)
— it will arrive through normal updates, no config change needed.
- https://github.com/ghostty-org/ghostty/discussions/13041
- https://github.com/ghostty-org/ghostty/pull/10727

Under X11 (`GDK_BACKEND=x11`) blur works but KDE also blurs the invisible shadow margin → grainy band. Rejected.

---

## 3. Super+º drop-down terminal

Ghostty's built-in quick terminal can't be resized with the mouse on Linux, so it was replaced by a
normal Ghostty window driven by a KWin script. Full details and rollback: `~/.config/ghostty/DROPDOWN-ROLLBACK.md`.

Behaviour:
- **Super+º** shows/hides it; appears at the top of the monitor under the mouse, always full width.
- Drag the bottom edge to resize; height is remembered per monitor until logout (default 50%).
- No title bar/frame (`--window-decoration=client --gtk-titlebar=false`), stays on top, not in taskbar/Alt+Tab.
- Hidden = parked off-screen at −30000 (not minimized) → no flash when switching monitors.
- If closed with `exit`, the next Super+º starts a fresh one (first press after login takes ~1 s).
- Drop-down-only Ghostty settings in `~/.config/ghostty/dropdown`: `window-padding-balance = false`
  (stops text jitter while resizing), `resize-overlay = never` (no cols×rows popup).

### Why it's tiled: the GTK/KWin size cap
Native-Wayland GTK windows can never grow beyond the size of the monitor they were created on:
KWin sends the size bounds only once (at creation), and GTK treats them as a permanent cap.
Known upstream, unfixed:
- GTK: https://gitlab.gnome.org/GNOME/gtk/-/issues/7869 (open; MR !9916 unmerged)
- KWin sends `configure_bounds` only with 0×0 configures: `src/xdgshellwindow.cpp`
- Ghostty discussions: #9421, #7984, #4869

Tiled windows skip the cap, so the script **quick-tiles the window to the top of the screen** while
it's shown (staged just above the target screen off-screen first, so nothing flashes), then sets the
height; it un-tiles before parking. A KWin rule (`ghostty-dropdown-first-screen`, position 1080,403)
also creates it on the wide monitor as a safety net — update that position if the monitor layout changes.

Tried and rejected: X11 backend (grainy blur band), window rule alone (moved the cap to the height).

---

## 4. zsh (oh-my-zsh + oh-my-posh)

Plugins (`~/.zshrc`): `git sudo colored-man-pages command-not-found fzf zoxide extract copypath
you-should-use fzf-tab zsh-autosuggestions zsh-syntax-highlighting` (syntax-highlighting must stay last,
fzf-tab must come before the last two).

| Key / command | Does |
|---|---|
| → | accept grey suggestion (history first, then completion) |
| Tab | fzf-tab searchable completion picker |
| Ctrl+R | fzf history search |
| ↑ | history search by what's typed |
| Esc Esc | prefix `sudo` |
| Ctrl+U | clear the line · Ctrl+C abandon it · Ctrl+_ or Ctrl+Z undo · Ctrl+Y redo |
| Ctrl+Backspace / Ctrl+Delete | delete word back / forward |
| `z foo` / `zi` | zoxide jump / pick |
| `ls` `ll` `la` `lt` | eza (icons, git status, tree) |
| `cat` | bat (terminal colours); `command cat` for plain |
| `extract f.zip` · `copypath` | unpack anything · copy current path |

Other settings: `zstyle ':completion:*' rehash true` (new commands complete without a new tab),
`ZSH_AUTOSUGGEST_STRATEGY=(history completion)`, dotnet completion, 50k history,
case-insensitive completion, `~/.local/bin` on PATH.

PowerShell profile equivalents: Terminal-Icons → eza · z → zoxide · PSReadLine predictions →
zsh-autosuggestions · Windows edit mode → key bindings above · winget completion → built-in pacman completion.

Tried and reverted: **zsh-autocomplete** (live list below the prompt) — replaces fzf-tab and fights
oh-my-zsh over keys.

---

## 5. Prompt and Claude Code theming

Colour scheme: Tokyo Night (Ghostty theme, prompt, Claude Code theme and status line all match).
The Velvet set from this repo was the starting point; its layout is kept, recoloured.

Prompt design rules (both the zsh prompt and the Claude Code status line):
- **Two groups:** left (folder › git › …) and right (… › weather / usage), joined "bubbles".
- **Gradient:** each group goes dark at the screen edge → light towards the centre
  (`#292e42` → `#3d59a1`).
- **Caps** (Nerd Font powerline half-circles: U+E0B6 = left-rounded, U+E0B4 = right-rounded):
  - left groups: open U+E0B6 · separators U+E0B4 · close U+E0B4
  - right groups (mirrored): open U+E0B6 · separators U+E0B6 · close U+E0B4. They use `diamond` segments with
    `"leading_diamond": "<background,parentBackground>\ue0b6</>"` and `"trailing_diamond": "\ue0b4"` on the last one.
- **Never** use oh-my-posh `invert_powerline` or a powerline segment first in a block: they draw
  reverse-video caps that look like solid dark shapes on a transparent terminal.

Claude Code (`~/.claude/settings.json`): `theme: custom:tokyonight`, status line = `~/.claude/statusline.sh`
(runs `oh-my-posh claude`, padding the right group 6 columns short of the terminal width — change
`MARGIN` there if it's cut off or leaves a gap). Left group: folder › git › lines changed; right:
model/context › effort › 5-hour usage. Also merged from Windows: empty commit/PR attribution,
`model: opus`, `autoUpdatesChannel: latest`, etc.

Note: the weather segment in `tokyonight.omp.json`/`velvet.omp.json` contains an OpenWeatherMap API key in plain text.

---

## 6. System

- **Passwordless sudo** (explicit choice; anything running as you gets root silently):
  `/etc/sudoers.d/zz-pablo-nopasswd`. Undo: `sudo rm /etc/sudoers.d/zz-pablo-nopasswd`
- **Updates: Arch-Update** (AUR, by an Arch packager). Tray icon at login, checks at boot + every 6 h
  (`arch-update.timer`), click → updates official + AUR (yay) in Ghostty, shows Arch news first,
  offers post-update cleanup (orphans, cache, .pacnew, reboot needed). Run manually: `arch-update`.
  `eos-update-notifier` was discontinued on 2026-09-01 — don't use it.
- Fully automatic updates were deliberately not set up (Arch manual-intervention news, .pacnew files, AUR).

---

## 7. Own builds from git (done 2026-09-19)

Rule: **clones live in `~/Projects/<name>`, PKGBUILDs in `~/Projects/pkgbuilds/<name>-local/`.**
Each PKGBUILD builds the clone's *working tree* (uncommitted changes included) into a normal pacman
package, so pacman tracks the files and nothing is `make install`ed by hand. Packages are named
`*-local` on purpose: names like `openrgb-git` exist in the AUR, and yay/Arch-Update would "update"
them with upstream code, discarding your changes.

Rebuild + install after editing or `git pull`ing a clone:
```sh
cd ~/Projects/pkgbuilds/<name>-local && makepkg -sfi
```

### Shader Wallpaper — `~/Projects/shader-wallpaper` → package `plasma6-wallpapers-shader-local`
- Upstream: https://github.com/y4my4my4m/kde-shader-wallpaper. v4 needs compiling (C++ QML plugin), so a
  symlink wasn't enough. Installed system-wide: `/usr/share/plasma/wallpapers/online.knowmad.shaderwallpaper`
  + `/usr/lib/qt6/qml/online/knowmad/shaderwallpaper/`.
- The build writes into `package/`, so the PKGBUILD rsyncs the clone to a scratch dir first (clone stays clean).
- After a rebuild: `systemctl --user restart plasma-plasmashell`.
- 2026-09-19: opening the wallpaper settings freezes plasmashell on Plasma 6.7 (main thread 100%, endless QML loop) — on master `6a8c01e` AND on release v4.1.1, so it's not the post-release dialog changes. Logs in `~/Projects/pkgbuilds/plasma6-wallpapers-shader-local/config-freeze-*.log`. Back on master. Don't open the settings; recover with `systemctl --user restart plasma-plasmashell` (Super+º terminal still works). Not reported upstream yet.
- Replaced the KDE Store 3.0.3 copy (removed from `~/.local/share/plasma/wallpapers/` and from
  `~/.local/share/knewstuff3/wallpaperplugin.knsregistry`). v3 settings pointed at `Shaders6/*.qsb`, which no
  longer exists; both desktops were repointed to `contents/ui/Shaders/Night_Sky.frag`.
- Rollback: `~/Projects/pkgbuilds/plasma6-wallpapers-shader-local/rollback-kde-store-3.0.3/` has the old plugin
  folder, the knsregistry and `plasma-org.kde.plasma.desktop-appletsrc`: `sudo pacman -R plasma6-wallpapers-shader-local`,
  copy them back (plugin → `~/.local/share/plasma/wallpapers/`), restart plasmashell.

### OpenRGB — `~/Projects/OpenRGB` → package `openrgb-local`

**Status (2026-09-19): fixed locally, installed, not sent upstream yet.** The RAM was already supported
([MR !2435](https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/2435), closed
[#2879](https://gitlab.com/CalcProgrammer1/OpenRGB/-/work_items/2879)); what broke it was
[#5698](https://gitlab.com/CalcProgrammer1/OpenRGB/-/work_items/5698): with the kernel's `spd5118` DDR5 temperature
driver loaded, the RAM wasn't detected.
- **Root cause:** this board's Intel chipset has "SPD Write Disable" set, which blocks writes to the SPD chips
  (0x50–0x57), including the page register. Only the first 128 bytes (page 0) of each stick's SPD are readable,
  by the kernel or anyone else. OpenRGB read the `spd5118` sysfs `eeprom` file in one 2048-byte go, which fails as
  a whole, and then used uninitialised memory (type "Unknown", JEDEC ID 0x0000). Without the kernel driver it only
  worked by accident: the failed page switch returns page-0 bytes 0x30 0x10, and upstream had added 0x300F /
  0x3011 as extra "Kingston" IDs (they're really those aliased bytes).
- **Fix 1** (`SPDAccessor/SPD5118Accessor_Linux.{cpp,h}`): read the eeprom page by page and use page-0 data for
  unreadable pages, the way the hardware behaves. RAM is now detected with `spd5118` loaded, and RAM temps keep working.
- **Fix 2** (`cli.cpp`, `Controllers/KingstonFuryDRAMController/RGBController_KingstonFuryDRAM.{cpp,h}`): a race.
  Command-line colour changes updated the RAM from two threads at once, so some LEDs kept a stale colour (e.g. one
  red LED on one stick). The CLI now queues the update, and the Kingston driver locks around each update.
- **Fix 3** (`Controllers/CorsairLightingNodeController/CorsairLightingNodeController.cpp`): the Commander Pro's
  firmware version is part of how OpenRGB matches saved settings to a device. At boot, other programs
  (CoolerControl, the kernel driver) talk to it at the same time, it once reported "0.0.0", and OpenRGB then
  ignored the saved zone sizes and segments (the RGB monitor crash-looped). The version request now drops stale
  replies and retries until it gets a real version.
- All three are uncommitted in the clone and belong in separate upstream MRs (#5698, the race, the retry).
- Seen on resume: `spd5118 9-005x: Failed to write b = 0: -6`. That's the same write block (the kernel restoring
  the page register). Harmless.
- Upstream: https://gitlab.com/CalcProgrammer1/OpenRGB (partial clone: full history, blobs fetched on demand).
- Build: qmake (`OpenRGB.pro`); see `Documentation/Compiling.md`, `SMBusAccess.md`.
- Hardware: 2×16 GB Kingston Fury DDR5-5600 (`KF556C40-16`) on ASUS ROG STRIX B660-G GAMING WIFI.
- RAM access (SMBus) prerequisites already OK: `i2c-dev` loaded, Intel SMBus `i2c_i801`, user in `i2c` group.
- Existing RAM drivers to use as templates: `Controllers/{CorsairDRAMController,KingstonFuryDRAMController,HyperXDRAMController,GigabyteRGBFusion2DRAMController}`.
- Installed: `openrgb-local` (replaced the official `openrgb` 1.0; same files: binary, udev rules generated
  by the new binary, `openrgb.service`, modules-load and tmpfiles configs from the official package).
  Verified: same detection as the official build (RAM only with `spd5118` unloaded).
- After changing the clone: `makepkg -sfi` in `~/Projects/pkgbuilds/openrgb-local`.
  For quick tests you can also run the binary from `~/Projects/pkgbuilds/openrgb-local/src/build/openrgb`.
- Back to the official package: `sudo pacman -S openrgb` (replaces `openrgb-local`). That brings the RAM
  detection bug back until upstream has the fix.
- The package's system-wide `openrgb.service` (`/usr/lib/systemd/system/`) stays **disabled**. The user service in
  section 8 runs the server instead; enabling both would clash on port 6742.

Each clone has a `CLAUDE.md` (excluded from git via `.git/info/exclude`) with the goals, findings and workflow — Claude sessions started in that folder load it automatically.

---

## 8. RGB lighting and fan control (done 2026-09-19)

Everything starts automatically at login, and the LEDs switch off while the PC sleeps.

### Hardware map
| Device (OpenRGB) | Zone / segment | LEDs | What it is |
|---|---|---|---|
| Corsair Commander Pro | RGB Header 1 → **Exhaust** | 0–15 | chain order; each fan = 4 inner-ring LEDs, then 12 outer-ring LEDs |
| | → **Middle Radiator** | 16–31 | |
| | → **Top Radiator** | 32–47 | |
| | → **Bottom Radiator** | 48–63 | |
| | RGB Header 2 → **Pump** | 0–9 | |
| | → **Cooler** (block on the CPU) | 10–17 | |
| Kingston Fury DDR5 | Fury Slot 1 / Fury Slot 2 | 12 each | sticks in board slots 2 (0x61) and 4 (0x63); LED 0 = bottom |
| ASUS ROG STRIX B660-G | Aura Mainboard | 4 | LED 2 = ROG eye, "RGB Header 1" = WiFi logo; LED 1 and "RGB Header 2" light nothing |
| | Addressable RGB Header 1–3 | 0 | nothing connected (sized 0) |

Fan speed sensors (Commander Pro, `corsair_cpro` hwmon): fan2 = pump, fan3 = middle radiator, fan4 = bottom
radiator, fan5 = exhaust, fan6 = top radiator. Zone sizes and segments are stored in `~/.config/OpenRGB/Configuration.json`
(copy in `~/personalization/openrgb/openrgb-config/`). They were found by lighting segments in different colours.

### What runs
| Service (`systemctl --user …`) | Does |
|---|---|
| `openrgb.service` | `openrgb --server --profile Synthwave`: SDK server on `127.0.0.1:6742`, loads the theme |
| `rgb-monitor.service` | `rgb_monitor.py`: shows system state on the LEDs (needs `openrgb.service`) |

`rgb_monitor.py` shows:
- **Fan outer rings:** a gauge that fills with that fan's RPM (cyan when idle -> pink at full speed). The bar spans
  `FAN_MIN_RPM` (1,000) to `FAN_MAX_RPM` (1,650), not 0 to max, so idle (~1,100 RPM) is ~2 of 12 LEDs and the ramp to
  full speed uses the whole ring. The pump bar spans `PUMP_MIN_RPM` (3,500) to `PUMP_MAX_RPM` (4,850), so its 4,800 RPM
  sits near the top and a drop would stand out.
- **Fan inner rings:** CPU package temperature, blue (35 °C) → green → yellow → red (85 °C).
- **Cooler:** CPU load as a gauge that fills from green to red.
- **Pump:** a gauge filling with the pump's RPM (full, since the pump runs at a fixed 100 %).
- **RAM:** memory used, filling from the bottom (updated once a second; Kingston writes are slow).
- **Board:** ROG eye pink, WiFi logo cyan.

Colours, speeds and ranges are constants at the top of the script.
**Sleep:** it holds a logind "delay" lock (`systemd-inhibit --list` shows it). When the PC is about to sleep it
switches every device to a black *hardware* mode (Commander Pro and RAM: Static black; board: Off), then lets the
PC sleep. In S3 the USB devices stay powered, and the Commander Pro would fall back to its built-in effect once
frames stop. On wake-up it reconnects, switches everything back to Direct (it waits until the server confirms the
mode, which it applies asynchronously), and resumes. When the service is stopped, it loads the Synthwave profile.
Tested 2026-09-19: Commander Pro and RAM go dark in sleep and come back on wake-up. **The board doesn't:** in sleep
its firmware takes over the Aura LEDs and plays the default ASUS effect, whatever mode was set before. Fix that in the
BIOS: *Advanced › Onboard Devices Configuration › RGB LED lighting › When system is in sleep, hibernate or soft off
states → Off*.

Files in `~/personalization/openrgb/`:
- `rgb_monitor.py`: the monitor.
- `theme.py`: applies the Synthwave theme live. SDK clients can't save profiles on this OpenRGB version, so to
  keep a changed theme, save it as "Synthwave" from the OpenRGB app.
- `fan_test.py`: stops one fan at a time behind colour cues, to map speed sensors to fans. Stop CoolerControl
  first; see the file's header.
- `systemd/`: the two unit files. `~/.config/systemd/user/` has symlinks to them, so edit them here and run
  `systemctl --user daemon-reload`.
- `openrgb-config/`: copies of `Configuration.json` and `Synthwave.json`.
- `requirements.txt`: dependencies for `.venv` (not in git). Recreate with
  `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

```sh
systemctl --user restart rgb-monitor       # after editing rgb_monitor.py
systemctl --user stop rgb-monitor          # pause it (lights go back to Synthwave)
journalctl --user -u rgb-monitor -f        # live log (sleep/wake, speed-read stats every minute)
systemctl --user disable --now rgb-monitor openrgb   # turn both off, no autostart
```
Opening the OpenRGB app is fine: it connects to the running server. But the monitor overwrites manual changes
within a frame, so stop the monitor first.

### Fan control: CoolerControl
CoolerControl (`coolercontrold` system service, app "CoolerControl", web UI `https://localhost:11987`) drives the
4 fans (Commander Pro fan3–fan6, through liquidctl):
- **Profile "Case fans (CPU temp)"** on CPU package temp: 30 °C → 50 %, 50 → 60, 60 → 75, 70 → 90,
  75 °C → 100 %. That's about 1,100 RPM at idle and 1,600 RPM from 75 °C up. Made more aggressive on 2026-09-19
  because of the cooling problem below; the first version (30→30 %, 50→35, 60→45, 70→60, 80→80, 90→100, ~650 RPM
  idle) is in `/etc/coolercontrol/config.toml.before-cooler-curve`.
- **Function "Smooth, quick up":** changes of 2–15 % per second. Slowing down waits 3 s and ignores drops under
  2 °C; speeding up is immediate.
- **Pump (fan2): fixed 100 %** (~4,810 RPM), since 2026-09-19. It was the Commander Pro's own curve (~4,000 RPM)
  before, and more flow through the CPU block helps with the cooling problem below. Backup:
  `/etc/coolercontrol/config.toml.before-pump-100`.

Change the curve in the CoolerControl app. For hand edits, stop the daemon first
(`sudo systemctl stop coolercontrold`), or it overwrites them.

### Known quirks
- **Animation smoothness** (tuned 2026-09-20, latest): `rgb_monitor.py` runs at `FPS = 30`; sending a frame costs ~0.1 ms
  client-side, so the limit is the USB write and the pauses below. Measured: median and p95 frame gap 33 ms over
  ~1,800 frames/minute at 30 fps. Three changes made it smooth during CPU load peaks, which was the remaining
  complaint:
  1. **Sensors are read in a background thread** (`SensorThread`), not in the animation loop. Reading the CPU package
     temperature makes the kernel interrupt a specific core, which took 200-250 ms when all cores were busy and
     stalled the animation exactly during temperature peaks.
  2. **Displayed values are eased** towards new readings (`SMOOTHING_TAU = 2 s`), so the spin rate and colours don't
     jump in steps when the fans ramp (speeds are only read every `RPM_INTERVAL`).
  3. `FPS = 40`, spin rate 1.0 rev/s (`FAN_REVS_PER_SEC_AT_MAX`), and `CPUWeight=400` on both services so they keep
     a CPU share under contention.
  Measured under a full all-core load: 2,375 frames/minute, median and p95 gap 25 ms, worst 28 ms (was 251 ms).
  4. **Spinner -> gauge** (`FAN_STYLE = "gauge"`, the spinner code is still there behind that setting). A speed read
     needs the LED stream to go quiet for ~70 ms or the kernel gets other programs' replies (measured with no pause:
     **0 of 40** batches valid). With a spinner that pause was a visible hitch every few seconds; a gauge doesn't
     move, so it can't be seen, and the frame rate can drop to 15 fps, which makes the USB quieter: read validity
     went from 2/6 to **14/15** per minute. The monitor logs `frame gap median/p95/max` and
  `slow frames` once a minute, so `journalctl --user -u rgb-monitor` shows whether it's still smooth.
- **Three programs share the Commander Pro's USB connection:** the kernel driver, OpenRGB and CoolerControl's
  liquidctl. Its replies carry no request ID, so one program can receive another's reply. Seen: speed reads of 0,
  and the pump's RPM showing up as the 12 V reading. `rgb_monitor.py` pauses the animation for 80 ms before
  reading speeds (every 8 s) and throws away any batch whose 12 V reading isn't about 12 V. Roughly 80-95 % of
  batches are good, and a rejected one just means the displayed speed is up to ~16 s old. That pause is the one regular hitch in the animation; raising `RPM_INTERVAL` trades speed
  freshness for smoothness. CoolerControl's RPM graphs may look jumpy for the same reason. Its fan control doesn't use them, so
  it's unaffected.
- **CPU power limits:** set in the BIOS on 2026-09-19 to Intel's spec for the 12900K: *Ai Tweaker › Internal CPU
  Power Management*, Long and Short Duration Package Power Limit = **241** (W). They were 280/330 W (ASUS
  default). This BIOS has no "Intel Default Settings" or "MultiCore Enhancement" option. Check from Linux:
  `cat /sys/class/powercap/intel-rapl:0/constraint_{0,1}_power_limit_uw`.
- **CPU cooling problem (found 2026-09-19, hardware, not fixed):** even at 241 W the CPU hits 100 °C within
  2 s of an all-core load, then throttles down to ~120 W / ~3.5 GHz (about 2,500 throttle events in 30 s). The
  power limit never comes into play. It drops to ~60 °C within seconds of the load stopping, and all P-cores are
  hot together (92–100 °C; E-cores 84–87). So heat isn't getting from the CPU into the cooler block: check the
  mounting (LGA1700 hardware and pressure, tightened evenly), the thermal paste, any protective film on the cold
  plate, and whether coolant actually flows (the pump reports ~4000 RPM, but that doesn't prove flow). Retest
  afterwards: 30 s full load (`for i in $(seq $(nproc)); do timeout 30 sh -c 'while :; do :; done' & done`) while
  watching `sensors`; a healthy result is well under 100 °C at around 200+ W.
  It's a **custom loop**, and it behaved the same on Windows, so it's older than any of today's changes. In order of
  effort: check flow in the reservoir; check the block's mounting kit is LGA1700 and remount with fresh paste;
  drain and clean the block's microfins if it's clogged.
  CPU block: **Corsair Hydro X XC5 RGB (1200)** (CX-9010011-WW, 16 LEDs in 8 zones, which is why the "Cooler"
  segment is 8 LEDs). Corsair ships it with an **LGA1200 bracket only** and lists no LGA1700 support, so it's
  almost certainly mounted with LGA1200 hardware on this LGA1700 CPU. The LGA1700 package is thinner, so that
  mount presses too lightly, which matches the 100 °C-in-2-seconds behaviour. Fix: an LGA1700 mounting kit for
  Hydro X XC5/XC7 blocks (ask Corsair support or check the Corsair store), or a block made for LGA1700, plus fresh
  paste. LGA1700 holes are 78 mm apart, LGA1200 75 mm.

  **Planned rebuild (as of 2026-09-20, nothing bought yet).** No LGA1700 kit exists for the XC5: Corsair's retrofit
  kits (CW-8960091, CW-8960096) cover only its AIO coolers, and the XC5's bracket is fixed at the LGA1200 75 mm span,
  so a new block is needed. Corsair's LGA1700-capable blocks are the **PRO** models; a listing must say "1700".
  Wrong-generation traps seen on amazon.es: "XC7 Waterblock RGB (1200/AM4)" (~90 €) and anything named **iCUE LINK**
  (needs a LINK hub, won't work with the Commander Pro).
  - **XC7 RGB PRO** (CX-9010015-WW black / -16 white / -17 silver) is the only option that keeps the lighting on the
    Commander Pro, but it was out of stock on amazon.es and corsair.com/es on 2026-09-20. LDLC also lists it.
  - Otherwise the candidates are **5 V ARGB** blocks (Alphacool Core 1 Aurora LT ~108 €, Alphacool Eisblock XPX
    Aurora Edge ~105 € incl. shipping, EK-Quantum Velocity³ ~187 €, Barrow FBLTGI-04I ~84 €). Those plug into one of
    the motherboard's free ARGB headers instead: **resize that zone from 0 to the block's LED count in OpenRGB, add a
    "Cooler" segment there, and point `rgb_monitor.py` at it** (the CPU-load gauge currently lives on Commander Pro
    header 2).
  - Also on the list: **Thermal Grizzly Contact Frame LT** (LGA1700, ~11 €, fixes the socket clamp bending the CPU)
    and **Arctic MX-6** paste (~9 €).
  - Loop work at the same time: hardline tubing is **12 mm OD acrylic**; the new block's ports sit differently, so the
    two CPU runs need re-bending (measure after mounting). Refill with **clear premixed coolant** (no pastel/dye —
    pastels clog block fins), flush the loop with distilled water first, and inspect the old XC5's fins for clogging
    while it's out.
- **RAM speed:** XMP must be on for DDR5-5600 (*Ai Tweaker › Ai Overclock Tuner = XMP I*); on Auto the RAM runs at
  4800. Check: `sudo dmidecode -t memory | grep "Configured Memory Speed"`.
- **If the RGB monitor logs "Commander Pro segments missing":** OpenRGB didn't apply its saved settings (see
  Fix 3 in section 7). Run `systemctl --user restart openrgb`.
- **Corsair K55 RGB PRO detector is disabled** in OpenRGB (`~/.config/OpenRGB/OpenRGB.json` › Detectors, or in
  the app under Settings › Supported Devices). The wired K55 is only plugged in for the BIOS. If it's detected
  and then unplugged, OpenRGB's Corsair V2 keepalive thread (`RGBController_CorsairV2SW::KeepaliveThread`) spins at
  100 % of a core sending to the missing keyboard. That's an OpenRGB bug, not reported yet. Seen as OpenRGB at ~90 %
  CPU, a warm CPU and fans at full speed.
- **Never set lighting in CoolerControl** for the Commander Pro or the Aura controller: it would fight OpenRGB.

---

## 9. Open items (as of 2026-09-19)

**Waiting on upstream (nothing to do, arrives via Arch-Update):**
- Ghostty blur on KDE 6.7 → next Ghostty release (PR #10727). After it lands, check the blur looks right;
  if the drop-down shows a grainy band around it, that's the shadow-margin problem (Ghostty discussion #10719).
- Drop-down size cap → GTK #7869 / MR !9916. If fixed, the quick-tiling in the KWin script becomes optional.

**Planned sessions (context in each clone's `CLAUDE.md`):**
- `~/Projects/shader-wallpaper`: fix the settings-dialog freeze (don't open the wallpaper settings until then;
  switch shaders with the Plasma-scripting command in that `CLAUDE.md`), then custom shader development.
  Not reported upstream yet. `inotify-tools` (needed for `./scripts/dev.sh --watch`) not installed yet.
- `~/Projects/OpenRGB`: the #5698 fix and the Kingston race fix work and are installed, but aren't committed.
  Next: commit on branches and open two upstream MRs (section 7). **Read the Safety section of its `CLAUDE.md`
  first**: never write to 0x48–0x57 on the RAM bus (PMIC voltages / SPD timings).
- RGB: the board's LEDs play the ASUS default effect while asleep. Needs the BIOS option in section 8 (set it
  next time you're in the BIOS, e.g. together with the CPU power limits).

**Undecided / loose ends:**
- Claude Code effort level: `~/.claude/settings.json` has both `"effortLevel": "high"` (merged from Windows) and a
  per-model `"claude-opus-5": {"effortLevel": "medium"}` (from Linux); the per-model one probably wins. Keep one.
- `~/.claude/settings.json` attribution is empty (from Windows) → Claude adds no Co-Authored-By lines to commits/PRs.
- zsh right prompt gradient is per segment, not per visible position: when python/node segments are hidden,
  the centre-most visible bubble (run time) isn't the lightest. Option: base the ramp on weather/git/run time only.
- Drop-down heights reset at every login (accepted); the script could persist them if wanted.
- OpenWeatherMap API key is in plain text in `~/.config/oh-my-posh/{tokyonight,velvet}.omp.json` (and in this
  repo's `oh-my-posh/velvet.omp.json`) — don't publish these files as-is.
- Old prompt `~/.config/oh-my-posh/capr4n.omp.json` and theme `~/.config/ghostty/themes/velvet` are unused
  leftovers; safe to delete.
- RAM runs at 4800 instead of 5600 since the 2026-09-19 BIOS visit (XMP went back to Auto); turn XMP I back on.
- A Corsair K55 RGB PRO keyboard is now detected by OpenRGB. It isn't in the Synthwave profile or the monitor yet.
- Check after the next boots that the Commander Pro keeps its segments (Fix 3 in section 7 was only tested with a
  service restart, not a cold boot).

---

## 10. Troubleshooting cheatsheet

- Super+º does nothing → System Settings › Shortcuts › KWin › "Toggle Ghostty drop-down".
- Drop-down stuck/weird → `exit` in it, press Super+º for a fresh one; or `systemctl --user restart ghostty-dropdown`.
- Ghostty config not applied → `pkill -USR2 -x ghostty`; validate with `ghostty +validate-config`.
- Prompt looks off → test render: `env -u POSH_THEME -u POSH_SESSION_ID oh-my-posh print primary --config ~/.config/oh-my-posh/tokyonight.omp.json --shell zsh`
- Preview Ghostty themes interactively: `ghostty +list-themes`.
- Desktop frozen (e.g. after opening the shader wallpaper settings) → Super+º (drop-down still works, it's
  KWin) → `systemctl --user restart plasma-plasmashell`. Open windows survive.
- RAM not in OpenRGB → the official `openrgb` package replaced `openrgb-local` (the fix is only in the local build):
  rebuild with `cd ~/Projects/pkgbuilds/openrgb-local && makepkg -sfi`.
- LEDs frozen or wrong → `systemctl --user restart openrgb rgb-monitor`; check `journalctl --user -u rgb-monitor`.
- Lights on while asleep → check `journalctl --user -u rgb-monitor` for "LEDs off". Also check the BIOS option
  for LED lighting in sleep state (ASUS: Advanced › Onboard Devices Configuration › RGB LED lighting).
- Rebuild an own package: `cd ~/Projects/pkgbuilds/<name>-local && makepkg -sfi`.
- sudo from Claude Code's `!` prefix needs a TTY — irrelevant now that sudo is passwordless.
