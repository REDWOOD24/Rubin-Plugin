import json
import random
from collections import defaultdict, deque
from pathlib import Path

SEED = 20260803
rng = random.Random(SEED)

OUTPUT_PATH = Path("../workload/quantum_graph_1_jobs.json")

# 20 data units × 5 quantum/task stages = 100 jobs.
STAGES = [
    {
        "task": "isr",
        "input_dataset": "raw",
        "output_dataset": "postISRCCD",
        "cores": (1, 2),
        "flops": (1_000_000, 1_300_000),
        "output_size": (900_000_000, 1_400_000_000),
    },
    {
        "task": "characterizeImage",
        "input_dataset": "postISRCCD",
        "output_dataset": "icExp",
        "cores": (1, 4),
        "flops": (1_200_000, 1_500_000),
        "output_size": (1_000_000_000, 1_600_000_000),
    },
    {
        "task": "calibrate",
        "input_dataset": "icExp",
        "output_dataset": "calexp",
        "cores": (1, 4),
        "flops": (1_400_000, 1_700_000),
        "output_size": (1_200_000_000, 1_900_000_000),
    },
    {
        "task": "makeWarp",
        "input_dataset": "calexp",
        "output_dataset": "deepCoadd_directWarp",
        "cores": (2, 6),
        "flops": (1_600_000, 1_900_000),
        "output_size": (1_800_000_000, 2_800_000_000),
    },
    {
        "task": "assembleCoadd",
        "input_dataset": "deepCoadd_directWarp",
        "output_dataset": "deepCoadd",
        "cores": (2, 8),
        "flops": (1_800_000, 2_000_000),
        "output_size": (2_500_000_000, 4_000_000_000),
    },
]

UNITS = 1

# jobid(stage, unit), where stage is 0..4 and unit is 0..19.
def job_id(stage_index: int, unit_index: int) -> int:
    return stage_index * UNITS + unit_index + 1


parents = {jid: set() for jid in range(1, 101)}
edge_dataset = {}
edge_delay = {}

# Per-unit stage dependencies:
# isr -> characterizeImage -> calibrate -> makeWarp -> assembleCoadd.
for unit in range(UNITS):
    for stage_index in range(len(STAGES) - 1):
        parent = job_id(stage_index, unit)
        child = job_id(stage_index + 1, unit)

        parents[child].add(parent)
        edge_dataset[(parent, child)] = STAGES[stage_index]["output_dataset"]
        edge_delay[(parent, child)] = rng.randint(0, 3)

# Add realistic coadd fan-in:
# each assembleCoadd quantum consumes warps from nearby patches.
for unit in range(UNITS):
    assemble_job = job_id(4, unit)

    for neighboring_unit in (unit - 2, unit - 1):
        if neighboring_unit >= 0:
            warp_job = job_id(3, neighboring_unit)
            parents[assemble_job].add(warp_job)
            edge_dataset[(warp_job, assemble_job)] = "deepCoadd_directWarp"
            edge_delay[(warp_job, assemble_job)] = rng.randint(0, 3)

children = defaultdict(list)

for child, parent_ids in parents.items():
    for parent in sorted(parent_ids):
        children[parent].append({
            "jobid": child,
            "creation_delay": edge_delay[(parent, child)],
            "dataset_type": edge_dataset[(parent, child)],
        })

# Build output filenames before constructing child input lists.
output_files_by_job = {}

for stage_index, stage in enumerate(STAGES):
    for unit in range(UNITS):
        jid = job_id(stage_index, unit)
        dataset_type = stage["output_dataset"]

        output_name = (
            f"{dataset_type}_job_{jid}_unit_{unit}.root"
        )
        output_size = rng.randint(*stage["output_size"])

        output_files_by_job[jid] = {
            output_name: output_size
        }

jobs = []

for stage_index, stage in enumerate(STAGES):
    for unit in range(UNITS):
        jid = job_id(stage_index, unit)

        band = ["g", "r", "i", "z", "y"][unit % 5]

        if stage_index <= 2:
            data_id = {
                "instrument": "LSSTCam",
                "visit": 10000 + unit,
                "detector": unit,
                "band": band,
            }
        else:
            data_id = {
                "instrument": "LSSTCam",
                "tract": 2000,
                "patch": unit,
                "band": band,
            }

        if stage_index == 0:
            # Root quantum: raw input originates outside the graph.
            input_files = [
                f"raw_visit_{10000 + unit}_detector_{unit}.fits"
            ]
        else:
            # Inputs are the actual output filenames of parent jobs.
            input_files = []
            for parent in sorted(parents[jid]):
                input_files.extend(output_files_by_job[parent].keys())

        jobs.append({
            "jobid": jid,
            "task": stage["task"],
            "resource_key": f"{stage['task']}:LSSTCam",
            "data_id": data_id,
            "cores": rng.randint(*stage["cores"]),
            "flops": rng.randint(*stage["flops"]),

            # Matches the workload-manager behavior:
            # only initially runnable jobs receive absolute creation times.
            "creation_time": (
                rng.randint(0, 30)
                if stage_index == 0
                else None
            ),

            "input_files": sorted(input_files),
            "output_files": output_files_by_job[jid],

            # Equivalent to add_parent(parent_jobid).
            "parents": sorted(parents[jid]),

            # Equivalent to add_child(child_jobid, relative_creation_time).
            "children": sorted(
                children[jid],
                key=lambda child: child["jobid"]
            ),
        })

# Validate acyclicity using Kahn's algorithm.
indegree = {
    jid: len(parent_ids)
    for jid, parent_ids in parents.items()
}

queue = deque(
    jid for jid, degree in indegree.items()
    if degree == 0
)

visited = 0

while queue:
    current = queue.popleft()
    visited += 1

    for child in children[current]:
        child_id = child["jobid"]
        indegree[child_id] -= 1

        if indegree[child_id] == 0:
            queue.append(child_id)

assert len(jobs) == 5*UNITS
assert visited == 100, "The generated QuantumGraph contains a cycle."

dependency_count = sum(len(value) for value in parents.values())

payload = {
    "schema_version": "0.2",
    "qgraph": {
        "instrument": "LSSTCam",
        "description": (
            "100 workload-manager jobs arranged as a five-stage QuantumGraph"
        ),
        "Num_of_Jobs": 100,
        "number_of_dependencies": dependency_count,
        "tasks": [stage["task"] for stage in STAGES],
    },
    "jobs": jobs,
}

with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")

print(f"Created: {OUTPUT_PATH}")
print(f"Jobs: {len(jobs)}")
print(f"Dependencies: {dependency_count}")
print(f"Root jobs: {sum(1 for value in parents.values() if not value)}")
print(f"Validated DAG: {visited == 100}")
