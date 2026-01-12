#!/usr/bin/env python3
"""
Oracle Cloud Deployment Script for Ministering Interviews App

Deploys the application to an Oracle Cloud VM using SSH.
Uses Podman (lightweight, pre-installed on Oracle Linux) instead of Docker.
Reads configuration from oracle_config.yaml with interactive prompts.
"""

import os
import sys
import secrets
import time
import select
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
    config.setdefault("git", {})
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

    # Git settings
    print("\n-- Git Repository --")
    config["git"]["repo_url"] = prompt(
        "Git repository URL",
        config["git"].get("repo_url", "https://github.com/YOUR_USERNAME/Ministering-Interviews.git")
    )

    config["git"]["branch"] = prompt(
        "Branch to deploy",
        config["git"].get("branch", "main")
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
    config["deploy"]["install_podman"] = prompt_yes_no(
        "Install Podman if not present?",
        config["deploy"].get("install_podman", True)
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
    channel.set_combine_stderr(True)  # Combine stdout and stderr
    channel.exec_command(command)

    output_lines = []

    # Stream output in real-time
    while True:
        # Check if there's data to read
        if channel.recv_ready():
            data = channel.recv(4096).decode("utf-8", errors="replace")
            if data:
                for line in data.splitlines():
                    print(f"   {line}")
                    output_lines.append(line)

        # Check if the command has finished
        if channel.exit_status_ready():
            # Read any remaining data
            while channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                if data:
                    for line in data.splitlines():
                        print(f"   {line}")
                        output_lines.append(line)
            break

        # Small sleep to prevent CPU spinning
        time.sleep(0.1)

    exit_code = channel.recv_exit_status()
    channel.close()

    output = "\n".join(output_lines)

    if check and exit_code != 0:
        print(f"   Command failed with exit code {exit_code}")
        return None

    return output


def check_podman_installed(client):
    """Check if Podman is installed."""
    result = run_command(client, "which podman 2>/dev/null", "Checking for Podman...", check=False)
    return result is not None and "podman" in result


def install_podman(client):
    """Install Podman on Oracle Linux using dnf."""
    print("\n>> Installing Podman (this may take a few minutes)...")

    # Install podman
    run_command(client, "sudo dnf install -y podman", "Installing Podman...")

    # Install podman-compose (try dnf first, fall back to pip)
    run_command(
        client,
        "sudo dnf install -y podman-compose 2>/dev/null || sudo pip3 install podman-compose",
        "Installing podman-compose..."
    )

    # Verify installation
    run_command(client, "podman --version", "Verifying Podman installation...")
    run_command(client, "podman-compose --version 2>/dev/null || echo 'podman-compose installed'", check=False)


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


def deploy_app(client, config):
    """Deploy the application."""
    app_dir = config["app"]["app_dir"]
    repo_url = config["git"]["repo_url"]
    branch = config["git"]["branch"]
    port = config["app"]["port"]
    secret_key = config["app"]["secret_key"]

    # Check if app directory exists
    result = run_command(client, f"test -d {app_dir} && echo 'exists'", "Checking if app exists...", check=False)

    if result and "exists" in result:
        # Update existing deployment
        print("\nApp directory exists. Updating...")
        run_command(client, f"cd {app_dir} && git fetch origin", "Fetching updates...")
        run_command(client, f"cd {app_dir} && git checkout {branch}", f"Checking out {branch}...")
        run_command(client, f"cd {app_dir} && git pull origin {branch}", "Pulling latest changes...")
    else:
        # Fresh clone
        run_command(client, f"git clone -b {branch} {repo_url} {app_dir}", "Cloning repository...")

    # Create .env file
    run_command(
        client,
        f"echo 'SECRET_KEY={secret_key}' > {app_dir}/.env && echo 'PORT={port}' >> {app_dir}/.env",
        "Creating .env file..."
    )

    # Create instance directory
    run_command(client, f"mkdir -p {app_dir}/instance", "Creating instance directory...")

    # Build and start with Podman Compose
    print("\n>> Building and starting containers (this may take several minutes)...")
    run_command(
        client,
        f"cd {app_dir} && podman-compose down 2>/dev/null; podman-compose up -d --build",
        "Building and starting Podman containers..."
    )

    # Show status
    run_command(
        client,
        f"cd {app_dir} && podman-compose ps",
        "Container status:"
    )


def main():
    """Main deployment function."""
    print("\n" + "=" * 60)
    print("  Ministering Interviews - Oracle Cloud Deployment")
    print("  (Using Podman - lightweight container runtime)")
    print("=" * 60)

    # Get configuration
    config = get_config_interactive()

    # Validate required fields
    if not config["oracle"]["vm_ip"]:
        print("\nError: VM IP address is required.")
        sys.exit(1)

    if not config["oracle"]["ssh_key_path"]:
        print("\nError: SSH key path is required.")
        sys.exit(1)

    if not os.path.exists(config["oracle"]["ssh_key_path"]):
        print(f"\nError: SSH key not found at {config['oracle']['ssh_key_path']}")
        sys.exit(1)

    # Confirm deployment
    print("\n" + "=" * 60)
    print("Ready to deploy with the following settings:")
    print(f"  VM: {config['oracle']['ssh_user']}@{config['oracle']['vm_ip']}")
    print(f"  Repo: {config['git']['repo_url']} ({config['git']['branch']})")
    print(f"  Port: {config['app']['port']}")
    print("=" * 60)

    if not prompt_yes_no("\nProceed with deployment?", True):
        print("Deployment cancelled.")
        sys.exit(0)

    # Connect via SSH
    client = create_ssh_client(config)

    try:
        # Add swap first (helps with memory during installs)
        if config["deploy"]["add_swap"]:
            add_swap(client, config["deploy"]["swap_size_mb"])

        # Install Podman if needed
        if config["deploy"]["install_podman"]:
            if not check_podman_installed(client):
                install_podman(client)
            else:
                print("\nPodman already installed.")
                # Still ensure podman-compose is installed
                run_command(
                    client,
                    "which podman-compose 2>/dev/null || sudo dnf install -y podman-compose 2>/dev/null || sudo pip3 install podman-compose",
                    "Ensuring podman-compose is installed...",
                    check=False
                )

        # Configure firewall
        if config["deploy"]["configure_firewall"]:
            configure_firewall(client, config["app"]["port"])

        # Deploy the app
        deploy_app(client, config)

        # Final message
        print("\n" + "=" * 60)
        print("  Deployment Complete!")
        print("=" * 60)
        print(f"\nYour app should be available at:")
        print(f"  http://{config['oracle']['vm_ip']}")
        print(f"\nTo view logs, SSH in and run:")
        print(f"  cd {config['app']['app_dir']} && podman-compose logs -f")
        print()

    finally:
        client.close()


if __name__ == "__main__":
    main()
