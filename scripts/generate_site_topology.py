import json
import random
from pathlib import Path

workload_path = Path("../workload/quantum_graph_100_jobs.json")
output_path = Path("../config/site_topology.json")

workload = json.loads(workload_path.read_text(encoding="utf-8"))
root_jobs = [job for job in workload["jobs"] if not job.get("parents")]

initial_files = [
    file_name
    for job in root_jobs
    for file_name in job.get("input_files", [])
]

rng = random.Random(20260803)

site_specs = [
    (20_000_000.0, 20, "4096GB"),
    (24_000_000.0, 24, "4096GB"),
    (28_000_000.0, 28, "2048GB"),
    (32_000_000.0, 32, "4096GB"),
    (36_000_000.0, 36, "8192GB"),
]

disk_types = ["CALIBDISK", "DATADISK", "LOCALGROUPDISK", "SCRATCHDISK"]
topology = {}

for site_index in range(5):
    assigned_files = initial_files[site_index::5]
    speed, cores, ram = site_specs[site_index]

    cpu_info = []
    for cpu_index in range(2):
        disks = []
        for disk_type in disk_types:
            disks.append({
                "name": f"SITE{site_index}_C{cpu_index}_{disk_type}",
                "read_bw": f"{rng.randint(1200, 4800)}MBps",
                "write_bw": f"{rng.randint(1000, 4500)}MBps"
            })

        cpu_info.append({
            "units": 1,
            "speed": speed + cpu_index * 4_000_000.0,
            "cores": cores + cpu_index * 8,
            "BW_CPU": f"{rng.randint(2200, 3600)}GBps",
            "LAT_CPU": f"{rng.randint(40, 90)}ns",
            "properties": [{"ram": ram}],
            "disks": disks
        })

    files = []
    for file_name in assigned_files:
        # Synthetic raw image size: approximately 5–8 GB.
        files.append([
            file_name,
            rng.randint(5_000_000_000, 8_000_000_000)
        ])

    topology[f"Site{site_index}"] = {
        "SITE_PROPERTIES": {
            "storage_capacity_bytes": str(20_000_000_000_000),
            "file_count": str(len(files))
        },
        "CPUInfo": cpu_info,
        "files": files
    }

output_path.write_text(json.dumps(topology, indent=2) + "\n", encoding="utf-8")

placed_files = [
    file_entry[0]
    for site in topology.values()
    for file_entry in site["files"]
]

assert len(initial_files) == 20
assert sorted(placed_files) == sorted(initial_files)
assert len(placed_files) == len(set(placed_files))

print(f"Created: {output_path}")
print(f"Sites: {len(topology)}")
print(f"Initial files placed: {len(placed_files)}")
print("Files per site:", [len(topology[f'Site{i}']['files']) for i in range(5)])
