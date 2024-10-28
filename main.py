"""This module is used to check GPU machines information asynchronously."""

import asyncio
import os
from typing import NamedTuple, Dict, List
import xml.etree.ElementTree as ET
import re
import sys
import logging
from logging.handlers import RotatingFileHandler
import traceback
from rich.live import Live
from rich.console import Console
import signal
import argparse
from pathlib import Path

# Add these imports at the top
import asyncssh
from src.table_display import GPUTable

# Configuration
USERNAME = 'afs219'
SSH_KEY_PATH = os.path.expanduser('~') + '/.ssh/id_rsa'
JUMP_SHELL = 'shell4.doc.ic.ac.uk'
SSH_TIMEOUT = 10  # seconds
REFRESH_RATE = 5
GPUS = [f'gpu{x:02}' for x in range(1, 31)]

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

    def __init__(self, servers: List[str]) -> None:
        self.servers = servers
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
        
    async def open_connection(self, target: str):
        """Modified connection method with better error handling"""
        logging.debug(f"Attempting to open connection to {target}")
        try:
            # Set up port forwarding
            listener = await asyncio.wait_for(
                self.jump_conn.forward_local_port('', 0, target, 22),
                timeout=SSH_TIMEOUT/2  # Shorter timeout for forwarding
            )
            tunnel_port = listener.get_port()
            
            # Attempt SSH connection
            conn = await asyncio.wait_for(
                asyncssh.connect(
                    'localhost', 
                    port=tunnel_port,
                    username=USERNAME, 
                    client_keys=[SSH_KEY_PATH],
                    known_hosts=None,
                    keepalive_interval=30,
                    keepalive_count_max=5
                ),
                timeout=SSH_TIMEOUT/2
            )
            
            self.connections[target] = conn
            logging.debug(f"Successfully connected to {target}")
            return {target: "Connected"}
            
        except asyncio.TimeoutError:
            logging.error(f"Timeout connecting to {target}")
            return {target: "Connection timeout"}
        except Exception as exc:
            logging.error(f"Error connecting to {target}: {str(exc)}")
            return {target: f"Connection error: {str(exc)}"}

    async def check_single_target(self, target: str) -> Dict[str, str]:
        """Check a single GPU target using an existing connection."""
        logging.debug(f"Checking target: {target}")
        try:
            conn = self.connections.get(target)
            if not conn:
                logging.warning(f"No connection for target: {target}")
                return {target: "No connection"}
            
            logging.debug(f"Running nvidia-smi command on {target}")
            result = await asyncio.wait_for(
                conn.run('nvidia-smi -q -x', check=True),
                timeout=SSH_TIMEOUT
            )
            if result.exit_status != 0:
                logging.error(f"Command failed on {target} with status {result.exit_status}")
                return {target: f"Command failed: {result.stderr}"}
            
            # Ensure we're working with a string
            output = result.stdout
            if isinstance(output, bytes):
                output = output.decode('utf-8')
            
            logging.debug(f"Received result from {target}, parsing GPU info")
            return {target: self.parse_gpu_info(target, output)}
        except asyncio.TimeoutError:
            logging.error(f"Timeout while querying {target}")
            return {target: "Timeout"}
        except asyncssh.Error as exc:
            logging.error(f"SSH Error for {target}: {str(exc)}")
            return {target: f"SSH Error: {str(exc)}"}
        except Exception as exc:
            logging.error(f"Unexpected error for {target}: {str(exc)}")
            logging.debug(f"Exception details for {target}:", exc_info=True)
            return {target: f"Unexpected error: {str(exc)}"}

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

            align_str = '\n' + " " * len(machine_name)
            return align_str.join(map(str, gpu_infos))
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
            initial_data = {server: "Connecting" for server in self.servers}
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
                connection_tasks = [self.open_connection(server) for server in self.servers]
                connection_results = await asyncio.gather(*connection_tasks, return_exceptions=True)
                
                # Process connection results
                for result in connection_results:
                    if isinstance(result, dict):
                        self.gpu_table.update_table(result)
                    else:
                        logging.error(f"Connection error: {str(result)}")
                
                live.update(self.gpu_table.table)
                logging.info("Finished opening connections to GPU servers")

                # Main loop
                logging.info("Entering main loop to query GPUs")
                while self.running:
                    try:
                        logging.debug("Starting a new round of GPU queries")
                        tasks = [self.check_single_target(server) for server in self.servers]
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

def setup_logging(debug_mode: bool = False):
    """Set up logging configuration based on debug mode"""
    if not debug_mode:
        return

    # Create logs directory if it doesn't exist
    log_dir = Path('./logs')
    log_dir.mkdir(exist_ok=True)
    
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = log_dir / 'gpu_checker.log'
    
    # Clear the log file
    with open(log_file, 'w') as f:
        f.write('')  # Write an empty string to clear the file
    
    log_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2)
    log_handler.setFormatter(log_formatter)
    log_handler.setLevel(logging.DEBUG)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.WARNING)
    root_logger.addHandler(log_handler)

async def main() -> None:
    """Main function for checking provided arguments and running GPU checker."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='GPU Checker')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Check for environment variable as alternative way to enable debug mode
    debug_mode = args.debug or os.environ.get('GPU_CHECKER_DEBUG', '').lower() in ('true', '1', 'yes')
    
    setup_logging(debug_mode)
    
    if debug_mode:
        logging.info("GPU checker started in debug mode")
    
    if not os.path.exists(SSH_KEY_PATH):
        if debug_mode:
            logging.error(f'SSH key not found at {SSH_KEY_PATH}')
        print('SSH key not found. Please check the provided path.')
        return

    gpu_checker = AsyncGPUChecker(GPUS)
    await gpu_checker.run()

if __name__ == '__main__':
    asyncio.run(main())
