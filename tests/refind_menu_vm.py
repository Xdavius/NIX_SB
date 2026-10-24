"""Drive the experimental rEFInd menu in QEMU; never access the host ESP."""
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def exercise_menu(command, root):
    qmp_path = root / 'qmp.sock'
    output = Path('dist/refind-preview').resolve()
    choice = os.environ.get('GLF_VM_REFIND_CHOICE', 'previous')
    if choice not in ('previous', 'other'):
        raise ValueError('GLF_VM_REFIND_CHOICE: previous or other expected')
    if choice == 'other':
        output = output / 'other'
    output.mkdir(parents=True, exist_ok=True)
    command += ['-qmp', f'unix:{qmp_path},server=on,wait=off']
    process = subprocess.Popen(command)
    try:
        deadline = time.monotonic() + 30
        while not qmp_path.exists():
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('QEMU did not expose QMP')
            time.sleep(0.1)
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(qmp_path))
            client.settimeout(30)
            stream = client.makefile('rwb')
            json.loads(stream.readline())

            def execute(name, arguments=None):
                message = {'execute': name}
                if arguments:
                    message['arguments'] = arguments
                stream.write(json.dumps(message).encode() + b'\n')
                stream.flush()
                while True:
                    response = json.loads(stream.readline())
                    if 'error' in response:
                        raise RuntimeError(response['error'])
                    if 'return' in response:
                        return response['return']

            def key(name):
                execute('send-key', {'keys': [{'type': 'qcode', 'data': name}]})
                time.sleep(1)

            def screenshot(name):
                execute('screendump', {'filename': str(output / f'{name}.ppm')})

            execute('qmp_capabilities')
            time.sleep(18)
            screenshot('01-main')
            if choice == 'previous':
                key('ret')
                screenshot('02-generations')
                key('esc')
                screenshot('03-return')
                key('ret')
                key('down')
                key('down')
                screenshot('04-previous-generation')
            else:
                key('right')
            key('ret')
        process.wait(timeout=120)
        if process.returncode != 0:
            raise RuntimeError(f'QEMU exited with {process.returncode}')
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
