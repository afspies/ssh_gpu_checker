# SSH GPU Checker Revamp TODOs

## 1. Implement Asynchronous SSH Checks
- [X] Refactor the main SSH checking function to be asynchronous
- [X] Implement an async function to check a single target
- [X] Create an async main function to run all checks concurrently
- [X] Implement a mechanism to update the results table as checks complete

## 2. Enhance Display with Rich Library
- [X] Design a new table layout with columns for hostname, status, GPU info, etc
- [X] Implement color coding for different statuses (e.g., green for available, red for unavailable)
- [X] Use font emphases (bold, italic) to highlight important information
- [X] Implement live updating of the table as results come in

## 3. Restructure Project
- [X] Create a new project structure:
  ```
  ssh_gpu_checker/
  ├── config/
  │   └── config.yaml
  ├── src/
  │   └── ssh_checker.py
  │   └── table_display.py
  ├── main.py
  └── requirements.txt
  ```
- [X] Move configuration to `config/config.yaml`
- [X] Implement config loading function in `main.py`
- [ ] Create `src/ssh_checker.py` for core SSH logic
- [X] Create `src/table_display.py` for Rich table implementation
- [ ] Update `main.py` to use the new structure and modules

## 4. Additional Improvements
- [X] Add error handling and logging
- [X] Implement command-line arguments for flexibility
- [ ] Write unit tests for core functions
- [X] Add documentation and comments throughout the code
- [ ] Create a README.md with usage instructions and project overview
