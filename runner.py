'''run experiments
'''

import time
from subprocess import Popen, PIPE


def set_memory_adaptive(args: list, memory_adaptive: int) -> list:
    return args + ["-ma", str(memory_adaptive)]

def set_update_prob(args: list) -> list:
    return args + ["-up"]

def set_node_seed(args: list, seed: int) -> list:
    return args + ["-ns", str(seed)]

def set_queue_seed(args: list, seed: int) -> list:
    return args + ["-qs", str(seed)]

def set_nodes(args: list, node: int) -> list:
    return args + ["-n", str(node)]

def set_strategy(args: list, strategy: str) -> list:
    return args + ["-s", strategy]

def set_purify(args: list) -> list:
    return args + ["-pf"]


def get_output(p: Popen):
    stderr = p.stderr.readlines()
    if stderr:
        for line in stderr:
            print(line)
    
    stdout = p.stdout.readlines()
    if stdout:
        for line in stdout:
            print(line)


def main_9_13_24():

    tasks = []

    command = ['python', 'main.py']
    base_args = ["-tp", "as", "-t", "200", "-d", "log/9.13.24"]

    nodes = [100]
    memory_adaptive = [0, 5]
    seed = list(range(20))
    update_prob = [False, True]
    for n in nodes:
        for ma in memory_adaptive:
            for up in update_prob:
                for s in seed:
                    if ma == 0 and up == True:
                        continue
                    
                    args = set_nodes(base_args, n)
                    args = set_memory_adaptive(args, ma)
                    if up:
                        args = set_update_prob(args)
                    ###
                    # args = set_node_seed(args, s)
                    args = set_queue_seed(args, s)
                    ###
                    tasks.append(command + args)

    parallel = 8
    ps = []       # processes current running
    while len(tasks) > 0 or len(ps) > 0:
        if len(ps) < parallel and len(tasks) > 0:
            task = tasks.pop(0)
            print(task, f'{len(tasks)} still in queue')
            ps.append(Popen(task, stdout=PIPE, stderr=PIPE))
        else:
            time.sleep(0.05)
            new_ps = []
            for p in ps:
                if p.poll() is None:
                    new_ps.append(p)
                else:
                    get_output(p)
            ps = new_ps


def main_10_14_24():

    tasks = []

    ###### for 2 node line topology ########
    command = ['python', 'main.py']
    base_args = ["-tp", "line", "-n", "2", "-t", "100", "-d", "log/10.14.24.2"]

    memory_adaptive = [0, 5]
    seed = list(range(20))

    for ma in memory_adaptive:
        if ma == 0:
            for s in seed:
                args = set_memory_adaptive(base_args, ma)
                args = set_node_seed(args, s)
                tasks.append(command + args)
        else:
            for strategy in ['random', 'freshest']:
                for s in seed:
                    args = set_strategy(base_args, strategy)
                    args = set_memory_adaptive(args, ma)
                    args = set_node_seed(args, s)
                    tasks.append(command + args)


    parallel = 8
    ps = []       # processes current running
    while len(tasks) > 0 or len(ps) > 0:
        if len(ps) < parallel and len(tasks) > 0:
            task = tasks.pop(0)
            print(task, f'{len(tasks)} still in queue')
            ps.append(Popen(task, stdout=PIPE, stderr=PIPE))
        else:
            time.sleep(0.05)
            new_ps = []
            for p in ps:
                if p.poll() is None:
                    new_ps.append(p)
                else:
                    get_output(p)
            ps = new_ps


    ###### for 100 node as topology ########
    # command = ['python', 'main.py']
    # base_args = ["-tp", "as", "-n", "100", "-t", "207", "-d", "log/10.14.24.2"]

    # memory_adaptive = [0, 5]
    # seed = list(range(20))

    # for ma in memory_adaptive:
    #     if ma == 0:
    #         for s in seed:
    #             args = set_memory_adaptive(base_args, ma)
    #             args = set_queue_seed(args, s)
    #             tasks.append(command + args)
    #     else:
    #         for update in [False, True]:
    #             for s in seed:
    #                 if update:
    #                     args = set_update_prob(base_args)
    #                 args = set_memory_adaptive(args, ma)
    #                 args = set_queue_seed(args, s)
    #                 tasks.append(command + args)

    # parallel = 8
    # ps = []       # processes current running
    # while len(tasks) > 0 or len(ps) > 0:
    #     if len(ps) < parallel and len(tasks) > 0:
    #         task = tasks.pop(0)
    #         print(task, f'{len(tasks)} still in queue')
    #         ps.append(Popen(task, stdout=PIPE, stderr=PIPE))
    #     else:
    #         time.sleep(0.05)
    #         new_ps = []
    #         for p in ps:
    #             if p.poll() is None:
    #                 new_ps.append(p)
    #             else:
    #                 get_output(p)
    #         ps = new_ps


def main_10_30_24():

    tasks = []

    ###### for 2 node line topology ########
    command = ['python', 'main.py']
    base_args = ["-tp", "line", "-n", "2", "-t", "100", "-d", "log/10.30.24"]

    memory_adaptive = [0, 5]
    seed = list(range(20))

    for ma in memory_adaptive:
        if ma == 0:
            for s in seed:
                args = set_memory_adaptive(base_args, ma)
                args = set_node_seed(args, s)
                tasks.append(command + args)
        else:
            for strategy in ['freshest']:
                for s in seed:
                    for pf in [False, True]:
                        args = set_strategy(base_args, strategy)
                        args = set_memory_adaptive(args, ma)
                        args = set_node_seed(args, s)
                        if pf:
                            args = set_purify(args)
                        tasks.append(command + args)

    parallel = 8
    ps = []       # processes current running
    while len(tasks) > 0 or len(ps) > 0:
        if len(ps) < parallel and len(tasks) > 0:
            task = tasks.pop(0)
            print(task, f'{len(tasks)} still in queue')
            ps.append(Popen(task, stdout=PIPE, stderr=PIPE))
        else:
            time.sleep(0.05)
            new_ps = []
            for p in ps:
                if p.poll() is None:
                    new_ps.append(p)
                else:
                    get_output(p)
            ps = new_ps




if __name__ == '__main__':
    main_10_30_24()

