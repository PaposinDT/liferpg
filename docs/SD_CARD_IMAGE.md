# Full SD-card images

Life RPG application backups and a full block image solve different recovery problems.

## Life RPG backups

The automatic backup system stores database and application recovery artifacts under the configured backup root (normally `/srv/liferpg/backups`). These are compact, version-aware and suitable for restoring Life RPG onto a working Linux installation.

## Full SD image

A block image copies the entire storage device, including:

- Raspberry Pi OS / Debian
- boot partitions and bootloader files stored on the card
- Docker images and volumes
- PostgreSQL data
- Ollama model data
- Life RPG source and backups
- `.env` secrets
- SSH/Tailscale machine state
- every other file on the card

Restoring that image to a sufficiently large replacement card returns the machine to the captured state much more closely than an application-only restore.

## Recommended imaging method

For the most consistent image, shut the Raspberry Pi down cleanly, remove the microSD card and image it from another computer. Do not make a live `dd` image of a mounted, actively changing root filesystem unless you understand the consistency trade-offs.

### Linux/macOS-style block imaging

First identify the card device carefully. The following is an example only:

```bash
sudo dd if=/dev/sdX of=liferpg-sd-YYYYMMDD.img bs=4M status=progress conv=fsync
```

Then optionally compress it:

```bash
zstd -T0 -19 liferpg-sd-YYYYMMDD.img
```

Restore example:

```bash
zstd -dc liferpg-sd-YYYYMMDD.img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
```

Using the wrong `/dev/sdX` destroys the selected disk, so verify the target before writing.

### Windows

Use a disk-imaging utility that supports reading an entire removable drive to an image file, such as USBImager or Win32 Disk Imager. Shut the Pi down, insert the microSD in the PC, create a full image, and store the image on a different physical disk.

## Important caveats

- A restored card must normally be at least as large as the source card in actual sector count.
- The image contains credentials and private data. Encrypt/protect it.
- An image stored on the same microSD is not a backup.
- Tailscale may occasionally require re-authentication after cloning/restoring machine state, especially when multiple clones of the same node are brought online.
- Keep normal Life RPG backups even if you also make SD images. Application backups are faster, smaller and easier to validate regularly.

A useful policy is: automatic Life RPG backups every day, off-device copies regularly, plus an occasional powered-down SD image before major OS/storage changes.
