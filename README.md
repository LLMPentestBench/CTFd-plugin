# LLMPentestBench CTFd plugin

Built with Python 3.11, CTFd 3.8.4.

## Development
Don't hot reload the application when a run is in progress. This will exit the monitoring thread as soon as it can (at the time of writing, this is when either attempting to stop the Docker container, or when writing the finished status to the database, so still after the timeout). If not using gevent's monkey patching (e.g. running the `serve.py` script with `--disable-gevent`), it instead errors and exits when attempting to hot reload.
