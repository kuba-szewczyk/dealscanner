#!/usr/bin/env bash
# DealScanner v3 first-login hardening. Run as root on a FRESH Ubuntu 24.04 box.
# Every step here is a direct lesson from the v2 compromise (password SSH left on).
set -euo pipefail

echo "== 1/6 SSH: key-only, survives cloud-init =="
cat >/etc/ssh/sshd_config.d/00-dealscanner-harden.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin prohibit-password
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
EOF
systemctl restart ssh || systemctl restart sshd

echo "== 2/6 Firewall: 22/80/443 only =="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== 3/6 fail2ban + unattended-upgrades =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq fail2ban unattended-upgrades
systemctl enable --now fail2ban
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "== 4/6 Timezone: ET (cron/timer times in this project are ET) =="
timedatectl set-timezone America/New_York

echo "== 5/6 Deploy user =="
if ! id dealscanner &>/dev/null; then
    adduser --disabled-password --gecos "" dealscanner
    mkdir -p /home/dealscanner/.ssh
    cp /root/.ssh/authorized_keys /home/dealscanner/.ssh/
    chown -R dealscanner:dealscanner /home/dealscanner/.ssh
    chmod 700 /home/dealscanner/.ssh && chmod 600 /home/dealscanner/.ssh/authorized_keys
fi

echo "== 6/6 Paranoia pass (anything unexpected here => STOP) =="
echo "-- UID-0 users (must be ONLY root):"
awk -F: '$3==0 {print "   " $1}' /etc/passwd
echo "-- root crontab (should be empty on a fresh box):"
crontab -l 2>/dev/null || echo "   (none)"
echo "-- /dev/shm (no executables expected):"
ls -lA /dev/shm
echo "-- failed password attempts so far:"
grep -c 'Failed password' /var/log/auth.log 2>/dev/null || echo "   0"

echo
echo "DONE. Now verify from a SECOND terminal that 'ssh root@<ip>' works with the"
echo "key and REJECTS passwords, before closing this session."
