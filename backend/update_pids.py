import re
import os

# 1. Parse markdown
md_path = r'd:\Work\Urea Simulation\References\Master_PID_Tuning_Constants.md'
with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

table_lines = [l for l in text.split('\n') if '|' in l and 'Controller Tag' not in l and '---' not in l]

pids = {}
for line in table_lines:
    parts = line.split('|')
    if len(parts) >= 6:
        tag = parts[1].replace('**', '').strip()
        if not tag: continue
        gain = float(parts[3].replace(' ', '').replace('s', '').strip())
        ti = float(parts[4].replace(' ', '').replace('s', '').strip())
        td = float(parts[5].replace(' ', '').replace('s', '').strip())
        tf = float(parts[6].replace(' ', '').replace('s', '').strip())
        # Replace dashes with underscores for regex matching (e.g., FIC-323401 -> FIC_323401)
        py_tag = tag.replace('-', '_')
        pids[py_tag] = {'Kc': gain, 'Ti': ti, 'Td': td, 'Tf': tf}
        pids[tag] = {'Kc': gain, 'Ti': ti, 'Td': td, 'Tf': tf} # Keep orig for steam_system

print(f'Parsed {len(pids)//2} PIDs.')

# 2. Update main.py
main_py_path = r'd:\Work\Urea Simulation\backend\main.py'
with open(main_py_path, 'r', encoding='utf-8') as f:
    main_code = f.read()

# For each dictionary assignment like self.FIC_323401 = {... "Kc": [val][* RHO], "Ti": [val], ...}
new_main_code = main_code
matches_found = 0
for tag, params in pids.items():
    if '_' not in tag: continue
    # Regex to find self.TAG = {...} block
    # It might span multiple lines. We can just search for "Kc": <val>, "Ti": <val> within the self.TAG assignment.
    # A simpler approach: regex find `self.TAG = { ... }` up to the closing brace, non-greedy.
    pattern = r'(self\.' + tag + r'\s*=\s*\{.*?\}\s*)'
    def repl(m):
        block = m.group(1)
        # Replace Kc
        # It could be `"Kc": 1.2` or `"Kc": 1.2 * RHO_401_KGM3`
        # We replace the float value but keep the RHO part if it exists.
        block = re.sub(r'("Kc"\s*:\s*)-?\d+\.?\d*', rf'\g<1>{params["Kc"]}', block)
        # Replace Ti
        block = re.sub(r'("Ti"\s*:\s*)-?\d+\.?\d*', rf'\g<1>{params["Ti"]}', block)
        # Replace Td
        block = re.sub(r'("Td"\s*:\s*)-?\d+\.?\d*', rf'\g<1>{params["Td"]}', block)
        # Replace Tf (if it exists)
        block = re.sub(r'("Tf"\s*:\s*)-?\d+\.?\d*', rf'\g<1>{params["Tf"]}', block)
        return block
    
    new_code, num_subs = re.subn(pattern, repl, new_main_code, flags=re.DOTALL)
    if num_subs > 0:
        matches_found += 1
        new_main_code = new_code

with open(main_py_path, 'w', encoding='utf-8') as f:
    f.write(new_main_code)
print(f'Updated {matches_found} controllers in main.py')

# 3. Update steam_system.py
steam_py_path = r'd:\Work\Urea Simulation\backend\steam_system.py'
with open(steam_py_path, 'r', encoding='utf-8') as f:
    steam_code = f.read()

# Manually update K_PIC_204, KI_PIC_204, K_PIC_207, KI_PIC_207, etc.
# In steam_system.py:
# K_PIC_204    = 40.0
# KI_PIC_204   = 2.0
if 'PIC-329204' in pids:
    steam_code = re.sub(r'(K_PIC_204\s*=\s*)-?\d+\.?\d*', rf'\g<1>{pids["PIC-329204"]["Kc"]}', steam_code)
    steam_code = re.sub(r'(KI_PIC_204\s*=\s*)-?\d+\.?\d*', rf'\g<1>{pids["PIC-329204"]["Kc"]/pids["PIC-329204"]["Ti"] if pids["PIC-329204"]["Ti"]>0 else 0}', steam_code)

if 'PIC-329207A' in pids: # we'll map 207 to A for now or maybe it needs a custom mapping. Wait, 207 is a "sub-controller".
    # The reference lists PIC-329207A, B, C separately.
    # In steam_system.py, K_PIC_207 is shared by A, B, C or is it?
    # Line 123: K_PIC_207 = 40.0, KI_PIC_207 = 2.0
    # Let's use the average or just one of them? A, B, C have Gains 6, 4, 4. Let's use B's for the generic 207.
    kc = pids["PIC-329207B"]["Kc"]
    ti = pids["PIC-329207B"]["Ti"]
    steam_code = re.sub(r'(K_PIC_207\s*=\s*)-?\d+\.?\d*', rf'\g<1>{kc}', steam_code)
    steam_code = re.sub(r'(KI_PIC_207\s*=\s*)-?\d+\.?\d*', rf'\g<1>{kc/ti if ti>0 else 0}', steam_code)

with open(steam_py_path, 'w', encoding='utf-8') as f:
    f.write(steam_code)

print("Finished steam_system.py")
