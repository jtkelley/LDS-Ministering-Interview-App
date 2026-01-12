#!/usr/bin/env python3
"""
Oracle Cloud Deployment Script for Ministering Interviews App

Deploys the application directly with Python (no containers, no git).
Copies files via SFTP - ideal for low-memory VMs where git/dnf get OOM killed.
Reads configuration from oracle_config.yaml with interactive prompts.
"""

import os
import sys
import secrets
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(1)

try:
    import paramiko
except ImportError:
    print("Paramiko not installed. Install with: pip install paramiko")
    sys.exit(1)


CONFIG_FILE = Path(__file__).parent / "oracle_config.yaml"
PROJECT_ROOT = Path(__file__).parent.parent.parent / "app-min"  # Points to app-min folder

# Files to copy to the server (relative to PROJECT_ROOT)
APP_FILES = [
    "app.py",
    "config.py",
    "models.py",
    "requirements.txt",
    "routes_admin.py",
    "routes_api.py",
    "routes_public.py",
    "services.py",
    "shared.py",
]

# Directories to copy (relative to PROJECT_ROOT)
APP_DIRS = [
    "templates",
    "utils",
]

SYSTEMD_SERVICE = """[Unit]
Description=Ministering Interviews Flask App
After=network.target

[Service]
User={user}
WorkingDirectory={app_dir}
Environment="PATH={app_dir}/venv/bin:/usr/local/bin:/usr/bin"
Environment="SECRET_KEY={secret_key}"
Environment="PORT={port}"
ExecStart={app_dir}/venv/bin/gunicorn --bind 0.0.0.0:{port} --workers 2 --timeout 120 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def load_config():
    """Load configuration from YAML file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return yaml.safe_load(f)
    return {}


def save_config(config):
    """Save configuration back to YAML file."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def prompt(message, default="", password=False):
    """Prompt user for input with optional default value."""
    if default:
        display_default = "***" if password and default else default
        prompt_text = f"{message} [{display_default}]: "
    else:
        prompt_text = f"{message}: "

    if password:
        import getpass
        value = getpass.getpass(prompt_text)
    else:
        value = input(prompt_text)

    return value.strip() if value.strip() else default


def prompt_yes_no(message, default=True):
    """Prompt for yes/no with default."""
    default_str = "Y/n" if default else "y/N"
    response = input(f"{message} [{default_str}]: ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes")


def get_config_interactive():
    """Interactively gather configuration with defaults from config file."""
    config = load_config()

    # Ensure nested dicts exist
    config.setdefault("oracle", {})
    config.setdefault("app", {})
    config.setdefault("deploy", {})

    print("\n" + "=" * 60)
    print("Oracle Cloud Deployment Configuration")
    print("=" * 60)
    print("Press Enter to use the default value shown in brackets.\n")

    # Oracle VM settings
    print("-- Oracle Cloud VM Connection --")
    config["oracle"]["vm_ip"] = prompt(
        "VM Public IP address",
        config["oracle"].get("vm_ip", "")
    )

    config["oracle"]["ssh_user"] = prompt(
        "SSH username",
        config["oracle"].get("ssh_user", "opc")
    )

    config["oracle"]["ssh_key_path"] = prompt(
        "SSH private key path",
        config["oracle"].get("ssh_key_path", "")
    )

    # Expand ~ in path
    if config["oracle"]["ssh_key_path"]:
        config["oracle"]["ssh_key_path"] = os.path.expanduser(
            config["oracle"]["ssh_key_path"]
        )

    # App settings
    print("\n-- Application Settings --")
    config["app"]["port"] = int(prompt(
        "Application port",
        str(config["app"].get("port", 80))
    ))

    default_secret = config["app"].get("secret_key", "")
    if not default_secret:
        default_secret = secrets.token_hex(32)
    config["app"]["secret_key"] = prompt(
        "Secret key (auto-generated if empty)",
        default_secret
    )

    config["app"]["app_dir"] = prompt(
        "App directory on server",
        config["app"].get("app_dir", "/home/opc/Ministering-Interviews")
    )

    # Deployment options
    print("\n-- Deployment Options --")
    config["deploy"]["clean_first"] = prompt_yes_no(
        "Clean existing deployment first? (removes venv, old files)",
        config["deploy"].get("clean_first", True)
    )

    config["deploy"]["configure_firewall"] = prompt_yes_no(
        "Configure firewall to open app port?",
        config["deploy"].get("configure_firewall", True)
    )

    config["deploy"]["add_swap"] = prompt_yes_no(
        "Add swap space? (recommended for 1GB RAM)",
        config["deploy"].get("add_swap", True)
    )

    if config["deploy"]["add_swap"]:
        config["deploy"]["swap_size_mb"] = int(prompt(
            "Swap size in MB",
            str(config["deploy"].get("swap_size_mb", 1024))
        ))

    # Save updated config
    print("\n-- Saving Configuration --")
    if prompt_yes_no("Save these settings to config file?", True):
        save_config(config)
        print(f"Configuration saved to {CONFIG_FILE}")

    return config


def create_ssh_client(config):
    """Create and connect SSH client."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    vm_ip = config["oracle"]["vm_ip"]
    ssh_user = config["oracle"]["ssh_user"]
    ssh_key_path = config["oracle"]["ssh_key_path"]

    print(f"\nConnecting to {ssh_user}@{vm_ip}...")

    try:
        client.connect(
            hostname=vm_ip,
            username=ssh_user,
            key_filename=ssh_key_path,
            timeout=30
        )
        print("Connected successfully!")
        return client
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)


def run_command(client, command, description=None, check=True):
    """Run a command via SSH with real-time output streaming."""
    if description:
        print(f"\n>> {description}")
    print(f"   $ {command}")

    # Get the transport and open a channel
    transport = client.get_transport()
    channel = transport.open_session()
    channel.get_pty()  # Request PTY to force unbuffered output
    channel.set_combine_stderr(True)  # Combine stdout and stderr
    channel.exec_command(command)

    output_lines = []
    last_output_time = time.time()
    dots_printed = 0

    # Stream output in real-time
    while True:
        # Check if there's data to read
        if channel.recv_ready():
            data = channel.recv(4096).decode("utf-8", errors="replace")
            if data:
                # Clear dots line if we printed any
                if dots_printed > 0:
                    print()
                    dots_printed = 0
                for line in data.splitlines():
                    print(f"   {line}")
                    output_lines.append(line)
                last_output_time = time.time()

        # Check if the command has finished
        if channel.exit_status_ready():
            # Read any remaining data
            while channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                if data:
                    if dots_printed > 0:
                        print()
                        dots_printed = 0
                    for line in data.splitlines():
                        print(f"   {line}")
                        output_lines.append(line)
            break

        # Print dots every 5 seconds to show it's working
        if time.time() - last_output_time > 5:
            print(".", end="", flush=True)
            dots_printed += 1
            last_output_time = time.time()

        # Small sleep to prevent CPU spinning
        time.sleep(0.1)

    exit_code = channel.recv_exit_status()
    channel.close()

    output = "\n".join(output_lines)

    if check and exit_code != 0:
        print(f"   Command failed with exit code {exit_code}")
        raise RuntimeError(f"Command failed: {command}")

    return output


def configure_firewall(client, port):
    """Open firewall port."""
    run_command(
        client,
        f"sudo firewall-cmd --permanent --add-port={port}/tcp",
        f"Opening port {port} in firewall..."
    )
    run_command(client, "sudo firewall-cmd --reload", "Reloading firewall...")


def add_swap(client, size_mb):
    """Add swap space."""
    # Check if swap already exists
    result = run_command(client, "swapon --show", "Checking existing swap...", check=False)
    if result and result.strip():
        print("   Swap already configured, skipping.")
        return

    print(f"\n>> Creating {size_mb}MB swap file (this may take a minute)...")

    run_command(
        client,
        f"sudo dd if=/dev/zero of=/swapfile bs=1M count={size_mb} status=progress",
        f"Creating {size_mb}MB swap file..."
    )
    run_command(client, "sudo chmod 600 /swapfile", "Setting swap file permissions...")
    run_command(client, "sudo mkswap /swapfile", "Formatting swap...")
    run_command(client, "sudo swapon /swapfile", "Enabling swap...")
    run_command(
        client,
        "grep -q swapfile /etc/fstab || echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab",
        "Adding swap to fstab..."
    )
    run_command(client, "free -h", "Memory status:")


def clean_environment(client, app_dir):
    """Clean out existing deployment - stop service, remove venv and files."""
    print(f"\n>> Cleaning existing deployment at {app_dir}...")

    # Stop the service if running
    run_command(
        client,
        "sudo systemctl stop ministering",
        "Stopping ministering service...",
        check=False
    )

    # Remove the virtual environment
    run_command(
        client,
        f"rm -rf {app_dir}/venv",
        "Removing virtual environment...",
        check=False
    )

    # Remove Python cache files
    run_command(
        client,
        f"find {app_dir} -type d -name '__pycache__' -exec rm -rf {{}} + 2>/dev/null || true",
        "Removing Python cache...",
        check=False
    )

    # Remove all .py files (will be re-uploaded)
    run_command(
        client,
        f"rm -f {app_dir}/*.py",
        "Removing old Python files...",
        check=False
    )

    # Remove templates and utils (will be re-uploaded)
    run_command(
        client,
        f"rm -rf {app_dir}/templates {app_dir}/utils",
        "Removing old templates and utils...",
        check=False
    )

    print("   Cleanup complete!")


def install_dependencies(client):
    """Install Python and system dependencies."""
    # Check Python version
    run_command(client, "python3 --version", "Checking Python version...")

    # Check if pip is already installed
    result = run_command(
        client,
        "python3 -m pip --version",
        "Checking if pip is installed...",
        check=False
    )

    if "pip" in result.lower():
        print("   pip is already installed, skipping.")
    else:
        # Install pip using curl (dnf gets OOM killed on low-memory VMs)
        print("   pip not found, installing via curl...")
        run_command(
            client,
            "curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py",
            "Downloading get-pip.py..."
        )
        run_command(
            client,
            "python3 /tmp/get-pip.py --user",
            "Installing pip..."
        )
        run_command(
            client,
            "rm /tmp/get-pip.py",
            "Cleaning up...",
            check=False
        )


def upload_files(client, app_dir):
    """Upload application files via SFTP."""
    print(f"\n>> Uploading application files to {app_dir}...")

    sftp = client.open_sftp()

    try:
        # Create app directory if it doesn't exist
        try:
            sftp.stat(app_dir)
        except FileNotFoundError:
            print(f"   Creating directory {app_dir}")
            sftp.mkdir(app_dir)

        # Upload individual files
        for filename in APP_FILES:
            local_path = PROJECT_ROOT / filename
            remote_path = f"{app_dir}/{filename}"

            if local_path.exists():
                print(f"   Uploading {filename}...")
                sftp.put(str(local_path), remote_path)
            else:
                print(f"   Warning: {filename} not found locally, skipping")

        # Upload directories
        for dirname in APP_DIRS:
            local_dir = PROJECT_ROOT / dirname
            remote_dir = f"{app_dir}/{dirname}"

            if local_dir.exists() and local_dir.is_dir():
                # Create remote directory
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    print(f"   Creating directory {dirname}/")
                    sftp.mkdir(remote_dir)

                # Upload all files in directory
                for item in local_dir.iterdir():
                    if item.is_file():
                        remote_file = f"{remote_dir}/{item.name}"
                        print(f"   Uploading {dirname}/{item.name}...")
                        sftp.put(str(item), remote_file)
                    elif item.is_dir():
                        # Handle subdirectories (one level deep)
                        sub_remote_dir = f"{remote_dir}/{item.name}"
                        try:
                            sftp.stat(sub_remote_dir)
                        except FileNotFoundError:
                            sftp.mkdir(sub_remote_dir)
                        for subitem in item.iterdir():
                            if subitem.is_file():
                                print(f"   Uploading {dirname}/{item.name}/{subitem.name}...")
                                sftp.put(str(subitem), f"{sub_remote_dir}/{subitem.name}")

        print("   File upload complete!")

    finally:
        sftp.close()


def deploy_app(client, config):
    """Deploy the application."""
    app_dir = config["app"]["app_dir"]
    port = config["app"]["port"]
    secret_key = config["app"]["secret_key"]
    user = config["oracle"]["ssh_user"]

    # Upload files via SFTP
    upload_files(client, app_dir)

    # Create virtual environment
    run_command(
        client,
        f"cd {app_dir} && python3 -m venv venv",
        "Creating virtual environment..."
    )

    # Install requirements
    run_command(
        client,
        f"cd {app_dir} && ./venv/bin/pip install --upgrade pip",
        "Upgrading pip..."
    )
    run_command(
        client,
        f"cd {app_dir} && ./venv/bin/pip install -r requirements.txt",
        "Installing Python dependencies..."
    )

    # Install gunicorn if not in requirements
    run_command(
        client,
        f"cd {app_dir} && ./venv/bin/pip install gunicorn",
        "Installing gunicorn..."
    )

    # Fix permissions on venv binaries (needed for systemd to execute)
    run_command(
        client,
        f"chmod +x {app_dir}/venv/bin/*",
        "Setting executable permissions on venv binaries..."
    )

    # Ensure opc owns everything
    run_command(
        client,
        f"sudo chown -R {user}:{user} {app_dir}",
        "Setting ownership..."
    )

    # Grant Python capability to bind to privileged ports (needed for port 80)
    run_command(
        client,
        "sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.9",
        "Granting Python capability to bind to port 80...",
        check=False  # Don't fail if Python version differs
    )

    # Create instance directory
    run_command(client, f"mkdir -p {app_dir}/instance", "Creating instance directory...")

    # Create systemd service file
    service_content = SYSTEMD_SERVICE.format(
        user=user,
        app_dir=app_dir,
        secret_key=secret_key,
        port=port
    )

    # Write service file (escape for shell)
    escaped_content = service_content.replace("'", "'\\''")
    run_command(
        client,
        f"echo '{escaped_content}' | sudo tee /etc/systemd/system/ministering.service > /dev/null",
        "Creating systemd service file..."
    )

    # Reload systemd and start service
    run_command(client, "sudo systemctl daemon-reload", "Reloading systemd...")
    run_command(client, "sudo systemctl enable ministering", "Enabling service on boot...")
    run_command(client, "sudo systemctl restart ministering", "Starting application...")

    # Check status
    run_command(client, "sudo systemctl status ministering --no-pager", "Service status:")


def quick_deploy(client, config):
    """Quick deploy - just upload files and restart service."""
    app_dir = config["app"]["app_dir"]

    print("\n" + "=" * 60)
    print("  Quick Deploy - Upload files and restart")
    print("=" * 60)

    # Upload files via SFTP
    upload_files(client, app_dir)

    # Restart service
    run_command(client, "sudo systemctl restart ministering", "Restarting application...")

    # Check status
    run_command(client, "sudo systemctl status ministering --no-pager", "Service status:")

    print("\n" + "=" * 60)
    print("  Quick Deploy Complete!")
    print("=" * 60)
    print(f"\nYour app should be available at:")
    print(f"  http://{config['oracle']['vm_ip']}")
    print()


def main():
    """Main deployment function."""
    print("\n" + "=" * 60)
    print("  Ministering Interviews - Oracle Cloud Deployment")
    print("  (Minimal version - no scraping, no SMS)")
    print("  (Direct SFTP upload - no git, no containers)")
    print("=" * 60)

    # Check for existing config for quick deploy option
    config = load_config()
    quick_mode = False

    if config.get("oracle", {}).get("vm_ip") and config.get("oracle", {}).get("ssh_key_path"):
        print(f"\nExisting config found for: {config['oracle'].get('vm_ip')}")
        print("\nDeploy options:")
        print("  1. Quick deploy (upload files + restart only)")
        print("  2. Full deploy (clean, setup venv, install deps, etc.)")
        print("  3. Reconfigure settings")

        choice = input("\nSelect option [1]: ").strip() or "1"

        if choice == "1":
            quick_mode = True
        elif choice == "3":
            config = get_config_interactive()
        # else choice == "2", do full deploy with existing config
    else:
        # No existing config, go through interactive setup
        config = get_config_interactive()

    # Validate required fields
    if not config.get("oracle", {}).get("vm_ip"):
        print("\nError: VM IP address is required.")
        sys.exit(1)

    if not config.get("oracle", {}).get("ssh_key_path"):
        print("\nError: SSH key path is required.")
        sys.exit(1)

    ssh_key_path = os.path.expanduser(config["oracle"]["ssh_key_path"])
    if not os.path.exists(ssh_key_path):
        print(f"\nError: SSH key not found at {ssh_key_path}")
        sys.exit(1)
    config["oracle"]["ssh_key_path"] = ssh_key_path

    # Connect via SSH
    client = create_ssh_client(config)

    try:
        if quick_mode:
            # Quick deploy - just upload and restart
            quick_deploy(client, config)
        else:
            # Full deploy
            # Confirm deployment
            print("\n" + "=" * 60)
            print("Ready for FULL deploy with the following settings:")
            print(f"  VM: {config['oracle']['ssh_user']}@{config['oracle']['vm_ip']}")
            print(f"  Source: {PROJECT_ROOT} (app-min)")
            print(f"  Remote dir: {config['app']['app_dir']}")
            print(f"  Port: {config['app']['port']}")
            print(f"  Clean first: {config['deploy'].get('clean_first', True)}")
            print("=" * 60)

            if not prompt_yes_no("\nProceed with full deployment?", True):
                print("Deployment cancelled.")
                sys.exit(0)

            # Clean existing deployment if requested
            if config["deploy"].get("clean_first", True):
                clean_environment(client, config["app"]["app_dir"])

            # Add swap first (helps with memory during installs)
            if config["deploy"].get("add_swap"):
                add_swap(client, config["deploy"]["swap_size_mb"])

            # Install system dependencies
            install_dependencies(client)

            # Configure firewall
            if config["deploy"].get("configure_firewall"):
                configure_firewall(client, config["app"]["port"])

            # Deploy the app
            deploy_app(client, config)

            # Final message
            print("\n" + "=" * 60)
            print("  Deployment Complete!")
            print("=" * 60)
            print(f"\nYour app should be available at:")
            print(f"  http://{config['oracle']['vm_ip']}")
            print(f"\nUseful commands (SSH into server first):")
            print(f"  sudo systemctl status ministering   # Check status")
            print(f"  sudo systemctl restart ministering  # Restart app")
            print(f"  sudo journalctl -u ministering -f   # View logs")
            print()

    except RuntimeError as e:
        print(f"\n{'=' * 60}")
        print(f"  Deployment FAILED!")
        print(f"{'=' * 60}")
        print(f"\nError: {e}")
        print("\nThis may be due to:")
        print("  - SSH connection dropped (exit code -1)")
        print("  - Server ran out of memory")
        print("  - Network timeout")
        print("\nTry: Reboot the VM and run the script again.")
        sys.exit(1)

    finally:
        client.close()


if __name__ == "__main__":
    main()
