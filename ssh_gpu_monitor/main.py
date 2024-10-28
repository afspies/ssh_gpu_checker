"""This module is used to check GPU machines information asynchronously."""

import asyncio
import os
from typing import NamedTuple, Dict, List, Optional, Any
import xml.etree.ElementTree as ET
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
from rich.live import Live
from rich.console import Console
import signal
from pathlib import Path

# Add these imports at the top
import asyncssh
from .src.table_display import GPUTable
from .src.config_loader import generate_targets, Target

class GPUInfo(NamedTuple):
    """A class for representing a GPU machine's information."""

    model: str
    num_procs: int
    gpu_util: str
    used_mem: str
    total_mem: str

    def __str__(self) -> str:
        return (
            f'{self.model:26} | '
            f'Free: {self.num_procs == 0!s:5} | '
            f'Num Procs: {self.num_procs:2d} | '
            f'GPU Util: {self.gpu_util:>3} % | '
            f'Memory: {self.used_mem:>5} / {self.total_mem:>5} MiB'
        )

class AsyncGPUChecker:
    """A class for asynchronously checking GPU machines."""

    def __init__(self, targets: List[Target]) -> None:
        self.targets = targets
        self.proc_filter = re.compile(r'.*')
        self.gpu_table = GPUTable()
        self.connections = {}
        self.jump_conn = None
        self.console = Console()
        self.running = True

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\nShutting down gracefully...")
        self.gpu_table.show_goodbye()  # Show goodbye message
        self.running = False
        
    async def open_connection(self, target: Target):
        """Modified connection method with better error handling"""
        logging.debug(f"Attempting to open connection to {target.host}")
        try:
            # Set up port forwarding
            listener = await asyncio.wait_for(
                self.jump_conn.forward_local_port('', 0, target.host, 22),
                timeout=SSH_TIMEOUT/2
            )
            tunnel_port = listener.get_port()
            
            # Expand the key path
            key_path = os.path.expanduser(target.key_path)
            
            # Attempt SSH connection using target-specific username and key
            conn = await asyncio.wait_for(
                asyncssh.connect(
                    'localhost', 
                    port=tunnel_port,
                    username=target.username,
                    client_keys=[key_path],  # Use target-specific key
                    known_hosts=None,
                    keepalive_interval=30,
                    keepalive_count_max=5
                ),
                timeout=SSH_TIMEOUT/2
            )
            
            self.connections[target.host] = conn
            logging.debug(f"Successfully connected to {target.host}")
            return {target.host: "Connected"}
            
        except asyncio.TimeoutError:
            logging.debug(f"Timeout connecting to {target.host}")
            return {target.host: "Connection timeout"}
        except Exception as exc:
            logging.debug(f"Error connecting to {target.host}: {str(exc)}")
            return {target.host: f"Connection error: {str(exc)}"}

    async def check_single_target(self, target: Target) -> Dict[str, str]:
        """Check a single GPU target using an existing connection."""
        logging.debug(f"Checking target: {target.host}")
        try:
            conn = self.connections.get(target.host)
            if not conn:
                logging.debug(f"No connection for target: {target.host}")
                return {target.host: "No connection"}
            
            logging.debug(f"Running nvidia-smi command on {target.host}")
            result = await asyncio.wait_for(
                conn.run('nvidia-smi -q -x', check=True),
                timeout=SSH_TIMEOUT
            )
            if result.exit_status != 0:
                logging.error(f"Command failed on {target.host} with status {result.exit_status}")
                return {target.host: f"Command failed: {result.stderr}"}
            
            # Ensure we're working with a string
            output = result.stdout
            if isinstance(output, bytes):
                output = output.decode('utf-8')
            
            logging.debug(f"Received result from {target.host}, parsing GPU info")
            return {target.host: self.parse_gpu_info(target.host, output)}
        except asyncio.TimeoutError:
            logging.debug(f"Timeout while querying {target.host}")
            return {target.host: "Timeout"}
        except asyncssh.Error as exc:
            logging.debug(f"SSH Error for {target.host}: {str(exc)}")
            return {target.host: f"SSH Error: {str(exc)}"}
        except Exception as exc:
            logging.debug(f"Unexpected error for {target.host}: {str(exc)}")
            logging.debug(f"Exception details for {target.host}:", exc_info=True)
            return {target.host: f"Unexpected error: {str(exc)}"}

    def parse_gpu_info(self, machine_name: str, xml_output: str) -> str:
        """Parse the GPU info from XML output."""
        try:
            # Ensure xml_output is a string
            if isinstance(xml_output, bytes):
                xml_output = xml_output.decode('utf-8')
            root = ET.fromstring(xml_output)

            gpu_infos = []
            for gpu in root.findall('gpu'):
                try:
                    model = gpu.find('product_name').text
                    processes = gpu.find('processes')
                    
                    # More robust process counting
                    num_procs = 0
                    if processes is not None:
                        for process in processes.findall('process_info'):
                            proc_name = process.find('process_name')
                            if proc_name is not None and proc_name.text is not None:
                                if self.proc_filter.search(proc_name.text):
                                    num_procs += 1
                    
                    gpu_util = gpu.find('utilization').find('gpu_util').text.removesuffix(' %')
                    memory_usage = gpu.find('fb_memory_usage')
                    used_mem = memory_usage.find('used').text.removesuffix(' MiB')
                    total_mem = memory_usage.find('total').text.removesuffix(' MiB')
                    
                    gpu_infos.append(GPUInfo(model, num_procs, gpu_util, used_mem, total_mem))
                except AttributeError as e:
                    logging.error(f"Error parsing GPU info for {machine_name}: {str(e)}")
                    return f"Error parsing GPU info: {str(e)}"

            # Join multiple GPU infos with newlines
            return '\n'.join(map(str, gpu_infos))
        except ET.ParseError as e:
            logging.error(f"XML parse error for {machine_name}: {str(e)}")
            return f"XML parse error: {str(e)}"
        except Exception as e:
            logging.error(f"Unexpected error parsing GPU info for {machine_name}: {str(e)}")
            return f"Parse error: {str(e)}"

    async def run(self) -> None:
        """Run the main loop of the GPU checker asynchronously."""
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print('\n-------------------------------------------------\n')
        logging.info("Starting GPU checker")
        try:
            # Initialize table with "Connecting" status
            initial_data = {target.host: "Connecting" for target in self.targets}  # Changed this line
            self.gpu_table.update_table(initial_data)

            # Create live display
            with Live(self.gpu_table.table, console=self.console, refresh_per_second=4) as live:
                # Open jump host connection
                logging.info("Connecting to jump host")
                self.jump_conn = await asyncssh.connect(
                    JUMP_SHELL, 
                    username=USERNAME, 
                    client_keys=[SSH_KEY_PATH],
                    keepalive_interval=30,  # Add keepalive to prevent timeouts
                    keepalive_count_max=5
                )
                logging.info("Connected to jump host")

                # Open connections to GPU servers
                logging.info("Starting to open connections to GPU servers")
                connection_tasks = [self.open_connection(target) for target in self.targets]
                connection_results = await asyncio.gather(*connection_tasks, return_exceptions=True)
                
                # Process connection results
                for result in connection_results:
                    if isinstance(result, dict):
                        self.gpu_table.update_table(result)
                    else:
                        logging.debug(f"Connection error: {str(result)}")
                
                live.update(self.gpu_table.table)
                logging.info("Finished opening connections to GPU servers")

                # Main loop
                logging.info("Entering main loop to query GPUs")
                while self.running:
                    try:
                        logging.debug("Starting a new round of GPU queries")
                        tasks = [self.check_single_target(target) for target in self.targets]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Process results
                        data = {}
                        for result in results:
                            if isinstance(result, dict):
                                data.update(result)
                            else:
                                logging.error(f"Query error: {str(result)}")
                        
                        # Update display
                        self.gpu_table.update_table(data)
                        live.update(self.gpu_table.table)
                        
                        # Wait before next update
                        await asyncio.sleep(REFRESH_RATE)
                        
                    except Exception as e:
                        logging.error(f"Error in main loop: {str(e)}")
                        await asyncio.sleep(1)  # Brief pause before retrying

        except Exception as exc:
            logging.error(f"An unexpected error occurred: {str(exc)}")
            logging.debug("Exception details:", exc_info=True)
            print(f"An unexpected error occurred: {str(exc)}", file=sys.stderr)
            
        finally:
            # Cleanup
            logging.info("Closing connections")
            for conn in self.connections.values():
                try:
                    conn.close()
                except:
                    pass
            if self.jump_conn:
                try:
                    self.jump_conn.close()
                except:
                    pass
            logging.info("GPU checker stopped")

def setup_logging(config: Dict) -> None:
    """Set up logging configuration based on debug config"""
    # Suppress all loggers initially
    logging.getLogger().setLevel(logging.CRITICAL)
    asyncssh_logger = logging.getLogger('asyncssh')
    asyncssh_logger.setLevel(logging.CRITICAL)

    if not config['debug']['enabled']:
        return

    log_dir = Path(config['debug']['log_dir'])
    log_dir.mkdir(exist_ok=True)
    
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = log_dir / config['debug']['log_file']
    
    with open(log_file, 'w') as f:
        f.write('')
    
    log_handler = RotatingFileHandler(
        log_file, 
        maxBytes=config['debug']['log_max_size'], 
        backupCount=config['debug']['log_backup_count']
    )
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.DEBUG)
    
    # Only add file handler if debug is enabled
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)

async def main(config: Dict[str, Any]) -> None:
    """Main function for running GPU checker."""
    # Remove config loading since it's now passed in
    setup_logging(config)
    
    # Expand SSH key path
    config['ssh']['key_path'] = os.path.expanduser(config['ssh']['key_path'])
    
    if config['debug']['enabled']:
        logging.info("GPU checker started in debug mode")
    
    if not os.path.exists(config['ssh']['key_path']):
        if config['debug']['enabled']:
            logging.error(f'SSH key not found at {config["ssh"]["key_path"]}')
        print('SSH key not found. Please check the provided path.')
        return

    # Generate target list
    targets = generate_targets(config)
    
    if config['debug']['enabled']:
        logging.info(f"Generated targets: {targets}")

    # Update global constants
    global USERNAME, SSH_KEY_PATH, JUMP_SHELL, SSH_TIMEOUT, REFRESH_RATE
    USERNAME = config['ssh']['username']
    SSH_KEY_PATH = config['ssh']['key_path']
    JUMP_SHELL = config['ssh']['jump_host']
    SSH_TIMEOUT = config['ssh']['timeout']
    REFRESH_RATE = config['display']['refresh_rate']

    gpu_checker = AsyncGPUChecker(targets)
    await gpu_checker.run()

if __name__ == '__main__':
    asyncio.run(main())
