"""
Assign collectors to tasks using round-robin per (team, branch_sk),
respecting max_daily_cases per collector.
"""
import pandas as pd
from models.model1_channel import CHANNEL_TO_TEAM


def assign_collectors(
    tasks_df: pd.DataFrame,
    collectors_df: pd.DataFrame
) -> pd.DataFrame:
    """
    tasks_df     – must have: assigned_channel, branch_sk, priority_rank
    collectors_df – from dim_collector: collector_sk, collector_name,
                    team, branch_sk, max_daily_cases, is_active

    Returns tasks_df with collector_sk and collector_name columns added.
    """
    tasks_df = tasks_df.copy()
    tasks_df["collector_sk"]   = None
    tasks_df["collector_name"] = None

    active = collectors_df[collectors_df["is_active"] == 1].copy()

    # Group collectors by (team, branch_sk)
    groups: dict[tuple, list] = {}
    for _, c in active.iterrows():
        key = (str(c["team"]), int(c["branch_sk"]))
        groups.setdefault(key, []).append({
            "collector_sk":   int(c["collector_sk"]),
            "collector_name": str(c["collector_name"]),
            "max_cases":      int(c["max_daily_cases"]),
            "assigned":       0,
        })

    # Round-robin pointers per group
    pointers: dict[tuple, int] = {k: 0 for k in groups}

    # Sort tasks by priority_rank (most urgent first = gets assigned first)
    task_index = tasks_df.sort_values("priority_rank").index

    for idx in task_index:
        channel   = tasks_df.at[idx, "assigned_channel"]
        branch_sk = int(tasks_df.at[idx, "branch_sk"]) if pd.notna(tasks_df.at[idx, "branch_sk"]) else 1
        team      = CHANNEL_TO_TEAM.get(str(channel))

        if team is None:
            continue  # ON_TIME tasks don't need a collector

        key = (team, branch_sk)
        collectors = groups.get(key)

        # Fallback: try same team in any branch
        if not collectors:
            for k, v in groups.items():
                if k[0] == team and v:
                    collectors = v
                    key = k
                    break

        if not collectors:
            continue

        # Round-robin through collectors in the group
        ptr   = pointers[key]
        start = ptr
        assigned = False
        while True:
            c = collectors[ptr % len(collectors)]
            if c["assigned"] < c["max_cases"]:
                tasks_df.at[idx, "collector_sk"]   = c["collector_sk"]
                tasks_df.at[idx, "collector_name"] = c["collector_name"]
                c["assigned"] += 1
                pointers[key] = (ptr + 1) % len(collectors)
                assigned = True
                break
            ptr = (ptr + 1) % len(collectors)
            if ptr == start:
                break  # all collectors in group are full

    return tasks_df
