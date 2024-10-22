import pandas as pd

from .config import get_config
from .train_types import (
    SYSTEM_FEATURES,
    WORKLOAD_FEATURES,
    FeatureGroup,
    FeatureGroups,
    deep_sort,
    get_valid_feature_groups,
)

PROM_SERVER = get_config("PROM_SERVER", "http://localhost:9090")
PROM_SSL_DISABLE = get_config("PROM_SSL_DISABLE", True)
PROM_QUERY_INTERVAL = get_config("PROM_QUERY_INTERVAL", 300)
PROM_QUERY_STEP = get_config("PROM_QUERY_STEP", 3)

PROM_THIRDPARTY_METRICS = get_config("PROM_THIRDPARTY_METRICS", list[str]([]))
VM_JOB_NAME = get_config("VM_JOB_NAME", "vm")

metric_prefix = "kepler_"
TIMESTAMP_COL = "timestamp"
PACKAGE_COL = "package"
SOURCE_COL = "source"
MODE_COL = "mode"

container_query_prefix = "kepler_container"
container_query_suffix = "total"
process_query_prefix = "kepler_process"
process_query_suffix = "total"

node_query_prefix = "kepler_node"
node_query_suffix = "joules_total"
vm_query_prefix = "kepler_vm"
vm_query_suffix = "joules_total"

usage_ratio_query = "kepler_container_cpu_usage_per_package_ratio"
# mostly available
valid_container_query = "kepler_container_bpf_cpu_time_ms_total"
node_info_query = "kepler_node_node_info"
cpu_frequency_info_query = "kepler_node_cpu_scaling_frequency_hertz"

container_id_cols = ["container_id", "pod_name", "container_name", "container_namespace"]
process_id_cols = ["container_id", "pid"]
node_info_column = "node_type"
pkg_id_column = "pkg_id"


def get_energy_unit(component):
    if component in ["package", "core", "uncore", "dram"]:
        return "package"
    return None


def feature_to_query(feature, use_process=False):
    if feature in SYSTEM_FEATURES:
        return f"{node_query_prefix}_{feature}"
    if feature in FeatureGroups[FeatureGroup.AcceleratorOnly]:
        return f"{node_query_prefix}_{feature}"
    if FeatureGroup.ThirdParty in FeatureGroups is not None and feature in FeatureGroups[FeatureGroup.ThirdParty]:
        return feature
    if use_process:
        return f"{process_query_prefix}_{feature}_{process_query_suffix}"
    return f"{container_query_prefix}_{feature}_{container_query_suffix}"


def energy_component_to_query(component):
    return f"{node_query_prefix}_{component}_{node_query_suffix}"


def vm_energy_component_to_query(component):
    return f"{vm_query_prefix}_{component}_{vm_query_suffix}"


def update_thirdparty_metrics(metrics):
    global FeatureGroups
    FeatureGroups[FeatureGroup.ThirdParty] = metrics
    FeatureGroups[FeatureGroup.WorkloadOnly] = deep_sort(WORKLOAD_FEATURES + metrics)


def get_valid_feature_group_from_queries(queries):
    all_workload_features = FeatureGroups[FeatureGroup.WorkloadOnly]
    features = [feature for feature in all_workload_features if feature_to_query(feature) in queries]
    return get_valid_feature_groups(features)


def split_container_id_column(container_id):
    split_values = dict()
    splits = container_id.split("/")
    if len(splits) != len(container_id_cols):
        # failed to split
        return None
    index = 0
    for col_name in container_id_cols:
        split_values[col_name] = splits[index]
        index += 1
    return split_values


def get_container_name_from_id(container_id):
    split_values = split_container_id_column(container_id)
    if split_values is None:
        return None
    return split_values["container_name"]


def generate_dataframe_from_response(query_metric, prom_response):
    items = []
    for res in prom_response:
        metric_item = res["metric"]
        for val in res["values"]:
            # labels
            item = metric_item.copy()
            # timestamp
            item[TIMESTAMP_COL] = val[0]
            # value
            item[query_metric] = float(val[1])
            items += [item]
    df = pd.DataFrame(items)
    return df


def prom_responses_to_results(prom_responses):
    results = dict()
    for query_metric, prom_response in prom_responses.items():
        results[query_metric] = generate_dataframe_from_response(query_metric, prom_response)
    return results
