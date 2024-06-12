# nvme_tcp_thingy
Take list of drive UUIDs and auto configure the NVME/tcp system -- also includes Drive Label if it exists to aid in identifying it on the remote system

Save file and run with: `python nvme-tcp_thingy.py` (you may need to use `python3 nvme_tcp_thingy.py`)

This will allow the drives to be shared.

On the remote system use: 
  `sudo nvme discover -t tcp -a <IP> -s 4420` to view shares
  `sudo nvme connect-all -t tcp -a <IP> -s 4420` to connect to all shares on that system

On the remote systems, you can also run `nvme list -v` to view more info about the drives it is connected to. It'll show you what /dev/device you will need to mount.


