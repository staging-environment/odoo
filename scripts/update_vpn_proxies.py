import subprocess

script_content = """#!/bin/bash
trap "kill 0" SIGINT SIGTERM EXIT

socat TCP4-LISTEN:33062,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33234 &
socat TCP4-LISTEN:54320,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33346 &
socat TCP4-LISTEN:33063,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33311 &
socat TCP4-LISTEN:33064,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33328 &
socat TCP4-LISTEN:33065,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33065 &
socat TCP4-LISTEN:33066,bind=10.8.0.1,fork,reuseaddr TCP4:127.0.0.1:33206 &

wait
"""

p = subprocess.Popen(["ssh", "utrecar-dev", "sudo tee /usr/local/bin/vpn-db-proxies.sh > /dev/null && sudo chmod +x /usr/local/bin/vpn-db-proxies.sh && sudo systemctl restart vpn-db-proxies.service"], stdin=subprocess.PIPE, text=True)
p.communicate(input=script_content)

res = subprocess.run(["ssh", "utrecar-dev", "sudo systemctl status vpn-db-proxies.service"], capture_output=True, text=True)
print(res.stdout)
