def error(*messages):
    print("\033[91m", *messages, "\033[0m", flush=True)


def success(*messages):
    print("\033[92m", *messages, "\033[0m", flush=True)


def warning(*messages):
    print("\033[93m", *messages, "\033[0m", flush=True)


removed = error
added = success


def print_change(infos, before, after, *, line=0):
    print(f'{infos}@{line}:')
    for before_line in before.splitlines():
        if before_line:
            removed(f'-{before_line}')
    for after_line in after.splitlines():
        if after_line:
            added(f'+{after_line}')


def print_changes(filename, changes):
    print(f'---{filename}')
    print(f'+++{filename}')
    for change in changes:
        before, after, line = change.values()
        print(f'@@ -{line},{len(before)} +{line},{len(after)} @@')
        for before_line in before.splitlines():
            if before_line:
                removed(f'-{before_line}')
        for after_line in after.splitlines():
            if after_line:
                added(f'+{after_line}')
