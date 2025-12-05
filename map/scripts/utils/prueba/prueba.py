from taskManager import DownloadManager

if __name__ == "__main__":
    manager = DownloadManager()
    manager.create_scheduled_task(run_at="00:34")
