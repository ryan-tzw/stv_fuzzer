import pandas as pd
import matplotlib.pyplot as plt


def create_coverage_graph(data, folder_dir):
    df = pd.DataFrame(data, columns=["timestamp", "total_edges"])

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["elapsed_seconds"] = (
        df["timestamp"] - df["timestamp"].iloc[0]
    ).dt.total_seconds()

    plt.figure()
    plt.plot(df["elapsed_seconds"], df["total_edges"], marker="o", color="blue")
    plt.xlabel("Time")
    plt.ylabel("Total Edges")
    plt.title("Coverage Over Time")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(folder_dir / "coverage_over_time.png", dpi=300)
    plt.close()


def create_unique_graph(data, folder_dir):
    df = pd.DataFrame(data, columns=["timestamp", "unique_crashes"])

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["elapsed_seconds"] = (
        df["timestamp"] - df["timestamp"].iloc[0]
    ).dt.total_seconds()

    plt.figure()
    plt.plot(df["elapsed_seconds"], df["unique_crashes"], marker="o", color="red")
    plt.xlabel("Time")
    plt.ylabel("Unique Crashes")
    plt.title("Unique Crashes Over Time")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(folder_dir / "unique_bugs_over_time.png", dpi=300)
    plt.close()


def create_interesting_graph(data, folder_dir):
    df = pd.DataFrame(data, columns=["timestamp", "interesting_seed"])

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["elapsed_seconds"] = (
        df["timestamp"] - df["timestamp"].iloc[0]
    ).dt.total_seconds()

    plt.figure()
    plt.plot(df["elapsed_seconds"], df["interesting_seed"], marker="o", color="green")
    plt.xlabel("Time")
    plt.ylabel("Interesting Seed")
    plt.title("Interesting Seed Over Time")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(folder_dir / "interesting_seed_over_time.png", dpi=300)
    plt.close()
