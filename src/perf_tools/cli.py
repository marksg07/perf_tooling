import sys

import pickle
from workload import WorkloadConfig
from genny_postprocess import print_genny_stats_csv, print_storage_stats_csv, print_timing_stats_csv
from genny_postprocess import fetch_ftdc_files, convert_ftdc_files
from ycsb_postprocess import YCSB_SUMMARY_STATS_CSV_FILENAME, YCSB_WC_STATS_CSV_FILENAME
from ycsb_postprocess import SUMMARY_STATS_HEADERS, WC_STATS_HEADERS
from ycsb_postprocess import download_and_extract_dsi_artifact
from ycsb_postprocess import update_ycsb_summary_stats_csv, force_update_ycsb_summary_stats_csv, print_ycsb_summary_stats_csv
from ycsb_postprocess import update_ycsb_wc_stats_csv, force_update_ycsb_wc_stats_csv, print_ycsb_wc_stats_csv
from locust_postprocess import print_ts_locust_stats_csv, print_ts_storage_stats_csv, download_and_extract_ts_dsi_artifacts

def usage():
    print(f"Usage: cli.py <COMMAND> <CONFIG_YML>\n")
    print(f"Commands:")
    print(f"  genny_stats       output Genny summary statistics as CSV")
    print(f"  storage_stats     output storage statistics as CSV")
    print(f"  timing_stats      output timing statistics as CSV")
    print(f"  fetch_ftdc        download FTDC files from Genny test executions")
    print(f"  fetch_artifacts   download DSI artifacts from Genny/YCSB test executions")
    print(f"  update_ycsb_summary_stats")
    print(f"                    update the {YCSB_SUMMARY_STATS_CSV_FILENAME} file for all WorkloadOutputs in the")
    print(f"                    workload's artifacts directory tree that does not have one.")
    print(f"                    The data written is the CSV summary stats from YCSB output logs.")
    print(f"  update_all_ycsb_summary_stats")
    print(f"                    update the {YCSB_SUMMARY_STATS_CSV_FILENAME} file for all WorkloadOutputs in the")
    print(f"                    workload's artifacts directory tree with the latest YCSB summary stats")
    print(f"                    from YCSB output logs")
    print(f"  ycsb_stats        output the contents of all {YCSB_SUMMARY_STATS_CSV_FILENAME} files in the artifacts")
    print(f"                    directory tree")
    print(f"  update_ycsb_wc_stats")
    print(f"                    updatee the {YCSB_WC_STATS_CSV_FILENAME} file for all WorkloadOutputs in the")
    print(f"                    workload's artifacts directory tree that does not have one.")
    print(f"                    The data written is the CSV write conflict stats from YCSB output logs.")
    print(f"  update_all_ycsb_wc_stats")
    print(f"                    update the {YCSB_WC_STATS_CSV_FILENAME} file for all WorkloadOutputs in the")
    print(f"                    workload's artifacts directory tree with the latest YCSB write conflict stats")
    print(f"                    from YCSB output logs")
    print(f"  ycsb_wc_stats     output the contents of all {YCSB_WC_STATS_CSV_FILENAME} files in the artifacts")
    print(f"                    directory tree")
    print(f"  ftdc_to_json      convert FTDC files to JSON files")
    print(f"  ftdc_to_csv       convert FTDC files to CSV files")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        usage()
        raise Exception(f"Need a command and a YAML file")

    cmd = sys.argv[1]
    cfg = sys.argv[2]
    if cfg.endswith('.pkl'):
        with open(cfg, 'rb') as f:
            wld = pickle.load(f)
    else:
        wld = WorkloadConfig(cfg)
        import pickle
        with open(cfg + '.pkl', 'wb') as f:
            pickle.dump(wld, f)

    if cmd == "genny_stats":
        print_genny_stats_csv(wld)
    elif cmd == "storage_stats":
        print_storage_stats_csv(wld)
    elif cmd == "timing_stats":
        print_timing_stats_csv(wld)
    elif cmd == "fetch_ftdc":
        wld.iterate_tasks(fetch_ftdc_files)
    elif cmd == "ftdc_to_json":
        convert_ftdc_files(wld, "json")
    elif cmd == "ftdc_to_csv":
        convert_ftdc_files(wld, "csv")
    elif cmd == "fetch_artifacts":
        wld.iterate_executions(download_and_extract_dsi_artifact)
    elif cmd == 'fetch_ts_artifacts':
        wld.parallel_iterate_executions(download_and_extract_ts_dsi_artifacts)
    elif cmd == 'ts_storage_stats':
        print_ts_storage_stats_csv(wld)
    elif cmd == 'ts_locust_stats':
        print_ts_locust_stats_csv(wld)
    elif cmd == "update_ycsb_summary_stats":
        wld.iterate_executions(update_ycsb_summary_stats_csv)
    elif cmd == "update_all_ycsb_summary_stats":
        wld.iterate_executions(force_update_ycsb_summary_stats_csv)
    elif cmd == "ycsb_stats":
        print(",".join(SUMMARY_STATS_HEADERS))
        wld.iterate_executions(print_ycsb_summary_stats_csv)
    elif cmd == "update_ycsb_wc_stats":
        wld.iterate_executions(update_ycsb_wc_stats_csv)
    elif cmd == "update_all_ycsb_wc_stats":
        wld.iterate_executions(force_update_ycsb_wc_stats_csv)
    elif cmd == "ycsb_wc_stats":
        print(",".join(WC_STATS_HEADERS))
        wld.iterate_executions(print_ycsb_wc_stats_csv)
    else:
        usage()
        raise Exception(f"Unknown command: {cmd}")
