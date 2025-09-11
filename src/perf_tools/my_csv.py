import json

DEFAULT_METRICS = [ "Patch ID", "Execution", "Task Name", "Topology", "Test" ]
DEFAULT_STORAGE_METRICS = DEFAULT_METRICS + [ "Node" ]

def _check_headers_include_defaults(headers, defaults):
    missing = []
    for hdr in defaults:
        if hdr not in headers:
            missing.append('"' + hdr + '"')
    if missing:
        raise Exception("Headers list must include the following: [" + ",".join(missing) + "]")

def _get_summary_stats_as_csv(json_obj, tests, headers, accumulated_csv):
    _check_headers_include_defaults(headers, DEFAULT_METRICS)
    if isinstance(json_obj, list):
        for elem in json_obj:
            _get_summary_stats_as_csv(elem, tests, headers, accumulated_csv)
    elif isinstance(json_obj, dict):
        current_csv = {}
        for hdr in headers:
            current_csv[hdr] = None

        try:
            test_name = json_obj["info"]["test_name"]
            if not test_name in tests:
                return
            stats = json_obj["rollups"]["stats"]
            if not isinstance(stats, list):
                return

            current_csv["Patch ID"] = json_obj["info"]["version"]
            current_csv["Execution"] = json_obj["info"]["execution"]
            current_csv["Task Name"] = json_obj["info"]["task_name"]
            current_csv["Topology"] = json_obj["info"]["variant"]
            current_csv["Test"] = test_name

            for stat in stats:
                name = stat["name"]
                value = stat["val"]
                if name in headers and not name in DEFAULT_METRICS:
                    current_csv[name] = value
        except:
            pass

        for key, value in current_csv.items():
            accumulated_csv[key].append(value)

def _get_storage_stats_as_csv(json_obj, tests, headers, accumulated_csv):
    _check_headers_include_defaults(headers, DEFAULT_STORAGE_METRICS)
    if isinstance(json_obj, list):
        for elem in json_obj:
            _get_storage_stats_as_csv(elem, tests, headers, accumulated_csv)
    elif isinstance(json_obj, dict):
        current_csv = {}
        for hdr in headers:
            current_csv[hdr] = None

        try:
            test_name = json_obj["info"]["test_name"]
            if not test_name in tests:
                return
            stats = json_obj["rollups"]["stats"]
            if not isinstance(stats, list):
                return

            current_csv["Patch ID"] = json_obj["info"]["version"]
            current_csv["Execution"] = json_obj["info"]["execution"]
            current_csv["Task Name"] = json_obj["info"]["task_name"]
            current_csv["Topology"] = json_obj["info"]["variant"]
            current_csv["Test"] = test_name

            extra_args = json_obj["info"]["args"]
            if isinstance(extra_args, dict):
                current_csv["Node"] = json.dumps(extra_args)

            for stat in stats:
                name = stat["name"]
                value = stat["val"]
                if name in headers and not name in DEFAULT_METRICS:
                    current_csv[name] = value
        except:
            pass

        for key, value in current_csv.items():
            accumulated_csv[key].append(value)

def _print_csv(csv_dict, headers):
    for index in range(0, len(csv_dict[headers[0]])):
        counts=[]
        for hdr in headers:
            value = csv_dict[hdr][index]
            counts.append(str(value) if value is not None else "")
        print(",".join(counts))

def get_summary_stats_as_csv(json_obj, tests, headers, accumulated_csv):
    _get_summary_stats_as_csv(json_obj, tests, headers, accumulated_csv)

def get_storage_stats_as_csv(json_obj, tests, headers, accumulated_csv):
    _get_storage_stats_as_csv(json_obj, tests, headers, accumulated_csv)

def print_csv(csv_dict, headers):
    _print_csv(csv_dict, headers)
