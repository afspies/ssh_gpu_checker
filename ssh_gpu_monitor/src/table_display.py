import logging
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.panel import Panel  # Add this import

class GPUTable:
    def __init__(self):
        self.console = Console()
        # Initialize dictionary to track max widths for each column
        self.max_widths = {
            "Hostname": 20,  # Start with our minimum requirements
            "Status/Model": 30,
            "Free": 5,
            "Procs": 5,
            "GPU %": 6,
            "Memory": 15
        }
        self._create_table()
        self.data = {}

    def _create_table(self):
        """Create the table with proper columns"""
        self.raw_table = Table(
            title="GPU Status",
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
            pad_edge=True,
            padding=(0, 1)
        )
        
        # Use tracked max widths for columns
        self.raw_table.add_column("Hostname", style="cyan", no_wrap=True, min_width=self.max_widths["Hostname"])
        self.raw_table.add_column("Status/Model", style="green", min_width=self.max_widths["Status/Model"])
        self.raw_table.add_column("Free", style="yellow", justify="center", min_width=self.max_widths["Free"])
        self.raw_table.add_column("Procs", style="red", justify="center", min_width=self.max_widths["Procs"])
        self.raw_table.add_column("GPU %", style="blue", justify="right", min_width=self.max_widths["GPU %"])
        self.raw_table.add_column("Memory", style="green", justify="right", min_width=self.max_widths["Memory"])

        self.table = Align.center(self.raw_table)

    def update_max_widths(self, hostname: str, values: list[str]) -> None:
        """Update the maximum widths based on new values"""
        columns = ["Hostname", "Status/Model", "Free", "Procs", "GPU %", "Memory"]
        values = [hostname] + values  # Add hostname to the values list
        
        for col, val in zip(columns, values):
            if val != "—":  # Don't update for placeholder values
                self.max_widths[col] = max(self.max_widths[col], len(str(val)))

    def update_table(self, new_data: dict[str, str]) -> None:
        """Update the table with new data"""
        logging.debug(f"Updating table with data: {new_data}")
        self.data.update(new_data)
        
        # First pass: update maximum widths
        for hostname, status in self.data.items():
            if status in ["Connecting", "Connected", "No connection"] or \
               status.startswith(("Connection", "Error", "Timeout", "SSH Error", "Unexpected error", "Parse error", "XML parse error")):
                self.update_max_widths(hostname, [status, "—", "—", "—", "—"])
            else:
                try:
                    # Split multiple GPU entries
                    gpu_entries = status.split('\n')
                    for gpu_entry in gpu_entries:
                        parts = [p.strip() for p in gpu_entry.split("|")]
                        if len(parts) == 5:
                            model = parts[0]
                            is_free = parts[1].split(":")[1].strip()
                            num_procs = parts[2].split(":")[1].strip()
                            gpu_util = parts[3].split(":")[1].strip()
                            memory = parts[4].split(":")[1].strip()
                            self.update_max_widths(hostname, [model, is_free, num_procs, gpu_util, memory])
                except:
                    pass

        # Recreate the table with updated widths
        self._create_table()
        
        # Second pass: add rows
        for hostname, status in sorted(self.data.items()):
            try:
                if status in ["Connecting", "Connected", "No connection"] or \
                   status.startswith(("Connection", "Error", "Timeout", "SSH Error", "Unexpected error", "Parse error", "XML parse error")):
                    self.raw_table.add_row(
                        hostname,
                        status,
                        "—",
                        "—",
                        "—",
                        "—"
                    )
                else:
                    try:
                        # Split multiple GPU entries
                        gpu_entries = status.split('\n')
                        for i, gpu_entry in enumerate(gpu_entries):
                            parts = [p.strip() for p in gpu_entry.split("|")]
                            if len(parts) != 5:
                                raise ValueError(f"Invalid format: expected 5 parts, got {len(parts)}")
                                
                            model = parts[0]
                            is_free = parts[1].split(":")[1].strip()
                            num_procs = parts[2].split(":")[1].strip()
                            gpu_util = parts[3].split(":")[1].strip()
                            memory = parts[4].split(":")[1].strip()
                            
                            # Only show hostname on first GPU row
                            display_hostname = hostname if i == 0 else ""
                            
                            self.raw_table.add_row(
                                display_hostname,
                                model,
                                is_free,
                                num_procs,
                                gpu_util,
                                memory
                            )
                    except (IndexError, ValueError) as e:
                        logging.error(f"Failed to parse GPU info for {hostname}: {str(e)}")
                        self.raw_table.add_row(
                            hostname,
                            f"Parse error: {str(e)}",
                            "—",
                            "—",
                            "—",
                            "—"
                        )
                        
            except Exception as e:
                logging.error(f"Error adding row for {hostname}: {str(e)}")
                self.raw_table.add_row(
                    hostname,
                    f"Error: {str(e)}",
                    "—",
                    "—",
                    "—",
                    "—"
                )
                
        logging.debug("Table updated successfully")

    def show_goodbye(self):
        """Show goodbye message instead of table"""
        goodbye_msg = "Goodbye! 👋"
        self.table = Align.center(Panel.fit(goodbye_msg))

    def get_live_table(self) -> Live:
        """Get a Live display context manager for the table"""
        return Live(
            self.table,  # Use the padded display instead of the raw table
            refresh_per_second=4,
            console=self.console,
            vertical_overflow="visible"
        )
