
import os
import subprocess

from contextlib import redirect_stdout
from pathlib import Path

from my_csv import print_csv

YCSB_SUMMARY_STATS_CSV_FILENAME="perf_data.csv"
YCSB_WC_STATS_CSV_FILENAME="wc_data.csv"
YCSB_DIRS=["ycsb_load", "ycsb_100read", "ycsb_50read50update", "ycsb_100update", "ycsb_95read5update"]
SUMMARY_STATS_HEADERS=[
    "Patch ID", "Execution", "Task Name", "Topology", "Test",
    "Overall RunTime(ms)", "Overall Throughput(ops/sec)",
    "Insert Operations", "Insert AverageLatency(us)", "Insert MinLatency(us)",
    "Insert MaxLatency(us)", "Insert 95thPercentileLatency(us)",
    "Insert 99thPercentileLatency(us)", "Read Operations", "Read AverageLatency(us)",
    "Read MinLatency(us)", "Read MaxLatency(us)", "Read 95thPercentileLatency(us)",
    "Read 99thPercentileLatency(us)", "Update Operations", "Update AverageLatency(us)",
    "Update MinLatency(us)", "Update MaxLatency(us)", "Update 95thPercentileLatency(us)",
    "Update 99thPercentileLatency(us)"
]
WC_STATS_HEADERS=["Patch ID", "Execution", "Task Name", "Topology"] + YCSB_DIRS

def get_output_dir(workload, task_execution):
    return os.path.join(workload.workload_name, task_execution.version_id, task_execution.build_variant,
        task_execution.display_name, str(task_execution.execution))

def setup_output_dir(workload, task_execution):
    path = get_output_dir(workload, task_execution)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def download_and_extract_dsi_artifact(workload, task_execution):
    dirpath = get_output_dir(workload, task_execution)

    def _try_untar(taskdir):
        if os.path.exists(os.path.join(taskdir, "WorkloadOutput")):
            return
        tgzfile = os.path.join(taskdir,"dsi_artifact.tgz")
        print(f"Unpacking {tgzfile}...")
        subprocess.run(["tar", "-C", taskdir, "-xvzf", tgzfile],
            stdout=subprocess.PIPE, check=True)

    def _try_wget(tgz_path, url):
        subprocess.run(["wget", "-O", tgz_path, url], stdout=subprocess.PIPE, check=True)

    if task_execution.status != "success":
        print(f"Skipping {dirpath} because the task execution failed.")
        return

    for artifact in task_execution.artifacts:
        if "DSI Artifacts" not in artifact.name:
            continue
        tgz_path = os.path.join(dirpath, "dsi_artifact.tgz")
        wld_output_path = os.path.join(dirpath, "WorkloadOutput")
        if os.path.exists(tgz_path):
            print(f"Artifact at {tgz_path} already exists. Skipping download.")
            _try_untar(dirpath)
        elif os.path.exists(wld_output_path):
            print(f"{wld_output_path} already exists. Skipping download.")
        else:
            setup_output_dir(workload, task_execution)
            print(f"Downloading: {artifact.url} to {dirpath}/dsi_artifact.tgz")
            try:
                _try_wget(tgz_path, artifact.url)
            except:
                print(f"Failed to download artifact from {artifact.url}")
                if os.path.exists(tgz_path):
                    os.remove(tgz_path)
                raise
            _try_untar(dirpath)
            os.remove(tgz_path)
        return

def update_ycsb_summary_stats_csv(workload, task_execution, force_update=False):
    dirpath = get_output_dir(workload, task_execution)
    csvpath = os.path.join(dirpath, YCSB_SUMMARY_STATS_CSV_FILENAME)
    reportsdir = os.path.join(dirpath, "WorkloadOutput", "reports")

    if not os.path.isdir(reportsdir):
        return
    if os.path.isfile(csvpath) and not force_update:
        return

    print(f"Updating {csvpath}")

    csv_table = {hdr: [] for hdr in SUMMARY_STATS_HEADERS}
    metrics_regex="(Operations|RunTime\\(ms\\)|Throughput\\(ops\\/sec\\)|(Average|Min|Max|95thPercentile|99thPercentile)Latency\\(us\\))"
    regex=f"\\[(OVERALL|INSERT|READ|UPDATE)\\], {metrics_regex}, [0-9.]+"

    for dir in YCSB_DIRS:
        csv_row={hdr: None for hdr in SUMMARY_STATS_HEADERS}
        csv_row["Patch ID"] = task_execution.version_id
        csv_row["Execution"] = task_execution.execution
        csv_row["Task Name"] = task_execution.display_name
        csv_row["Topology"] = task_execution.build_variant
        csv_row["Test"] = dir
        logpath = os.path.join(reportsdir, dir, "test_output.log")

        with subprocess.Popen(["egrep", "-o", regex, logpath], stdout=subprocess.PIPE, universal_newlines=True) as egrep:
            for line in egrep.stdout:
                # Each line is a 3-column CSV: (eg. "[OVERALL], Operations, 100000")
                cols = [x.strip() for x in line.split(",")]

                # Combine column 0 & 1 values to a metric key (e.g "Overall Operations")
                key = cols[0][1] + cols[0][2:len(cols[0])-1].lower() + " " + cols[1]
                csv_row[key] = cols[2]
        for key, value in csv_row.items():
            csv_table[key].append(value)

    with open(csvpath, "w") as fstream:
        with redirect_stdout(fstream):
            print(",".join(SUMMARY_STATS_HEADERS))
            print_csv(csv_table, SUMMARY_STATS_HEADERS)

def force_update_ycsb_summary_stats_csv(workload, task_execution):
    update_ycsb_summary_stats_csv(workload, task_execution, True)

def print_ycsb_summary_stats_csv(workload, task_execution, include_headers=False):
    dirpath = get_output_dir(workload, task_execution)
    csvpath = os.path.join(dirpath, YCSB_SUMMARY_STATS_CSV_FILENAME)
    if not os.path.isfile(csvpath):
        return
    with open(csvpath, "r") as fstream:
        if not include_headers:
            fstream.readline()
        for k in fstream:
            print(k.strip())

def _grep_writeconflict_count(logpath):
    regex = "WriteConflict.*Please retry your operation"
    if not os.path.isfile(logpath):
        return None
    with subprocess.Popen(["egrep", "-c", regex, logpath], stdout=subprocess.PIPE, universal_newlines=True) as grep:
        for line in grep.stdout:
            try:
                return int(line.strip())
            except:
                return None

def update_ycsb_wc_stats_csv(workload, task_execution, force_update=False):
    dirpath = get_output_dir(workload, task_execution)
    csvpath = os.path.join(dirpath, YCSB_WC_STATS_CSV_FILENAME)
    reportsdir = os.path.join(dirpath, "WorkloadOutput", "reports")
    sharded="shard" in task_execution.build_variant

    if not os.path.isdir(reportsdir):
        return
    if os.path.isfile(csvpath) and not force_update:
        return
    if task_execution.status != "success":
        print(f"Skipping {dirpath} because the task execution failed.")
        return

    print(f"Updating {csvpath}")

    csv_table = {hdr: [] for hdr in WC_STATS_HEADERS}

    for phase in YCSB_DIRS:
        logpath = os.path.join(reportsdir, phase, "mongod.0", "mongod.log")
        count = _grep_writeconflict_count(logpath)
        if count is None:
            return
        if sharded:
            logpath = os.path.join(dirpath, "WorkloadOutput", "reports", phase, "mongod.2", "mongod.log")
            s2_count = _grep_writeconflict_count(logpath)
            if s2_count is None:
                return
            count += s2_count
        csv_table[phase].append(str(count))

    csv_table["Patch ID"].append(task_execution.version_id)
    csv_table["Execution"].append(task_execution.execution)
    csv_table["Task Name"].append(task_execution.display_name)
    csv_table["Topology"].append(task_execution.build_variant)

    with open(csvpath, "w") as fstream:
        with redirect_stdout(fstream):
            print(",".join(WC_STATS_HEADERS))
            print_csv(csv_table, WC_STATS_HEADERS)

def force_update_ycsb_wc_stats_csv(workload, task_execution):
    update_ycsb_wc_stats_csv(workload, task_execution, True)

def print_ycsb_wc_stats_csv(workload, task_execution, include_headers=False):
    dirpath = get_output_dir(workload, task_execution)
    csvpath = os.path.join(dirpath, YCSB_WC_STATS_CSV_FILENAME)
    if not os.path.isfile(csvpath):
        return
    with open(csvpath, "r") as fstream:
        if not include_headers:
            fstream.readline()
        for k in fstream:
            print(k.strip())
