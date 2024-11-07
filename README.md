# Server Coordinator

Server Coordinator is a lightweight assistant tool for coordinating server usage. It helps multiple users to know running jobs on certain servers, and to arrange performance-testing jobs in sequence without interference with other jobs.

Unlike other workload management system like sbatch, server coordinator doesn't have a controller to monitor resources between jobs. It just implements a exclusive/inclusive lock for each server.

## setup

    1. run a redis server on a server accessible for users
    2. set redis ip, port and password in server_coordinator.py
    3. This script depends on redis-py which can be installed by pip

## usage

### Shell script integration
```
    # for a performance test waiting until other tasks finishes
    python3 server_coordinator.py lock -s 42 49 -e
    # do your experiment
    python3 server_coordinator.py unlock -s 42 49 -e
```
### Python script integration
```
    # for a normal test you don't want to wait
    import server_coordinator
    c = server_coordinator.Coordinator()
    if c.trylock(["42", "49"], is_exclusive=False):
        try:
            # do your experiment
        except:
        finally:
            c.unlock(["42", "49"], is_exclusive=False)
```
### check locks on the cluster

```
  python3 server_coordinator.py check
```

## help

    # find help by
    python3 server_coordinator.py -h

## TODO

+ now multiple inclusive tasks may cause a exclusive task starving
+ no fairness, earlier task in line may run later
+ no input validation
