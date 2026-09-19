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

**Finding (2026-09-19): the RAM is already supported.** The old thread was
[#2879](https://gitlab.com/CalcProgrammer1/OpenRGB/-/work_items/2879) (Nov 2022), closed when
[MR !2435](https://gitlab.com/CalcProgrammer1/OpenRGB/-/merge_requests/2435) "Support for Kingston Fury DDR4/5
DIMMs" was merged (2024-07-23, included in the installed 1.0). What breaks it here is the kernel's
`spd5118` DDR5 temperature driver claiming the SPD chips (bus 9, 0x51/0x53):
[#5698](https://gitlab.com/CalcProgrammer1/OpenRGB/-/work_items/5698) (open).
Verified: with `spd5118` loaded → RAM not detected; after `sudo modprobe -r spd5118` → detected as
"Kingston Fury DDR5 DRAM"; reloading it afterwards brings RAM temps back, control lasts until reboot.
Manual workaround: `sudo modprobe -r spd5118; openrgb; sudo modprobe spd5118`.
Options for the future session: (a) boot service that unloads spd5118, starts OpenRGB (server mode) and
reloads the driver; (b) blacklist spd5118 (lose RAM temps); (c) upstream fix for #5698 (the real goal now).
- Upstream: https://gitlab.com/CalcProgrammer1/OpenRGB (partial clone: full history, blobs fetched on demand).
- Build: qmake (`OpenRGB.pro`); see `Documentation/Compiling.md`, `SMBusAccess.md`.
- Hardware: 2×16 GB Kingston Fury DDR5-5600 (`KF556C40-16`) on ASUS ROG STRIX B660-G GAMING WIFI.
- RAM access (SMBus) prerequisites already OK: `i2c-dev` loaded, Intel SMBus `i2c_i801`, user in `i2c` group.
- Existing RAM drivers to use as templates: `Controllers/{CorsairDRAMController,KingstonFuryDRAMController,HyperXDRAMController,GigabyteRGBFusion2DRAMController}`.
- Installed: `openrgb-local` (replaced the official `openrgb` 1.0; same files: binary, udev rules generated
  by the new binary, `openrgb.service`, modules-load and tmpfiles configs from the official package).
  Verified: same detection as the official build (RAM only with `spd5118` unloaded).
- Develop the #5698 fix in the clone, then `makepkg -sfi` in `~/Projects/pkgbuilds/openrgb-local`.
  For quick tests you can also run the binary from `~/Projects/pkgbuilds/openrgb-local/src/build/openrgb`.
- Back to the official package: `sudo pacman -S openrgb` (replaces `openrgb-local`).
- Send the fix upstream as a GitLab MR on #5698.

Each clone has a `CLAUDE.md` (excluded from git via `.git/info/exclude`) with the goals, findings and workflow — Claude sessions started in that folder load it automatically.

---

## 8. Open items (as of 2026-09-19)

**Waiting on upstream (nothing to do, arrives via Arch-Update):**
- Ghostty blur on KDE 6.7 → next Ghostty release (PR #10727). After it lands, check the blur looks right;
  if the drop-down shows a grainy band around it, that's the shadow-margin problem (Ghostty discussion #10719).
- Drop-down size cap → GTK #7869 / MR !9916. If fixed, the quick-tiling in the KWin script becomes optional.

**Planned sessions (context in each clone's `CLAUDE.md`):**
- `~/Projects/shader-wallpaper`: fix the settings-dialog freeze (don't open the wallpaper settings until then;
  switch shaders with the Plasma-scripting command in that `CLAUDE.md`), then custom shader development.
  Not reported upstream yet. `inotify-tools` (needed for `./scripts/dev.sh --watch`) not installed yet.
- `~/Projects/OpenRGB`: fix #5698 (RAM not detected while `spd5118` is loaded). **Read the Safety section of its
  `CLAUDE.md` first** — never write to 0x48–0x57 on the RAM bus (PMIC voltages / SPD timings).

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

---

## 9. Troubleshooting cheatsheet

- Super+º does nothing → System Settings › Shortcuts › KWin › "Toggle Ghostty drop-down".
- Drop-down stuck/weird → `exit` in it, press Super+º for a fresh one; or `systemctl --user restart ghostty-dropdown`.
- Ghostty config not applied → `pkill -USR2 -x ghostty`; validate with `ghostty +validate-config`.
- Prompt looks off → test render: `env -u POSH_THEME -u POSH_SESSION_ID oh-my-posh print primary --config ~/.config/oh-my-posh/tokyonight.omp.json --shell zsh`
- Preview Ghostty themes interactively: `ghostty +list-themes`.
- Desktop frozen (e.g. after opening the shader wallpaper settings) → Super+º (drop-down still works, it's
  KWin) → `systemctl --user restart plasma-plasmashell`. Open windows survive.
- RAM lighting now (until #5698 is fixed): `sudo modprobe -r spd5118; openrgb; sudo modprobe spd5118`.
- Rebuild an own package: `cd ~/Projects/pkgbuilds/<name>-local && makepkg -sfi`.
- sudo from Claude Code's `!` prefix needs a TTY — irrelevant now that sudo is passwordless.
