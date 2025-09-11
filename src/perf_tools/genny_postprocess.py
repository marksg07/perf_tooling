
import requests
import os
import subprocess

from multiprocessing.pool import ThreadPool
from pathlib import Path

from my_csv import print_csv

def get_output_dir(workload, task_execution):
    return os.path.join(workload.workload_name, task_execution.version_id, task_execution.build_variant,
        task_execution.display_name, str(task_execution.execution))

def setup_output_dir(workload, task_execution):
    path = get_output_dir(workload, task_execution)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def fetch_ftdc_files(workload, task):
    if workload.genny_metrics is None:
        raise Exception(f"Must specify a genny_metrics element in config YAML to fetch ftdc artifacts")

    print("Fetch genny metrics: %s", task)
    tid = task.task_id
    try:
        rsp = requests.get(f"https://cedar.mongodb.com/rest/v1/perf/task_id/{tid}")
        rsp.raise_for_status()
    except:
        print(f"Cedar fetch failed for task {tid}")
        return


    print("Genny metrics: %s", rsp.text)
    json_obj = rsp.json()

    for obj in json_obj:
        test_name = obj["info"]["test_name"]
        if test_name not in workload.genny_metrics.tests:
            continue

        execution = obj["info"]["execution"]

        task_execution = task.get_execution(execution)
        dir_path = get_output_dir(workload, task_execution)

        path = os.path.join(dir_path, test_name)
        if os.path.exists(path):
            print(f"Artifact at {path} already exists. Skipping download.")
            continue

        try:
            uri = obj["artifacts"][0]["download_url"]
            print(f"Fetching {uri}...")
            rsp = requests.get(uri)
            rsp.raise_for_status()
        except:
            continue
        setup_output_dir(workload, task_execution)
        open(path, "wb").write(rsp.content)
        print(f"Saved artifact to {path}")

def _print_stats_csv(workload, task, metrics_obj):
    if not metrics_obj:
        raise Exception(f"No ${metrics_obj.yaml_name} YAML node to report summary stats")

    headers = metrics_obj.get_all_headers()
    csv_dict = {key: [] for key in headers}
    tid = task.task_id
    try:
        print(f'loading "https://cedar.mongodb.com/rest/v1/perf/task_id/{tid}"')
        rsp = requests.get(f"https://cedar.mongodb.com/rest/v1/perf/task_id/{tid}")
        rsp.raise_for_status()
    except:
        print('fail')
        return
    metrics_obj.get_stats_as_csv(rsp.json(), headers, csv_dict)
    print_csv(csv_dict, headers)

def print_genny_stats_csv(workload):
    def cb(workload, task):
        _print_stats_csv(workload, task, workload.genny_metrics)
    print(",".join(workload.genny_metrics.get_all_headers()))
    workload.iterate_tasks(cb)

def print_storage_stats_csv(workload):
    print(",".join(workload.storage_metrics.get_all_headers()))
    workload.iterate_tasks(lambda wld, tsk : _print_stats_csv(wld, tsk, wld.storage_metrics))

def print_timing_stats_csv(workload):
    print(",".join(workload.timing_metrics.get_all_headers()))
    workload.iterate_tasks(lambda wld, tsk : _print_stats_csv(wld, tsk, wld.timing_metrics))

def _ftdc_to_json(workload, ftdc_path):
    json_path = ftdc_path + ".json"
    if os.path.exists(json_path):
        print(f"Skipping conversion of {ftdc_path} as {json_path} already exists")
        return json_path
    print(f"Converting {ftdc_path} to JSON in {json_path}")
    fstream = open(json_path, "w", 1)
    cmd = [workload.curator_binpath, "ftdc", "export", "json", "--input", ftdc_path]
    proc = subprocess.Popen(cmd, stdout=fstream)
    proc.wait()
    fstream.close()
    return json_path

def _ftdc_to_csv(workload, ftdc_path):
    csv_path = ftdc_path + ".csv"
    if os.path.exists(csv_path):
        print(f"Skipping conversion of {ftdc_path} as {csv_path} already exists")
        return csv_path
    print(f"Converting {ftdc_path} to CSV in {csv_path}")
    fstream = open(csv_path, "w", 1)
    cmd = [workload.curator_binpath, "ftdc", "export", "csv", "--input", ftdc_path]
    proc = subprocess.Popen(cmd, stdout=fstream)
    proc.wait()
    fstream.close()
    return csv_path

def convert_ftdc_files(workload, format):
    if workload.genny_metrics is None:
        raise Exception(f"Must specify a genny_metrics element in config YAML to convert ftdc to ${format}")
    if workload.curator_binpath is None:
        raise Exception(f"Must specify a path to the curator binary in config YAML to convert ftdc to ${format}")
    print(f"curator is {workload.curator_binpath}")

    pool = ThreadPool(None)
    func = _ftdc_to_csv if format == "csv" else _ftdc_to_json
    try:
        for patch in workload.patches:
            for task in patch.task_executions:
                for x in range(task.execution + 1):
                    execution = task.get_execution(x)
                    destdir = get_output_dir(workload, execution)
                    if os.path.isdir(destdir):
                        for test_name in workload.genny_metrics.tests:
                            path = os.path.join(destdir, test_name)
                            if os.path.isfile(path):
                                pool.apply_async(func, (workload, path))
    except:
        pass
    finally:
        pool.close()
        pool.join()
