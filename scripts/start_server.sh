#!/bin/sh
# Runs INSIDE WSL as root: (re)generate Caddyfile with current eth0 IP and (re)start Caddy.
IP=$(ip -4 addr show eth0 | sed -n 's/.*inet \([0-9.]*\).*/\1/p')
cat > /root/Caddyfile <<EOF
{
	auto_https disable_redirects
	local_certs
	servers :8441 {
		protocols h1
	}
	servers :8442 {
		protocols h1 h2
	}
	servers :8443 {
		protocols h1 h2 h3
	}
}

https://localhost:8441, https://127.0.0.1:8441, https://$IP:8441 {
	tls internal
	root * /root/www
	file_server
}

https://localhost:8442, https://127.0.0.1:8442, https://$IP:8442 {
	tls internal
	root * /root/www
	file_server
}

https://localhost:8443, https://127.0.0.1:8443, https://$IP:8443 {
	tls internal
	root * /root/www
	file_server
}
EOF
caddy stop >/dev/null 2>&1
caddy start --config /root/Caddyfile >/tmp/caddy.log 2>&1
sleep 1
echo "server ip: $IP"
curl -sk -o /dev/null -w "h1 check: %{http_code} http/%{http_version}\n" "https://$IP:8441/manifest.json"
curl -sk -o /dev/null -w "h2 check: %{http_code} http/%{http_version}\n" "https://$IP:8442/manifest.json"
