# SSH GPU Monitor
Some awful, brittle code to check GPU status of multiple machines at a given host address through an SSH jumpnode.

Glued together from:
* https://github.com/pawni/gpuobserver
* https://stackoverflow.com/a/36096801/7565759

## Usage
Set target addresses and SSH Key location in main.py then just
```
python main.py
```
![Un-aesthetic Usage Example](example_running.png)




## Requirements
Needs
```
paramiko
tableprint
```
