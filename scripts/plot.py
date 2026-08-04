#!/usr/bin/env python3
import argparse
import html
import json
import shutil
import subprocess
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True)


def load_jobs(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    jobs = {int(job["jobid"]): job for job in data["jobs"]}
    return data, jobs


def task_order(data, jobs):
    order = list(data.get("qgraph", {}).get("tasks", []))
    for job in jobs.values():
        task = job.get("task", "unknown")
        if task not in order:
            order.append(task)
    return order


def node_label(job):
    creation = job.get("creation_time")
    flops = f'{job.get("flops", 0) / 1_000_000:.2f} MF'
    parents = len(job.get("parents", []))
    children = len(job.get("children", []))
    inputs = len(job.get("input_files", []))
    outputs = len(job.get("output_files", {}))

    creation_row = ""
    if creation is not None:
        creation_row = (
            f'<TR><TD ALIGN="LEFT">start: {creation}</TD></TR>'
        )

    return f'''<
<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">
  <TR><TD><B>Job {job["jobid"]}</B></TD></TR>
  <TR><TD ALIGN="LEFT">{job.get("cores", 0)} cores, {flops}</TD></TR>
  <TR><TD ALIGN="LEFT">P/C {parents}/{children}, I/O {inputs}/{outputs}</TD></TR>
  {creation_row}
</TABLE>>'''


def build_dot(data, jobs, edge_labels):
    order = task_order(data, jobs)
    grouped = {task: [] for task in order}

    for job_id, job in jobs.items():
        grouped.setdefault(job.get("task", "unknown"), []).append(job_id)

    lines = [
        "digraph JobDAG {",
        '  graph [rankdir=LR, compound=true, newrank=true, splines=polyline,',
        '         nodesep=0.10, ranksep=0.85, pad=0.20,',
        '         label="QuantumGraph workload", labelloc=t,',
        '         fontsize=20, fontname="Helvetica"];',
        '  node [shape=plain, fontname="Helvetica", fontsize=8];',
        '  edge [fontname="Helvetica", fontsize=7, arrowsize=0.60, penwidth=0.75];',
    ]

    representatives = []

    for stage_index, task in enumerate(order):
        job_ids = sorted(grouped.get(task, []))
        if not job_ids:
            continue

        representatives.append(job_ids[0])
        lines.extend([
            f"  subgraph cluster_{stage_index} {{",
            f'    label="{esc(task)}";',
            '    labelloc=t;',
            '    fontsize=14;',
            '    fontname="Helvetica";',
            '    style="rounded";',
            '    rank=same;',
        ])

        for previous, current in zip(job_ids, job_ids[1:]):
            lines.append(
                f"    j{previous} -> j{current} "
                "[style=invis, weight=20, constraint=false];"
            )

        for job_id in job_ids:
            job = jobs[job_id]
            child_ids = [
                child["jobid"]
                for child in job.get("children", [])
            ]
            tooltip = (
                f"Job {job_id}; "
                f"task={job.get('task', '')}; "
                f"cores={job.get('cores', 0)}; "
                f"flops={job.get('flops', 0)}; "
                f"creation_time={job.get('creation_time')}; "
                f"parents={job.get('parents', [])}; "
                f"children={child_ids}; "
                f"inputs={job.get('input_files', [])}; "
                f"outputs={list(job.get('output_files', {}).keys())}"
            )
            lines.append(
                f'    j{job_id} [label={node_label(job)}, '
                f'tooltip="{esc(tooltip)}"];'
            )

        lines.append("  }")

    for left, right in zip(representatives, representatives[1:]):
        lines.append(
            f"  j{left} -> j{right} "
            "[style=invis, weight=100, minlen=2];"
        )

    for parent_id, job in jobs.items():
        for child in job.get("children", []):
            child_id = int(child["jobid"])
            dataset = child.get("dataset_type", "")
            delay = child.get("creation_delay", 0)
            tooltip = (
                f"{parent_id} -> {child_id}; "
                f"dataset={dataset}; creation_delay={delay}"
            )

            if edge_labels:
                label = f"{esc(dataset)}\\n+{delay}"
                lines.append(
                    f'  j{parent_id} -> j{child_id} '
                    f'[label="{label}", tooltip="{esc(tooltip)}"];'
                )
            else:
                lines.append(
                    f'  j{parent_id} -> j{child_id} '
                    f'[tooltip="{esc(tooltip)}"];'
                )

    lines.extend([
        '  subgraph cluster_legend {',
        '    label="Legend";',
        '    style="rounded,dashed";',
        '    fontsize=10;',
        '    key1 [shape=box, label="Column = task stage"];',
        '    key2 [shape=box, label="Arrow = dependency"];',
        '    key1 -> key2 [style=invis];',
        '  }',
        "}",
    ])

    return "\n".join(lines) + "\n"


def render(json_path, output_prefix, edge_labels):
    if shutil.which("dot") is None:
        raise RuntimeError("Graphviz 'dot' was not found.")

    data, jobs = load_jobs(json_path)
    pdf_path = Path(output_prefix).with_suffix(".pdf")

    subprocess.run(
        ["dot", "-Tpdf", "-o", str(pdf_path)],
        input=build_dot(data, jobs, edge_labels),
        text=True,
        check=True,
    )

    print(f"PDF: {pdf_path}")


def main():
    
    input_file = "../workload/quantum_graph_100_jobs.json";
    output_file = "../plot/dag_dependency.pdf"
    render(input_file, output_file, "store_true")


if __name__ == "__main__":
    main()
