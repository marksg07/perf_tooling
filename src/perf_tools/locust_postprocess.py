import re
import tarfile

import os
import subprocess
import csv
import json

from contextlib import redirect_stdout
from pathlib import Path

from genny_postprocess import ftdc_to_json


YCSB_SUMMARY_STATS_CSV_FILENAME="perf_data.csv"
YCSB_WC_STATS_CSV_FILENAME="wc_data.csv"
YCSB_DIRS=["ycsb_load", "ycsb_100read", "ycsb_50read50update", "ycsb_100update", "ycsb_95read5update"]
LOCUST_HEADERS=['Type', 'Name', 'Request Count', 'Failure Count', 'Median Response Time', 'Average Response Time', 'Min Response Time', 'Max Response Time', 'Average Content Size', 'Requests/s', 'Failures/s', '50%', '66%', '75%', '80%', '90%', '95%', '98%', '99%', '99.9%', '99.99%', '100%']
STORAGE_HEADERS=['Name', 'Total Objects', 'Uncompressed Data Size', 'Compressed Data Size', 'Index Size', 'Total Compressed Size']
LOCUST_HISTORY_HEADERS=['Timestamp', 'User Count', 'Type', 'Name', 'Requests/s', 'Failures/s', '50%', '66%', '75%', '80%', '90%', '95%', '98%', '99%', '99.9%', '99.99%', '100%', 'Total Request Count', 'Total Failure Count', 'Total Median Response Time', 'Total Average Response Time', 'Total Min Response Time', 'Total Max Response Time', 'Total Average Content Size']

def get_output_dir(workload, task_execution):
    return os.path.join(workload.workload_name, task_execution.version_id, task_execution.build_variant,
        task_execution.display_name, str(task_execution.execution))

def setup_output_dir(workload, task_execution):
    path = get_output_dir(workload, task_execution)
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def download_and_extract_ts_dsi_artifacts(workload, task_execution):
    locust_file_base_regex = r'\.\/build\/WorkloadOutput\/reports-.*\/.*\/'
    stats_subregex = r'locust_output_.*stats.*\.csv'
    ftdc_subregex = r'mongod\.0\/diagnostic\.data\/metrics\.20.*'
    interesting_pattern = re.compile(f'^{locust_file_base_regex}(({stats_subregex})|({ftdc_subregex}))$')

    def _is_interesting_locust_file(path):
        return re.fullmatch(interesting_pattern, path)
    
    def _output_path(path):
        bn = os.path.basename(path)
        if 'locust_output_' in bn:
            return bn
        elif 'metrics.' in bn:
            _output_path.metric_n += 1
            if _output_path.metric_n > 1:
                raise Exception('Did not expect multiple metrics files')
            return 'metrics' 
        
    _output_path.metric_n = 0

    dirpath = get_output_dir(workload, task_execution)

    if task_execution.status != "success":
        print(f"Skipping {dirpath} because the task execution failed.")
        return

    for artifact in task_execution.artifacts:
        if "DSI Artifacts" not in artifact.name:
            continue
        tgz_path = os.path.join(dirpath, "dsi_artifact.tgz")
        if os.path.exists(tgz_path):
            print(f"Artifact at {tgz_path} already exists. Skipping download.")
        else:
            setup_output_dir(workload, task_execution)
            print(f"Downloading: {artifact.url} to {dirpath}/dsi_artifact.tgz")
            try:
                subprocess.run(["wget", "-O", tgz_path, artifact.url], stdout=subprocess.PIPE, check=True)
            except:
                print(f"Failed to download artifact from {artifact.url}")
                if os.path.exists(tgz_path):
                    os.remove(tgz_path)
                raise
        if os.path.exists(os.path.join(dirpath, 'metrics.json')):
            print('Already extracted')
        else:
            print(f'Extracting files from {tgz_path}')
            with tarfile.open(tgz_path, 'r:gz') as tarf:
                good_files = list(filter(_is_interesting_locust_file, tarf.getnames()))

                for fi in good_files:
                    contents = tarf.extractfile(fi).read()
                    with open(os.path.join(dirpath, _output_path(fi)), 'wb') as f:
                        f.write(contents)
            
            # Unpack metrics as json
            metrics_path = os.path.join(dirpath, 'metrics')
            assert(os.path.exists(metrics_path))
            ftdc_to_json(workload, metrics_path)
        return

def extract_good_from_artifacts(workload, task_execution):
    dirpath = get_output_dir(workload, task_execution)
    for artifact in task_execution.artifacts:
        if "DSI Artifacts" not in artifact.name:
            continue
        tgz_path = os.path.join(dirpath, "dsi_artifact.tgz")
        wld_output_path = os.path.join(dirpath, "WorkloadOutput")
        if not os.path.exists(tgz_path):
            print(f"Artifact at {tgz_path} does not exist, skipping {task_execution.display_name}")
            continue
        with tarfile.open(tgz_path, 'r:gz') as tarf:
            good_files = list(filter(lambda c: 'locust_output_stats.csv' in c or 'locust_output_db_stats.csv' in c, tarf.getnames()))
            assert len(good_files) == 2

            for fi in good_files:
                contents = tarf.extractfile(fi).read()
                with open(dirpath + os.path.basename(fi), 'wb') as f:
                    f.write(contents)

def print_ts_locust_stats_csv(workload):
    def cb(workload, task):
        dir = get_output_dir(workload, task)
        file = os.path.join(dir, 'locust_output_stats.csv')
        with open(file, 'r', newline='') as csvfile:
            csv_reader = csv.reader(csvfile)
            header = next(csv_reader)
            for row in csv_reader:
                print(','.join([task.display_name, str(task.execution)] + row))

    print(",".join(['Task Name', 'Execution'] + LOCUST_HEADERS))
    workload.iterate_tasks(cb)

def print_ts_locust_history_stats_csv(workload):
    def cb(workload, task):
        dir = get_output_dir(workload, task)
        file = os.path.join(dir, 'locust_output_stats_history.csv')
        with open(file, 'r', newline='') as csvfile:
            csv_reader = csv.reader(csvfile)
            header = next(csv_reader)
            for row in csv_reader:
                print(','.join([task.display_name, str(task.execution)] + row))

    print(",".join(['Task Name', 'Execution'] + LOCUST_HISTORY_HEADERS))
    workload.iterate_tasks(cb)

def print_ts_storage_stats_csv(workload):
    def cb(workload, task):
        dir = get_output_dir(workload, task)
        file = os.path.join(dir, 'locust_output_db_stats.csv')
        with open(file, 'r', newline='') as csvfile:
            csv_reader = csv.reader(csvfile)
            header = next(csv_reader)
            for row in csv_reader:
                print(','.join([task.display_name, str(task.execution)] + row))

    print(",".join(['Task Name', 'Execution'] + STORAGE_HEADERS))
    workload.iterate_tasks(cb)

def print_ts_basepaths_csv(workload):
    def cb(workload, task):
        dir = get_output_dir(workload, task)
        print(','.join([task.display_name, str(task.execution), dir]))

    print(",".join(['Task Name', 'Execution', 'Output Path']))
    workload.iterate_tasks(cb)