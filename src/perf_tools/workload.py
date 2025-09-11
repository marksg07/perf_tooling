import yaml

import multiprocessing as mp
from evergreen.api import EvergreenApi
from evergreen.config import get_auth

from my_csv import DEFAULT_METRICS, DEFAULT_STORAGE_METRICS
from my_csv import get_summary_stats_as_csv, get_storage_stats_as_csv

class TestAndMetrics:
    def __init__(self, cfg_node, yaml_name, default_metrics, csv_func):
        self.yaml_name = yaml_name
        self.csv_func = csv_func
        self.default_metrics = default_metrics
        metrics_node = cfg_node[yaml_name]
        assert "tests" in metrics_node
        assert "metrics" in metrics_node
        self.tests = metrics_node["tests"]
        self.selected_metrics= metrics_node["metrics"]
        assert isinstance(self.tests, list)
        assert isinstance(self.selected_metrics, list)
        for v in self.tests:
            assert isinstance(v, str)
        for v in self.selected_metrics:
            assert isinstance(v, str)

    def get_all_headers(self):
        return self.default_metrics + self.selected_metrics

    def get_stats_as_csv(self, json_obj, headers, csv_dict):
        self.csv_func(json_obj, self.tests, headers, csv_dict)


def worker_init(*args, **kwargs):
    global GLOBAL_SHARED_DATA
    GLOBAL_SHARED_DATA = dict(args)
    print(f"Worker initialized with: {GLOBAL_SHARED_DATA}")

def task_function(task):
    # Access the shared data within the task
    print('I am running!!!')
    for x in range(task.execution + 1):
        execution = task.get_execution(x)
        GLOBAL_SHARED_DATA['callback'](GLOBAL_SHARED_DATA['workload'], execution)
class Patch:
    def __init__(self, workload_name, patch_id, patch_cfg, api):
        self.patch_id = patch_id
        self.task_executions = []
        self.workload_name = workload_name

        # get the build info
        builds = api.builds_by_version(patch_id)

        # filter by the selected build variants
        filtered_builds = [x for x in builds if x.build_variant in patch_cfg]
        if len(filtered_builds) == 0:
            raise ValueError("Did not find any builds after filtering in the patch\nExpected: %s\nActual: %s\n:" % (patch_cfg, [x.build_variant for x in builds]))

        for build in filtered_builds:
            for task_id in build.tasks:
                task = api.task_by_id(task_id, fetch_all_executions=True)
                if task.display_name in patch_cfg[build.build_variant]:
                    self.task_executions.append(task)

        if len(self.task_executions) == 0:
            raise ValueError("Did not find any task executions")

    def iterate_executions(self, workload, callback):
        for task in self.task_executions:
            for x in range(task.execution + 1):
                execution = task.get_execution(x)
                callback(workload, execution)

    def parallel_iterate_executions(self, workload, callback):
        shared_ctx = {'workload': workload, 'callback': callback}
        with mp.Pool(16, initializer=worker_init, initargs=shared_ctx.items()) as p:
            p.map(task_function, self.task_executions)

    def iterate_tasks(self, workload, callback):
        for task in self.task_executions:
            callback(workload, task)

class WorkloadConfig:
    def __init__(self, cfgfile):
        self.workload_name=""
        self.patches_cfg={}
        self.patches=[]

        self.curator_binpath=None
        self.genny_metrics=None
        self.storage_metrics=None
        self.timing_metrics=None

        self._parse_config(cfgfile)
        self.evgauth = get_auth()
        # print("Auth: " + self.evgauth.username + ", " + self.evgauth.api_key)
        self.evgapi = EvergreenApi.get_api(self.evgauth)

        for patch_id, patch_cfg in self.patches_cfg.items():
            self.patches.append(Patch(self.workload_name, patch_id, patch_cfg, self.evgapi))

    def _parse_config(self, cfgfile):
        with open(cfgfile, "r") as fstream:
            y = yaml.safe_load(fstream)
            self.workload_name = y["workload_name"]
            self.patches_cfg = y["patches"]
            assert isinstance(self.workload_name, str)
            assert isinstance(self.patches_cfg, dict)

            if "genny_metrics" in y:
                self.genny_metrics = TestAndMetrics(y, "genny_metrics", DEFAULT_METRICS, get_summary_stats_as_csv)
            if "storage_metrics" in y:
                self.storage_metrics = TestAndMetrics(y, "storage_metrics", DEFAULT_STORAGE_METRICS, get_storage_stats_as_csv)
            if "timing_metrics" in y:
                self.timing_metrics = TestAndMetrics(y, "timing_metrics", DEFAULT_METRICS, get_summary_stats_as_csv)
            if "curator" in y:
                self.curator_binpath = y["curator"]
                assert isinstance(self.curator_binpath, str)

    def iterate_executions(self, callback):
        for p in self.patches:
            p.iterate_executions(self, callback)

    def parallel_iterate_executions(self, callback):
        for p in self.patches:
            p.parallel_iterate_executions(self, callback)

    def iterate_tasks(self, callback):
        for p in self.patches:
            p.iterate_tasks(self, callback)
