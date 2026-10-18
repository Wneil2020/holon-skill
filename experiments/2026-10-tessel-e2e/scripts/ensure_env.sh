#!/bin/sh
# Re-create what a sandbox reset wipes: Chromium (debs cached under /workspace) and the playwright client (under /workspace).
D=/workspace/tools/debs
if ! which chromium >/dev/null 2>&1; then
  if ls $D/*.deb >/dev/null 2>&1; then sudo dpkg -i $D/*.deb >/dev/null 2>&1 || true; fi
  if ! which chromium >/dev/null 2>&1; then
    sudo apt-get update -q >/dev/null 2>&1
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q chromium fonts-noto-cjk >/dev/null 2>&1
    mkdir -p $D && cp /var/cache/apt/archives/*.deb $D/ 2>/dev/null
  fi
fi
[ -d /workspace/tools/py/playwright ] || pip install -q --target /workspace/tools/py playwright >/dev/null 2>&1
which chromium; ls /workspace/tools/debs | wc -l
