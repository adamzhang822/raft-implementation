# On tests

To execute tests, put the test file in the repo root folder and make sure that the `PROGRAM_FILE_PATH` is pointing towards the `src/node.py`

If you are executing tests by invoking commands like `python3 src/node.py config.json 0`, please make sure the config file is in the root folder.

To execute tests detailed in `testing_report.md`, look for the corresponding config file in either `election_test_configs` or `log_replication_test_configs` under `test` folder. Make sure you start the system using these config files so that system enters the desired state for testing upon starting.

You can change the timer setting for election timer and heart beat timer in `src/raft/raft_node.py` if tests do not pass due to some time constraint.

