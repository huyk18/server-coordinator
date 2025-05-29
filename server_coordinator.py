#! /bin/python3

"""
server coordinator: help to use servers efficiently

written by huyk, 2024/10/30

help

    # find help by
    python3 server_coordinator.py -h

setup

    1. Guarantee the redis_server can be accessed.
    2. This script depends on redis-py which can be installed by pip

usage

    Shell

        # for a performance test waiting until other tasks finishes
        python3 server_coordinator.py lock -s 42 49 -e
        # do your experiment
        python3 server_coordinator.py unlock -s 42 49 -e

    Python

        # for a normal test you don't want to wait
        import server_coordinator
        c = server_coordinator.Coordinator()
        # if you want to wait for the lock, use c.lock instead
        if c.trylock(["42", "49"], is_exclusive=False):
            try:
                # do your experiment
            except:
            finally:
                c.unlock(["42", "49"], is_exclusive=False)
        else:
            print("failed to acquire server_coordinator's lock")

TODO

    now multiple inclusive tasks may cause a exclusive task starving
    no fairness
    earlier task in line may run later
    no server ip validation
"""

import redis
import argparse
import getpass
import time

default_redis_ip = "***REMOVED***"
default_redis_port = 6380
default_redis_passwd = "***REMOVED***"
namespace = "server_coordinator"
user = getpass.getuser()

list_key_suffix = "_user_list"


class Coordinator:
    def __init__(
        self,
        redis_ip=default_redis_ip,
        port=default_redis_port,
        password=default_redis_passwd,
    ):
        self.rs = redis.Redis(
            host=default_redis_ip,
            port=default_redis_port,
            decode_responses=True,
            password=password,
        )
        assert self.rs is not None

    def __trylock_inclusive_server(self, server):
        lock_key = namespace + server
        if self.rs.setnx(lock_key, "inclusive_locked") == 1:
            self.rs.lpush(lock_key + list_key_suffix, user)
            return True
        else:
            with self.rs.pipeline() as pipe:
                while True:
                    try:
                        pipe.watch(lock_key + list_key_suffix)
                        pipe.watch(lock_key)
                        ret = pipe.get(lock_key)
                        pipe.multi()
                        if ret == "inclusive_locked":
                            pipe.lpush(lock_key + list_key_suffix, user)
                            pipe.execute()
                            return True
                        else:
                            pipe.execute()
                            return False
                    except redis.WatchError:
                        continue

    def __unlock_inclusive_server(self, server):
        lock_key = namespace + server
        if self.rs.lrem(lock_key + list_key_suffix, 1, user) != 1:
            print("failed to unlock", server)
            return
        with self.rs.pipeline() as pipe:
            while True:
                try:
                    pipe.watch(lock_key + list_key_suffix)
                    pipe.watch(lock_key)
                    ret = pipe.llen(lock_key + list_key_suffix)
                    pipe.multi()
                    if ret == 0:
                        pipe.delete(lock_key)
                    pipe.execute()
                    break
                except redis.WatchError as e:
                    print(e)
                    continue

    def trylock(self, servers: list, is_exclusive: bool):
        locked_servers = []
        if is_exclusive:
            for server in sorted(servers):
                key = namespace + server
                if self.rs.setnx(key, user + "_exclusive_locked") == 1:
                    locked_servers.append(key)
                else:
                    break
            else:
                return True
            if locked_servers:
                self.rs.delete(*locked_servers)
            return False
        else:
            for server in sorted(servers):
                if self.__trylock_inclusive_server(server):
                    locked_servers.append(server)
                else:
                    break
            else:
                return True
            for server in locked_servers:
                self.__unlock_inclusive_server(server)
            return False

    def lock(self, servers: list, is_exclusive: bool):
        while not self.trylock(servers, is_exclusive):
            time.sleep(5)

    def unlock(self, servers: list, is_exclusive: bool):
        if is_exclusive:
            for server in sorted(servers):
                if self.rs.delete(namespace + server) != 1:
                    print("failed to unlock", server)
        else:
            for server in sorted(servers):
                self.__unlock_inclusive_server(server)

    def check(self):
        k_list = self.rs.keys(namespace + "*")
        if not k_list:
            print("no lock found")
        for k in k_list:
            if k.endswith(list_key_suffix):
                v = self.rs.lrange(k, 0, -1)
            else:
                v = self.rs.get(k)
            print(k, v)

    def unlockall(self):
        k_list = self.rs.keys(namespace + "*")
        if k_list:
            self.rs.delete(*k_list)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="coordinate the use of servers by a lock manner"
    )
    parser.add_argument(
        "COMMAND",
        choices=["lock", "trylock", "check", "unlock", "unlockall"],
        help="NOTE that unlockall will unlock locks of all users, don't use it except for debugging",
    )
    parser.add_argument(
        "-s",
        "--servers",
        type=str,
        nargs="*",
        help="the last byte of servers' ip to use, for example, to use 114.114.114.49 and 172.168.0.42, input two arguments with space: -s 42 49",
    )
    parser.add_argument("-m", "--redis_ip", type=str, default="114.114.114.49")
    parser.add_argument("-p", "--redis_port", type=int, default=11211)
    parser.add_argument(
        "-e",
        "--exclusive_use",
        help="set this will forbid multiple users on the servers, for performance experiment",
        action="store_true",
    )
    args = parser.parse_args()
    c = Coordinator(
        args.redis_ip if args.redis_ip is not None else default_redis_ip,
        args.redis_port if args.redis_port is not None else default_redis_port,
        default_redis_passwd,
    )

    if args.COMMAND in ["lock", "trylock", "unlock"] and args.servers is None:
        print("no servers to lock or unlock")
        exit(-1)
    if args.COMMAND == "lock":
        c.lock(args.servers, args.exclusive_use)
    elif args.COMMAND == "trylock":
        if not c.trylock(args.servers, args.exclusive_use):
            print("failed to acquire lock")
            c.check()
    elif args.COMMAND == "check":
        c.check()
    elif args.COMMAND == "unlock":
        c.unlock(args.servers, args.exclusive_use)
    elif args.COMMAND == "unlockall":
        c.unlockall()
    else:
        print("unexpect command", args.COMMAND)
        exit(-1)
