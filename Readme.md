# SSH GPU Monitor 🖥️ 
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A fast, asynchronous GPU monitoring tool that provides real-time status of NVIDIA GPUs across multiple machines through SSH, with support for jump hosts and per-machine credentials.

![Example Output](example_running.png)

## ✨ Features

- **Real-time Monitoring**: Live updates of GPU status across multiple machines
- **Asynchronous Operation**: Fast, non-blocking checks using `asyncio` and `asyncssh`
- **Jump Host Support**: Access machines behind a bastion/jump host
- **Rich Display**: Beautiful terminal UI using the `rich` library
- **Flexible Configuration**: 
  - YAML-based configuration
  - Per-machine SSH credentials
  - Pattern-based target generation
- **Robust Error Handling**: Graceful handling of network issues and timeouts

## 🚀 Installation & Usage

### Install from PyPI
```bash
pip install ssh-gpu-monitor
```

### Run the Monitor
After installation, you can run the monitor in several ways:

```bash
# Run using the command-line tool
ssh-gpu-monitor

# Or run as a Python module
python -m ssh_gpu_monitor

# Use a custom config file
ssh-gpu-monitor --config /path/to/your/config.yaml

# Get the default config path
ssh-gpu-monitor --get_config_path
```

### Configuration
1. Get the default config path:
```bash
ssh-gpu-monitor --get_config_path
```

2. Either:
   - Copy the default config to your preferred location and use `--config` to specify it
   - Modify the default config directly

Example config file:
```yaml
ssh:
  username: "your_username"
  key_path: "~/.ssh/id_rsa"
  jump_host: "jump.example.com"
  timeout: 10

targets:
  individual:
    - "gpu-server1"
    - "gpu-server2"

display:
  refresh_rate: 5
```

## 📖 Configuration

### Basic Structure
```yaml
ssh:
  username: "default_user"  # Default username
  key_path: "~/.ssh/id_rsa"  # Default SSH key
  jump_host: "jump.example.com"
  timeout: 10  # seconds

targets:
  # Individual machines
  individual:
    - host: "gpu-server1"
      username: "different_user"  # Optional override
      key_path: "~/.ssh/special_key"  # Optional override
    - "gpu-server2"  # Uses default credentials
  
  # Pattern-based groups
  patterns:
    - prefix: "gpu"
      start: 1
      end: 30
      format: "{prefix}{number:02}"  # Results in gpu01, gpu02, etc.
      username: "gpu_user"  # Optional override
      key_path: "~/.ssh/gpu_key"  # Optional override

display:
  refresh_rate: 5  # seconds

debug:
  enabled: false
  log_dir: "logs"
  log_file: "gpu_checker.log"
  log_max_size: 1048576  # 1MB
  log_backup_count: 3
```

### Command Line Options
Override any configuration option via command line:
```bash
# Enable debug logging
python main.py --debug.enabled

# Override SSH settings
python main.py --ssh.username=other_user --ssh.key_path=~/.ssh/other_key

# Check specific targets
python main.py --targets gpu01 gpu02 special-server
```

## 🔧 Advanced Usage

### Custom Target Patterns
Generate targets using patterns:
```yaml
patterns:
  - prefix: "compute"
    start: 1
    end: 100
    format: "{prefix}-{number:03d}"  # compute-001, compute-002, etc.
```

### Per-Machine Credentials
Specify different credentials for specific machines:
```yaml
individual:
  - host: "special-gpu"
    username: "admin"
    key_path: "~/.ssh/admin_key"
```

### Debug Logging
Enable detailed logging for troubleshooting:
```yaml
debug:
  enabled: true
  log_dir: "logs"
  log_file: "debug.log"
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

### Original Contributors
Originally created as "some awful, brittle code to check GPU status of multiple machines at a given host address through an SSH jumpnode."

Special thanks to:
- @harrygcoppock and @minut1bc for their PRs on v1
- [gpuobserver](https://github.com/pawni/gpuobserver) for earlier code concepts
- [Stack Overflow answer](https://stackoverflow.com/a/36096801/7565759) for SSH connection handling insights

### Libraries
- [Rich](https://github.com/Textualize/rich) for the beautiful terminal interface
- [asyncssh](https://github.com/ronf/asyncssh) for async SSH support
- [PyYAML](https://pyyaml.org/) for configuration management

## 🔍 Similar Projects

- [nvidia-smi-tools](https://github.com/example/nvidia-smi-tools)
- [gpu-monitor](https://github.com/example/gpu-monitor)

## ⚠️ Known Issues

- SSH connection might timeout on very slow networks
- Some older NVIDIA drivers might return incompatible XML formats

## 📊 Roadmap

- [ ] Add support for AMD GPUs
- [ ] Implement process name filtering
- [ ] Add web interface
- [ ] Support for custom SSH config files
