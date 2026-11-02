---
title: Linux Command Line Essentials
category: tech
tags: [tech, linux, raspberry pi, reference]
summary: The commands you'll actually use on a Pi or Linux server — files, permissions, processes, services, disks, networking — with a troubleshooting checklist.
---

# Linux Command Line Essentials

Raspberry Pi OS, Ubuntu and Debian (including the server ARK·π runs on) all use these. `sudo` runs a command as administrator. **Tab** autocompletes names, **↑** recalls the last command, **Ctrl+C** stops a running command.

## Moving Around & Files
| Command | Does |
|---|---|
| `pwd` | Where am I? |
| `ls -lah` | List files with sizes and hidden files |
| `cd /opt/offline-server` · `cd ..` · `cd ~` | Change folder · up one · home |
| `cat file` · `less file` | Show a file · scroll it (`q` quits) |
| `head -20 file` · `tail -f log` | First lines · follow a growing log |
| `nano file` | Simple text editor (Ctrl+O save, Ctrl+X exit) |
| `cp a b` · `cp -r dir1 dir2` | Copy file · copy folder |
| `mv a b` | Move or rename |
| `rm file` · `rm -r dir` | Delete (no trash can, so double-check!) |
| `mkdir -p a/b/c` | Make folders |
| `find / -name "*.zim" 2>/dev/null` | Find files by name |
| `grep -ri "tourniquet" /opt/offline-server/content` | Search inside files |
| `tar czf backup.tgz folder/` · `tar xzf backup.tgz` | Make / unpack an archive |

## Permissions & Users
| Command | Does |
|---|---|
| `ls -l` | Shows `rwx` permissions for owner/group/others |
| `chmod +x script.sh` | Make a script runnable |
| `chmod 644 file` · `chmod 755 dir` | Typical file / folder permissions |
| `sudo chown user:user file` | Change owner |
| `whoami` · `id` | Who am I, which groups |
| `sudo adduser name` · `passwd` | Add a user · change your password |

## System & Processes
| Command | Does |
|---|---|
| `htop` (or `top`) | Live CPU/memory/process view (`q` quits) |
| `ps aux \| grep python` | Find a process |
| `kill PID` · `kill -9 PID` | Stop a process · force it |
| `free -h` | Memory use |
| `uptime` | How long it's been on, load average |
| `sudo reboot` · `sudo shutdown -h now` | Restart · power off safely |
| `vcgencmd measure_temp` | Pi CPU temperature |

## Services (systemd)
| Command | Does |
|---|---|
| `systemctl status offline-server` | Is ARK·π running? Recent log lines |
| `sudo systemctl restart offline-server` | Restart it |
| `sudo systemctl enable --now kiwix` | Start now and at every boot |
| `journalctl -u offline-server -n 50` | Last 50 log lines for a service |
| `journalctl -u kiwix -f` | Follow a log live |

## Disks & Storage
| Command | Does |
|---|---|
| `df -h` | Free space per drive |
| `du -sh /opt/*` | What's using space |
| `lsblk` | List drives and partitions (find the SSD: `/dev/sda`) |
| `sudo mount /dev/sda1 /mnt` · `sudo umount /mnt` | Attach / detach a drive |
| `sudo blkid` | Drive IDs (for `/etc/fstab` auto-mount) |

## Networking
| Command | Does |
|---|---|
| `hostname -I` | My IP address(es) |
| `ip a` | All network interfaces |
| `ping -c 4 10.42.0.1` | Can I reach it? |
| `nmcli device wifi list` | Nearby Wi-Fi networks |
| `nmcli device status` | Wi-Fi/Ethernet state |
| `ss -ltnp` | Which programs are listening on which ports |
| `curl -I http://localhost:8000` | Is a web server answering? |
| `ssh user@host` · `scp file user@host:/path` | Remote login · copy a file over |

## Packages (need internet, or a local cache)
| Command | Does |
|---|---|
| `sudo apt update` | Refresh package lists |
| `sudo apt install -y name` | Install |
| `sudo apt full-upgrade -y` | Upgrade everything |
| `apt search word` | Find a package |
See [Offline Software Stockpile](/tech/offline_software_stockpile) for installing **without** internet.

## Shortcuts
- `command > file` writes output to a file; `>>` appends; `2>&1` includes errors.
- `cmd1 | cmd2` pipes output into the next command.
- `!!` repeats the last command (`sudo !!` = "do that again as admin").
- `history | grep apt` finds a command you ran before.
- `man ls` shows the manual for a command (`q` to quit). The Bash manual is in the offline [Library](/library#wiki).

## Troubleshooting Checklist
1. **Is it running?** `systemctl status name`
2. **What does the log say?** `journalctl -u name -n 50`
3. **Disk full?** `df -h`
4. **Is the port open?** `ss -ltnp`
5. **Network up?** `hostname -I`, `ping`
6. **Power OK (Pi)?** `vcgencmd get_throttled` should be `0x0`
7. **Turn it off and on again**, properly: `sudo reboot`
