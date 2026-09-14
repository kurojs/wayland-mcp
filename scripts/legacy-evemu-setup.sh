#!/bin/bash
# Legacy evemu setup -- DO NOT RUN THIS. Kept only as a record of what the
# upstream setup.sh did, so anyone who already ran it can undo it.
#
# The original script, which this fork removed from the install path:
#
#   1. chmod u+s /usr/bin/evemu-event          # setuid root on an input injector
#   2. /etc/sudoers.d/evemu-event, NOPASSWD    # passwordless root for the same
#   3. usermod -aG input $USER                 # persistent input group membership
#   4. chmod 666 /dev/input/event*             # every input device world-writable
#   5. /etc/udev/rules.d/99-input.rules        # ... and again after every reboot:
#                                              #   KERNEL=="event*", MODE="0666"
#
# Steps 4 and 5 are the serious ones. A world-readable /dev/input lets ANY local
# process -- any script, any browser extension with native messaging, any package
# post-install hook -- read your keystrokes, passwords included, for as long as the
# rule exists. Step 1 hands the same process root. None of it is needed: this fork
# uses the XDG RemoteDesktop portal, which synthesises input with no privilege at
# all, and falls back to wtype or ydotool before ever considering evemu.
#
# To undo a previous run of the upstream script:
#
#   sudo rm -f /etc/udev/rules.d/99-input.rules /etc/sudoers.d/evemu-event
#   sudo chmod u-s /usr/bin/evemu-event
#   sudo gpasswd -d "$USER" input     # optional, if you do not want the membership
#   sudo udevadm control --reload-rules && sudo udevadm trigger
#   # then reboot, or re-plug your input devices, to restore the default 0600 modes
#
# Verify afterwards -- the modes should be 0600 or 0660, never 0666:
#
#   ls -l /dev/input/event*
#   ls -l /etc/udev/rules.d/99-input.rules   # should not exist

echo "This script is documentation, not a setup step. Read it; do not run it." >&2
echo "wayland-mcp needs no privileged setup: see README, section 'Installation'." >&2
exit 1
