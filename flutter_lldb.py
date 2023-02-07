#!/usr/bin/env python
# coding=utf-8

import argparse
import os
import re
import subprocess
import sys

"""Tool for starting a lldb-server to debug a Flutter engine process on an Android device.

Usage:
  flutter_lldb \
  --abi armeabi \
  --android-sdk /path/to/androidSdk \
  --local-engine-src-path /path/to/engine/src \
  --local-engine android_debug_unopt \
  --build-dir /path/to/your/engine/build/dir \
  --symbol-dir /path/to/your/engine/symbol/dir \
   com.example.package_name
"""


def _find_package_pid(adb_path, package):
    """Find the pid of the Flutter application process."""
    ps_output = subprocess.check_output([adb_path, 'shell', 'ps'])
    ps_match = re.search('^\S+\s+(\d+).*\s%s' % package, ps_output.decode('utf-8'), re.MULTILINE)
    if not ps_match:
        print('Unable to find pid for package %s on device' % package)
        print('You can get the application pid by execute one of the commands in terminal:')
        print('adb shell pidof %s' % package)
        print('adb shell ps | grep %s | awk \'{ print $2 }\'' % package)
        print('')
        return None
    return int(ps_match.group(1))


def _get_device_abi(adb_path):
    """get the device abi."""
    abi_output = subprocess.check_output(
        [adb_path, 'shell', 'getprop', 'ro.product.cpu.abi']).strip()
    if abi_output.startswith('arm64'):
        return 'arm64-v8a'
    if abi_output.startswith('arm'):
        return 'armeabi'
    return abi_output


def _get_android_home(args):
    """get the android sdk home."""
    android_sdk = args.android_sdk
    if android_sdk and os.path.exists(android_sdk):
        return android_sdk
    android_home = os.getenv("ANDROID_HOME")
    if not android_home:
        raise EnvironmentError(
            "You must set environment with $ANDROID_HOME or provide the android sdk home with --android-sdk")
    return android_home


def _get_adb_path(args):
    """get the adb path."""
    return os.path.join(_get_android_home(args), "platform-tools", "adb")


def _get_android_lldb_server(args):
    """get the lldb-server path.""" 
    src_dir = '/Users/vke/Work/flutter/engine/src'
    src_dir = args.local_engine_src_path
    clang_dir = src_dir + '/third_party/android_tools/ndk/toolchains/llvm/prebuilt/darwin-x86_64/lib64/clang/'
    x = ''
    try: 
        x = os.listdir(clang_dir)[0]
    except Exception as e:
        print(e)
    return clang_dir + x + 'lib/linux/arm/lldb-server'


LLDB_SERVER_DEVICE_TMP_PATH = '/data/local/tmp/lldb-server'

def _config_vscode_launch_json(args, config_json):
    engine_dir = args.local_engine_src_path
    f = open(engine_dir + "/.vscode/launch.json", 'w')
    f.write(config_json)
    f.close()

def main():
    parser = argparse.ArgumentParser(description='lldb debugger tool')
    parser.add_argument('--android-sdk', type=str, help='android sdk home')
    parser.add_argument('--abi', type=str, choices=['armeabi', 'arm64-v8a', 'x86', 'x86_64'],
                        help="lldb-server executable's abi type")
    parser.add_argument('--local-engine-src-path', type=str, default='/path/to/engine/src',
                        help="flutter local engine src")
    parser.add_argument('--local-engine', type=str, default='android_debug_unopt',
                        help="flutter local engine, such as `android_debug_unopt`")
    parser.add_argument('--build-dir', type=str, help="flutter build dir on build machine if need, default use src.")
    parser.add_argument('--symbol-dir', type=str, help="flutter symbol dir, default use out/local-engine.")
    parser.add_argument('package', type=str, help="the application's package name run in device")
    return run(parser.parse_args())


def run(args):
    print(args)
    adb_path = _get_adb_path(args)
    lldb_server_local_path = _get_android_lldb_server(args)
    application_pid = _find_package_pid(adb_path, args.package)
    pid = application_pid or (
            'get pid by execute `adb shell pidof %s` yourself' % args.package)

    if not application_pid:
        print("You should replace the `pid` in vscode launch.json yourself because I can't get the pid auto")
        print('')

    if args.local_engine_src_path == '/path/to/engine/src':
        print("You should replace the `add-dsym` in vscode launch.json yourself because I can't get symbol(libflutter.so) path")
        print("You should replace the `target.source-map` in vscode launch.json yourself because I can't get engine src path")
        print('')
        print('In order to generate the vscode config auto')
        print("You'd better provide the flutter local engine src path by --local-engine-src-path /path/to/engin/src")
        print("You'd better provide the flutter local engine out dirname by --local-engine android_debug_unopt")
        print('')
    local_engine_out = os.path.join(args.local_engine_src_path, 'out', args.local_engine)

    vscode_config = """
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "remote_lldb",
            "type": "lldb",
            "request": "attach",
            "pid": "%s",
            "initCommands": [
                "platform select remote-android",
                "platform connect unix-abstract-connect:///data/data/%s/debug.socket"
            ],
            "postRunCommands": [
                "add-dsym %s/libflutter.so",
                "settings set target.source-map %s %s"
            ],
        }
    ]
}
    """ % (
        pid, args.package, args.symbol_dir or local_engine_out, args.build_dir or args.local_engine_src_path,
        args.local_engine_src_path)

    print("")
    print("Visual Studio Code launch configuration.")
    print("This configuration perform like `attach to debuggable process`.")
    print("Copy it to .vscode/launch.json if you have already load libflutter.so into memory:\n%s" % vscode_config)

    vscode_config = """
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "remote_lldb",
            "type": "lldb",
            "request": "attach",
            "pid": "%s",
            "initCommands": [
                "platform select remote-android",
                "platform connect unix-abstract-connect:///data/data/%s/debug.socket"
            ],
            "preRunCommands": [
                "settings append target.exec-search-paths %s"
            ],
            "postRunCommands": [
                "settings set target.source-map %s %s"
            ],
        }
    ]
}
        """ % (
    pid, args.package, args.symbol_dir or local_engine_out, args.build_dir or args.local_engine_src_path, args.local_engine_src_path)

    print("Visual Studio Code launch configuration.")
    print("This configuration perform like `wait for debuggable process`.")
    print("Copy it to .vscode/launch.json if you have not load libflutter.so into memory:\n%s" % vscode_config)

    _config_vscode_launch_json(args, vscode_config)

    # subprocess.check_call([adb_path, 'push', lldb_server_local_path, LLDB_SERVER_DEVICE_TMP_PATH], shell=True)
    FNULL = open(os.devnull, 'w')
    subprocess.call([adb_path, 'push', lldb_server_local_path, LLDB_SERVER_DEVICE_TMP_PATH], shell=True, stdout=FNULL, stderr=subprocess.STDOUT)
    lldb_server_device_path = '/data/data/%s/lldb-server' % args.package
    subprocess.check_call([adb_path, 'shell', 'run-as', args.package, 'cp', '-F',
                           LLDB_SERVER_DEVICE_TMP_PATH,
                           lldb_server_device_path])
    subprocess.check_call([adb_path, 'shell', 'run-as', args.package, 'chmod', 'a+x', lldb_server_device_path])
    subprocess.call([adb_path, 'shell', 'run-as', args.package, 'killall', 'lldb-server'])

    subprocess.check_call([adb_path, 'shell', 'run-as', args.package, 'sh', '-c',
                           "'%s platform --server --listen unix-abstract:///data/data/%s/debug.socket'" % (
                               lldb_server_device_path, args.package)])

    return 0


if __name__ == '__main__':
    sys.exit(main())
