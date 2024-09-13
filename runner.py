'''run experiments
'''

import time
from subprocess import Popen, PIPE


def set_memory_adaptive(args: list, memory_adaptive: int):
    return args + ["-ma", str(memory_adaptive)]

def set_update_prob(args: list):
    return args + ["-up"]

def set_node_seed(args: list, seed: int):
    return args + ["-ns", str(seed)]

def set_queue_seed(args: list, seed: int):
    return args + ["-qs", str(seed)]

def get_output(p: Popen):
    stderr = p.stderr.readlines()
    if stderr:
        for line in stderr:
            print(line)
    
    stdout = p.stdout.readlines()
    if stdout:
        for line in stdout:
            print(line)


def main():

    tasks = []

    command = ['python', 'main.py']
    base_args = ["-tp", "as", "-n", "100", "-t", "200", "-d", "log/9.12.24"]

    memory_adaptive = [0, 5]
    seed = list(range(15, 20))
    for ma in memory_adaptive:
        for up in [False, True]:
            if ma == 0 and up == True:
                continue
            for s in seed:
                args = set_memory_adaptive(base_args, ma)
                if up:
                    args = set_update_prob(args)
                ###
                # args = set_node_seed(args, s)
                args = set_queue_seed(args, s)
                ###
                tasks.append(command + args)

    parallel = 7
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
    main()

