import os
import subprocess
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define common variables
ip_address = "0.0.0.0" # listens on everything by default
subsystem_prefix = "mckenna-" # Helps identify drives on remote system and will include drive label if it exists
port_number = 4420
transport_type = "tcp"
address_family = "ipv4"

# List NVMe drives (by-uuid)
nvme_drives = [
    "a52c88ab-41e1-4c3a-9e0c-a276b4146b1e",
    "cafd9e45-177a-4b28-8fc9-a1872871182b"
]

# Load necessary kernel modules
logging.info("Loading kernel modules...")
subprocess.run(["sudo", "modprobe", "nvme_tcp"], check=True)
subprocess.run(["sudo", "modprobe", "nvmet"], check=True)
subprocess.run(["sudo", "modprobe", "nvmet-tcp"], check=True)

# Function to clean up existing NVMe configuration
def cleanup_nvme_configuration():
    logging.info("Cleaning up existing NVMe configuration...")
    port_path = f"/sys/kernel/config/nvmet/ports/1"
    if os.path.exists(port_path):
        logging.info(f"Removing port configuration at {port_path}...")
        try:
            subprocess.run(["sudo", "sh", "-c", f"find {port_path} -type f -delete"], check=True)
            subprocess.run(["sudo", "rmdir", port_path], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to remove port configuration at {port_path}: {e}")

    for i in range(len(nvme_drives)):
        subsystem_path = f"/sys/kernel/config/nvmet/subsystems/{subsystem_prefix}{i+1:02d}"
        if os.path.exists(subsystem_path):
            logging.info(f"Removing subsystem configuration at {subsystem_path}...")
            try:
                # Unbind namespaces
                namespaces_path = f"{subsystem_path}/namespaces"
                if os.path.exists(namespaces_path):
                    for ns in os.listdir(namespaces_path):
                        ns_path = os.path.join(namespaces_path, ns)
                        subprocess.run(["sudo", "rmdir", ns_path], check=True)
                subprocess.run(["sudo", "rmdir", subsystem_path], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to remove subsystem configuration at {subsystem_path}: {e}")

# Cleanup any existing NVMe configuration
cleanup_nvme_configuration()

def create_file_with_content(path, content):
    try:
        with open(path, 'w') as f:
            f.write(content)
        logging.info(f"Wrote to file {path}")
    except Exception as e:
        logging.error(f"Failed to write to {path}: {e}")

def get_drive_label(uuid):
    try:
        result = subprocess.run(["lsblk", "-no", "LABEL", f"/dev/disk/by-uuid/{uuid}"], check=True, capture_output=True, text=True)
        label = result.stdout.strip()
        if label:
            return label
        else:
            return None
    except subprocess.CalledProcessError:
        return None

try:
    # Configure the NVMe-oF TCP port
    port_path = f"/sys/kernel/config/nvmet/ports/1"
    logging.info(f"Creating NVMe-oF TCP port 1 on port {port_number}...")
    os.makedirs(port_path, exist_ok=True)
    logging.info(f"Created directory {port_path}")

    create_file_with_content(f"{port_path}/addr_traddr", ip_address)
    create_file_with_content(f"{port_path}/addr_trtype", transport_type)
    create_file_with_content(f"{port_path}/addr_trsvcid", str(port_number))
    create_file_with_content(f"{port_path}/addr_adrfam", address_family)

    for i, uuid in enumerate(nvme_drives, start=1):
        label = get_drive_label(uuid)
        if label:
            subsystem_name = f"{subsystem_prefix}{label}"
        else:
            subsystem_name = f"{subsystem_prefix}{i:02d}"
        
        subsystem_path = f"/sys/kernel/config/nvmet/subsystems/{subsystem_name}"

        # Create the NVMe subsystem directory
        logging.info(f"Creating NVMe subsystem directory for {subsystem_name}...")
        os.makedirs(subsystem_path, exist_ok=True)
        logging.info(f"Created directory {subsystem_path}")

        # Set the subsystem to accept any host
        logging.info(f"Setting attr_allow_any_host for {subsystem_name}...")
        create_file_with_content(f"{subsystem_path}/attr_allow_any_host", '1')

        namespace_path = f"{subsystem_path}/namespaces/1"

        # Create and configure the namespace
        logging.info(f"Creating and configuring namespace 1 for {subsystem_name}...")
        os.makedirs(namespace_path, exist_ok=True)
        logging.info(f"Created directory {namespace_path}")

        create_file_with_content(f"{namespace_path}/device_path", f"/dev/disk/by-uuid/{uuid}")

        # Manually create the enable file and write to it
        enable_file_path = f"{namespace_path}/enable"
        retry_count = 0
        max_retries = 10
        while retry_count < max_retries:
            try:
                with open(enable_file_path, 'w') as f:
                    f.write('1')
                logging.info(f"Wrote to file {enable_file_path}")
                break
            except FileNotFoundError:
                logging.warning(f"{enable_file_path} not found, retrying...")
                time.sleep(1)
                retry_count += 1

        if retry_count == max_retries:
            logging.error(f"Failed to write to {enable_file_path} after multiple attempts")

        # Link the subsystem to the port
        logging.info(f"Linking subsystem {subsystem_name} to port 1...")
        symlink_path = f"{port_path}/subsystems/{subsystem_name}"
        if not os.path.exists(symlink_path):
            os.symlink(subsystem_path, symlink_path)
            logging.info(f"Linked {subsystem_path} to {symlink_path}")
        else:
            logging.warning(f"Symlink {symlink_path} already exists")

except Exception as e:
    logging.error(f"An error occurred: {e}")

logging.info("NVMe configuration completed.")
