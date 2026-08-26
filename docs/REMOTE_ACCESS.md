# Remote Access

## Telegram

The Telegram bot works from any internet connection as long as the Life RPG host itself has internet access. The phone and server do not need to be on the same LAN.

## Dashboard

With Tailscale enabled, the installer configures Tailscale Serve. The dashboard is then reachable from authenticated devices in the same tailnet at an HTTPS URL similar to:

```text
https://liferpg.example-tailnet.ts.net
```

It remains private to the tailnet.

## SSH

The installer enables OpenSSH where available. Connect through the host's Tailscale IP or MagicDNS name:

```bash
ssh your-linux-user@100.x.y.z
```

This works across different Wi-Fi networks, hotel client isolation, CGNAT and without router port forwarding, subject to Tailscale policy.

## Without Tailscale

The dashboard remains bound to `127.0.0.1`. You can administer it locally or use an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 user@server
```

Then open `http://127.0.0.1:8080` on the client.

Changing `LIFERPG_DASHBOARD_BIND` to `0.0.0.0` exposes the dashboard to the host LAN and is not the secure default.
