# Rubin Plugin

A C++17 dispatcher plugin for [CGSim](https://github.com/REDWOOD24/CGSim) that simulates a synthetic Rubin Observatory-inspired data-processing workflow across multiple computing sites.

> This is a research example, not an official Rubin Observatory or LSST Science Pipelines component.

## Requirements

- CMake 3.12+
- C++17 compiler
- CGSim
- SimGrid
- Boost
- SQLite3
- `nlohmann/json`
- Python 3 and Graphviz are optional for regenerating inputs and plotting workload DAGs.

## Build

Build and install CGSim first, then build the plugin:

```bash
git clone https://github.com/REDWOOD24/CGSim.git
git clone https://github.com/REDWOOD24/Rubin-Plugin.git

cmake -S CGSim -B CGSim/build -DCMAKE_BUILD_TYPE=Release
cmake --build CGSim/build -j
sudo cmake --install CGSim/build

cd Rubin-Plugin
cmake -S plugin -B plugin/build -DCMAKE_BUILD_TYPE=Release
cmake --build plugin/build -j
```

The plugin library is normally created at:

- Linux: `plugin/build/libRubinPlugin.so`
- macOS: `plugin/build/libRubinPlugin.dylib`

For a custom CGSim installation, pass its prefix to CMake:

```bash
cmake -S plugin -B plugin/build \
  -DCMAKE_PREFIX_PATH="$HOME/.local"
```

## Configure

Edit `config/rubin_config.json` before running. Update the plugin, workload, and output paths:

```json
{
  "Grid_Name": "GRID",
  "Sites_Information": "site_topology.json",
  "Sites_Connection_Information": "site_connections.json",
  "Dispatcher_Plugin": "../plugin/build/libRubinPlugin.so",
  "Limited_Sites": [],
  "Custom_Parameters": {
    "jobs_file": "../workload/quantum_graph_100_jobs.json",
    "output_file": "../output/events.db"
  }
}
```

Use `libRubinPlugin.dylib` on macOS.

## Run

Run CGSim from the `config` directory so the relative paths resolve correctly:

```bash
cd config
cg-sim -c rubin_config.json
```

Simulation events are written to `output/events.db` by default. Existing output databases are replaced when a new simulation starts.

## Workloads

Workloads are JSON dependency graphs stored in `workload/`. Select one with `Custom_Parameters.jobs_file` in `rubin_config.json`.

The included examples model this five-stage pipeline:

```text
isr → characterizeImage → calibrate → makeWarp → assembleCoadd
```

- `quantum_graph_100_jobs.json` contains 100 jobs across 20 data units, with 117 dependencies and additional fan-in between neighboring warp and coadd jobs.

Each job describes its task and data identity, requested cores, simulated FLOPs, input and output files, creation time, parents, and children. Root jobs have an initial `creation_time`; dependent jobs become eligible after their parents complete and the configured child `creation_delay` has elapsed.

A simplified job entry looks like this:

```json
{
  "jobid": 1,
  "task": "isr",
  "resource_key": "isr:LSSTCam",
  "cores": 2,
  "flops": 1095745,
  "creation_time": 9,
  "input_files": ["raw_visit_10000_detector_0.fits"],
  "output_files": {
    "postISRCCD_job_1_unit_0.root": 1330789834
  },
  "parents": [],
  "children": [
    {
      "jobid": 21,
      "creation_delay": 1,
      "dataset_type": "postISRCCD"
    }
  ]
}
```

The values are synthetic simulation inputs; they are not measured Rubin pipeline performance data.

## Scheduling

The dispatcher favors sites containing the most required input files, checks that enough output storage is available, and assigns the job to the first suitable CPU registered for that site.

## Regenerate Inputs

From the repository root:

```bash
python3 scripts/generate_site_topology.py
python3 scripts/generate_site_connections.py
python3 scripts/generate_workload.py
```

`generate_workload.py` currently uses `UNITS = 1`, writes `quantum_graph_1_jobs.json`, and retains some hard-coded 100-job metadata. Update those values together when changing the workload size.

To generate the workload DAG PDF, install Graphviz and run:

```bash
python3 scripts/plot.py
```

## Project Structure

```text
config/      CGSim topology, network, and runtime configuration
plugin/      C++ plugin source and CMake build files
scripts/     Workload, topology, connection, and DAG generators
workload/    Example workflow JSON files
output/      Generated SQLite event database
plot/        Generated workflow visualization
```

## License

Licensed under the [Apache License 2.0](LICENSE).
