import os
import paramiko
import xml.etree.ElementTree as ET
import re
import time
from reprint import output

JUMP_SHELL = 'shell4.doc.ic.ac.uk'
USERNAME = 'afs219'
SSH_KEY_LOC = os.getenv('HOME') + '/.ssh/id_rsa'
SERVERS = ['gpu0{}'.format(x) for x in range(1, 10)] + ['gpu{}'.format(x) for x in range(10,30)]
SSH_TIMEOUT = 1
REFRESH_RATE = 5

def main():
    gpu_checker = GPUChecker(SERVERS)
    gpu_checker.run()

class GPUChecker:
    def __init__(self, servers):
        self.servers = servers
        self.proc_filter = re.compile(r'.*')
        self.jumpbox = self.open_jump()
        self.ssh_gpus = self.connect_gpus()

    def open_jump(self):
        print('-- Opening Jump Connection --')
        jumpbox=paramiko.SSHClient()
        jumpbox.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jumpbox.connect(JUMP_SHELL, username=USERNAME, key_filename=SSH_KEY_LOC)
        print('-- Succesfully Opened Jump Connection --')
        return jumpbox

    
    def connect_gpus(self):
        print('-- Opening GPU SSH Connections --')
        ssh_connnections = {}
        for server in self.servers:
            ssh_connnections[server] = self.open_ssh_gpu(server)
        print('-- Finished Connecting to GPUs --')
        return ssh_connnections

    def open_ssh_gpu(self, target_addr):
        jumpbox_transport = self.jumpbox.get_transport()

        src_addr = (JUMP_SHELL, 22)
        dest_addr = (target_addr, 22)

        try:
            jumpbox_channel = jumpbox_transport.open_channel("direct-tcpip", dest_addr, src_addr, timeout=SSH_TIMEOUT)
        except (paramiko.ssh_exception.ChannelException, paramiko.ssh_exception.SSHException) as e:
            return "Offline"

        target = paramiko.SSHClient()
        target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            target.connect(target_addr, username='afs219', key_filename=SSH_KEY_LOC, sock=jumpbox_channel, timeout=SSH_TIMEOUT, auth_timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT)
        except paramiko.ssh_exception.SSHException:
            return "No Session"
        return target

    def get_gpu_info(self, ssh):
        info_dict = self.get_gpu_info_raw(ssh)
        return "{model} | Free: {free} | GPU Util: {gpu_util} | Num Procs: {numprocs} | Memory: {used_mem}/{mem}".format(**info_dict)

    def get_gpu_info_raw(self, ssh):
        # collects gpu usage information for a ssh connection  
        _, ssh_stdout, _ = ssh.exec_command('nvidia-smi -q -x')
        res = ''.join(ssh_stdout.readlines())
        nvidiasmi_output = ET.fromstring(res)
        gpus = nvidiasmi_output.findall('gpu')

        gpu_infos = []
        info = {}
        for idx, gpu in enumerate(gpus):
            model = "{:<23}".format(gpu.find('product_name').text)
            processes = gpu.findall('processes')[0]
            pids = [process.find('pid').text for process in processes if self.proc_filter.search(process.find('process_name').text)]
            numprocs = len(pids)
            mem = gpu.find('fb_memory_usage').find('total').text
            gpu_util = "{:<5}".format(gpu.find('utilization').find('gpu_util').text)
            used_mem = gpu.find('fb_memory_usage').find('used').text.replace(' MiB', "")
            free = "{:<5}".format(str((len(pids) == 0)))

            info['idx'] =  idx
            info['model'] = model
            info['numprocs'] = numprocs
            info['free'] = free
            info['mem'] = mem
            info['gpu_util'] = gpu_util
            info['used_mem'] = used_mem
        
        return info

    def init_output(self):
        self.output_table = output(output_type='dict')
        print('\n---------------------------------------------------------------\n')

    def run(self):
        self.init_output()
        try:
            with self.output_table as output_table:
                while True:
                    output_table['Time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                    for gpu_name, gpu_connection in self.ssh_gpus.items():
                        if isinstance(gpu_connection, paramiko.client.SSHClient):
                            output = self.get_gpu_info(gpu_connection)
                        else:
                            # output = gpu_connection
                            pass
                            
                        output_table[gpu_name] = output
                    time.sleep(REFRESH_RATE)
        except KeyboardInterrupt:
            print("-- Closing SSH Connections --")
            for connection in self.ssh_gpus.values():
                if isinstance(connection, paramiko.client.SSHClient):
                    connection.close()
            self.jumpbox.close()

if __name__ == '__main__':
    main()