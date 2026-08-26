#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import shutil
from pathlib import Path


def mem_mb() -> int:
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 0


def disk_gb(path: str = '/') -> float:
    usage = shutil.disk_usage(path)
    return round(usage.free / 1024**3, 1)


def main() -> None:
    os_release = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                os_release[key] = value.strip('"')
    except OSError:
        pass

    data = {
        'system': platform.system(),
        'architecture': platform.machine(),
        'distribution': os_release.get('PRETTY_NAME', 'unknown'),
        'systemd': Path('/run/systemd/system').exists(),
        'memory_mb': mem_mb(),
        'disk_free_gb': disk_gb(),
        'docker': shutil.which('docker') is not None,
        'tailscale': shutil.which('tailscale') is not None,
    }
    print(json.dumps(data, indent=2))

    if data['system'] != 'Linux':
        raise SystemExit('Life RPG automated installer currently supports Linux only.')
    if data['architecture'] not in {'aarch64', 'arm64', 'x86_64', 'amd64'}:
        raise SystemExit(f"Unsupported architecture: {data['architecture']}")
    if not data['systemd']:
        raise SystemExit('systemd is required for automatic backup scheduling.')
    if data['memory_mb'] and data['memory_mb'] < 1800:
        print('WARNING: less than 2 GB RAM detected; local AI should be disabled.', flush=True)
    if data['disk_free_gb'] < 4:
        raise SystemExit('At least 4 GB free disk space is required; 8+ GB is recommended.')


if __name__ == '__main__':
    main()
