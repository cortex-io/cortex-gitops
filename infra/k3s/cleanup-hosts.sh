#\!/bin/bash
# Remove stale hardcoded registry IPs from /etc/hosts on all k3s nodes
# These cause DNS resolution to bypass proper DNS and hit dead IPs
# Run via: for node in k3s-master0{1..3} k3s-worker0{1..4}; do ssh $node 'sudo bash /etc/rancher/k3s/cleanup-hosts.sh'; done

sed -i '/production.cloudflare.docker.com/d' /etc/hosts
sed -i '/registry-1.docker.io/d' /etc/hosts
sed -i '/registry.npmjs.org/d' /etc/hosts
sed -i '/dl-cdn.alpinelinux.org/d' /etc/hosts
sed -i '/pypi.org/d' /etc/hosts
sed -i '/files.pythonhosted.org/d' /etc/hosts
echo 'Stale /etc/hosts entries removed'