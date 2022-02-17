"""This module is used to check GPU machines information."""

from typing import NamedTuple
import xml.etree.ElementTree as ET
import os
import re
import time
import paramiko
import reprint

# Change these according to your own configuration.
USERNAME = 'afs219'
SSH_KEY_PATH = os.path.expanduser('~') + '/.ssh/id_rsa'

JUMP_SHELL = 'shell4.doc.ic.ac.uk'  # One of shell1, shell2, shell3, shell4 or shell5
SSH_TIMEOUT = 1
REFRESH_RATE = 5

# Lab Machines
TEXELS  = [f'texel{x:02}'  for x in range(1, 45)]
SPRITES = [f'sprite{x:02}' for x in range(1, 39)]
ARCS    = [f'arc{x:02}'    for x in range(1, 15)]
GPUS    = [f'gpu{x:02}'    for x in range(1, 28)]
EDGES   = [f'edge{x:02}'   for x in range(1, 41)]
VERTEXS = [f'vertex{x:02}' for x in range(1, 63)]
RAYS    = [f'ray{x:02}'    for x in range(1, 27)]
POINTS  = [f'point{x:02}'  for x in range(1, 30)]

SERVERS = GPUS


class GPUInfo(NamedTuple):
    """A class for representing a GPU machine's information."""

    model: str
    num_procs: int
    gpu_util: str
    used_mem: str
    total_mem: str

    def __str__(self) -> str:
        return (
            f'{self.model:26} | Free: {self.num_procs == 0!s:5} | Num Procs: {self.num_procs} | '
            f'GPU Util: {self.gpu_util:>3} % | Memory: {self.used_mem:>5} / {self.total_mem:>5} MiB'
        )


class GPUChecker:
    """A class for checking GPU machines."""

    def __init__(self, servers: list[str]) -> None:
        self.servers = servers
        self.proc_filter = re.compile(r'.*')
        self.output_table = reprint.output(output_type='dict')
        self.jumpbox = self.open_jump()
        self.ssh_gpus = self.connect_gpus()

    def close(self) -> None:
        """Closes the SSH connections."""

        print('-- Closing the SSH connections --')

        for connection in self.ssh_gpus.values():
            if isinstance(connection, paramiko.SSHClient):
                connection.close()

        self.jumpbox.close()

        print('-- Successfully closed the SSH connections --')

    def open_jump(self) -> paramiko.SSHClient:
        """Opens a jump connection."""

        print('-- Opening the Jump connection --')
        jumpbox = paramiko.SSHClient()
        jumpbox.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            jumpbox.connect(JUMP_SHELL, username=USERNAME, key_filename=SSH_KEY_PATH)
        except paramiko.AuthenticationException as err:
            print('Authentication failed. Check user name and SSH key configuration.')
            raise ValueError from err

        print('-- Successfully opened the Jump connection --')
        return jumpbox

    def connect_gpus(self):
        """Opens SSH connections to all the GPU machines."""

        print('-- Opening the GPU SSH connections --')
        ssh_connnections = {server: self.open_ssh_gpu(server) for server in self.servers}
        print('-- Successfully opened the GPU SSH connections --')
        return ssh_connnections

    def open_ssh_gpu(self, target_addr: str):
        """Opens a SSH connection to a given GPU machine address."""

        jumpbox_transport = self.jumpbox.get_transport()

        src_addr = (JUMP_SHELL, 22)
        dest_addr = (target_addr, 22)

        try:
            jumpbox_channel = jumpbox_transport.open_channel('direct-tcpip', dest_addr, src_addr, timeout=SSH_TIMEOUT)
        except (paramiko.ChannelException, paramiko.SSHException):
            return 'Offline'

        target = paramiko.SSHClient()
        target.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            target.connect(target_addr, username=USERNAME, key_filename=SSH_KEY_PATH, sock=jumpbox_channel,
                           timeout=SSH_TIMEOUT, auth_timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
        except paramiko.SSHException:
            return 'No Session'

        return target

    def get_gpu_info(self, machine_name: str, ssh_connection: paramiko.SSHClient) -> str:
        """Gets the GPU info for the given SSH connection, in string format."""

        # Transform each info to a string and join preserving alignment
        align_str = '\n' + " " * len(machine_name)
        return align_str.join(map(str, self.get_gpu_info_raw(ssh_connection)))

    def get_gpu_info_raw(self, ssh_connection: paramiko.SSHClient):
        """Gets the GPU info for the given SSH connection, in raw format."""

        _, ssh_stdout, _ = ssh_connection.exec_command('nvidia-smi -q -x')
        res = ''.join(ssh_stdout.readlines())

        try:
            nvidiasmi_output = ET.fromstring(res)
        except ET.ParseError:
            # Unable to parse result, return error.
            yield res
            return

        proc_filter = self.proc_filter

        for gpu in nvidiasmi_output.findall('gpu'):
            model = gpu.find('product_name').text
            num_procs = sum(1 for process in gpu.find('processes')
                            if proc_filter.search(process.find('process_name').text))
            gpu_util = gpu.find('utilization').find('gpu_util').text.removesuffix(' %')
            memory_usage = gpu.find('fb_memory_usage')
            used_mem = memory_usage.find('used').text.removesuffix(' MiB')
            total_mem = memory_usage.find('total').text.removesuffix(' MiB')

            yield GPUInfo(model, num_procs, gpu_util, used_mem, total_mem)

    def run(self) -> None:
        """Runs the main loop of the GPU checker."""

        print('\n-------------------------------------------------\n')

        try:
            with self.output_table as output_table:
                while True:
                    output_table['Time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

                    for name, connection in self.ssh_gpus.items():
                        if isinstance(connection, paramiko.SSHClient):
                            output_table[name] = self.get_gpu_info(name, connection)
                        else:
                            # Connection could not be created, use error message.
                            output_table[name] = connection

                    time.sleep(REFRESH_RATE)
        except KeyboardInterrupt:
            self.close()


def main() -> None:
    """Main function for checking provided arguments and running GPU checker."""

    if not os.path.exists(SSH_KEY_PATH):
        print('SSH key not found. Please check the provided path.')
        return

    try:
        gpu_checker = GPUChecker(SERVERS)
    except ValueError:
        return

    gpu_checker.run()


if __name__ == '__main__':
    main()
