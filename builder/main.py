# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from platform import system
from os import makedirs
from os.path import isdir, join

from SCons.Script import (ARGUMENTS, COMMAND_LINE_TARGETS, AlwaysBuild,
                          Builder, Default, DefaultEnvironment)

env = DefaultEnvironment()
platform = env.PioPlatform()
board = env.BoardConfig()
variant = board.get("build.variant", "")

use_adafruit = board.get("build.bsp.name", "nrf5") == "adafruit"
if use_adafruit:
    FRAMEWORK_DIR = platform.get_package_dir("framework-arduinoadafruitnrf52")

    os_platform = sys.platform
    if os_platform == "win32":
        nrfutil_path = join(FRAMEWORK_DIR, "tools", "adafruit-nrfutil", os_platform, "adafruit-nrfutil.exe")
    elif os_platform == "darwin":
        nrfutil_path = join(FRAMEWORK_DIR, "tools", "adafruit-nrfutil", "macos", "adafruit-nrfutil")
    else:
        nrfutil_path = "adafruit-nrfutil"
else:
    # set it to empty since we won't need it
    nrfutil_path = ""

env.Replace(
    AR="arm-none-eabi-ar",
    AS="arm-none-eabi-as",
    CC="arm-none-eabi-gcc",
    CXX="arm-none-eabi-g++",
    GDB="arm-none-eabi-gdb",
    OBJCOPY="arm-none-eabi-objcopy",
    RANLIB="arm-none-eabi-ranlib",
    SIZETOOL="arm-none-eabi-size",

    ARFLAGS=["rc"],

    SIZEPROGREGEXP=r"^(?:\.text|\.data|\.rodata|\.text.align|\.ARM.exidx)\s+(\d+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.bss|\.noinit)\s+(\d+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    ERASEFLAGS=["--eraseall", "-f", "nrf52"],
    ERASECMD="nrfjprog $ERASEFLAGS",

    PROGSUFFIX=".elf"
)

# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

env.Append(
    BUILDERS=dict(
        ElfToBin=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "binary",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".bin"
        ),
        ElfToHex=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "ihex",
                "-R",
                ".eeprom",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".hex"
        ),
        MergeHex=Builder(
            action=env.VerboseAction(" ".join([
                join(platform.get_package_dir("tool-sreccat") or "",
                     "srec_cat"),
                "$SOFTDEVICEHEX",
                "-intel",
                "$SOURCES",
                "-intel",
                "-o",
                "$TARGET",
                "-intel",
                "--line-length=44"
            ]), "Building $TARGET"),
            suffix=".hex"
        )
    )
)

if use_adafruit:
    env.Append(
        BUILDERS=dict(
            PackageDfu=Builder(
                action=env.VerboseAction(" ".join([
                    '"%s"' % nrfutil_path,
                    "dfu",
                    "genpkg",
                    "--dev-type",
                    "0x0052",
                    "--sd-req",
                    board.get("build.softdevice.sd_fwid"),
                    "--application",
                    "$SOURCES",
                    "$TARGET"
                ]), "Building $TARGET"),
                suffix=".zip"
            ),
            SignBin=Builder(
                action=env.VerboseAction(" ".join([
                    "$PYTHONEXE",
                    join(FRAMEWORK_DIR or "",
                        "tools", "pynrfbintool", "pynrfbintool.py"),
                    "--signature",
                    "$TARGET",
                    "$SOURCES"
                ]), "Signing $SOURCES"),
                suffix="_signature.bin"
            )
        )
    )


if not env.get("PIOFRAMEWORK"):
    env.SConscript("frameworks/_bare.py")

#
# Target: Build executable and linkable firmware
#

upload_protocol = env.subst("$UPLOAD_PROTOCOL")
target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    target_firm = join("$BUILD_DIR", "${PROGNAME}.hex")
else:
    target_elf = env.BuildProgram()

    if "SOFTDEVICEHEX" in env:
        target_firm = env.MergeHex(
            join("$BUILD_DIR", "${PROGNAME}"),
            env.ElfToHex(join("$BUILD_DIR", "userfirmware"), target_elf))
    elif "DFUBOOTHEX" in env:
        if "nrfutil" == upload_protocol:
            target_firm = env.PackageDfu(
                join("$BUILD_DIR", "${PROGNAME}"),
                env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf))
        elif "nrfjprog" == upload_protocol:
            target_firm = env.ElfToHex(
                join("$BUILD_DIR", "${PROGNAME}"), target_elf)
        else:
            target_firm = env.SignBin(
                join("$BUILD_DIR", "${PROGNAME}"),
                env.ElfToBin(join("$BUILD_DIR", "${PROGNAME}"), target_elf))
    else:
        target_firm = env.ElfToHex(
            join("$BUILD_DIR", "${PROGNAME}"), target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

if "DFUBOOTHEX" in env:
    env.Append(
        # Check the linker script for the correct location
        BOOT_SETTING_ADDR=board.get("build.bootloader.settings_addr", "0x7F000")
    )

    AlwaysBuild(env.Alias("dfu", env.PackageDfu(
        join("$BUILD_DIR", "${PROGNAME}"),
        env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf))))

    AlwaysBuild(env.Alias("bootloader", None, [
        env.VerboseAction("nrfjprog --program $DFUBOOTHEX -f nrf52 --chiperase", "Uploading $DFUBOOTHEX"),
        env.VerboseAction("nrfjprog --erasepage $BOOT_SETTING_ADDR -f nrf52", "Erasing bootloader config"),
        env.VerboseAction("nrfjprog --memwr $BOOT_SETTING_ADDR --val 0x00000001 -f nrf52", "Disable CRC check"),
        env.VerboseAction("nrfjprog --reset -f nrf52", "Reset nRF52")
    ]))

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload by default .bin file
#

debug_tools = env.BoardConfig().get("debug.tools", {})
upload_actions = []

if upload_protocol == "mbed":
    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for upload disk..."),
        env.VerboseAction(env.UploadToDisk, "Uploading $SOURCE")
    ]

elif upload_protocol.startswith("blackmagic"):
    env.Replace(
        UPLOADER="$GDB",
        UPLOADERFLAGS=[
            "-nx",
            "--batch",
            "-ex", "target extended-remote $UPLOAD_PORT",
            "-ex", "monitor %s_scan" %
            ("jtag" if upload_protocol == "blackmagic-jtag" else "swdp"),
            "-ex", "attach 1",
            "-ex", "load",
            "-ex", "compare-sections",
            "-ex", "kill"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS $BUILD_DIR/${PROGNAME}.elf"
    )
    upload_actions = [
        env.VerboseAction(env.AutodetectUploadPort, "Looking for BlackMagic port..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

elif upload_protocol == "nrfjprog":
    env.Replace(
        UPLOADER="nrfjprog",
        UPLOADERFLAGS=[
            "--sectorerase" if "DFUBOOTHEX" in env else "--chiperase",
            "--reset"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS --program $SOURCE"
    )
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

elif upload_protocol == "nrfutil":
    env.Replace(
        UPLOADER=nrfutil_path,
        UPLOADERFLAGS=[
            "dfu",
            "serial",
            "-p",
            "$UPLOAD_PORT",
            "-b",
            "$UPLOAD_SPEED",
            "--singlebank",
        ],
        UPLOADCMD='"$UPLOADER" $UPLOADERFLAGS -pkg $SOURCE'
    )
    upload_actions = [env.VerboseAction(env.AutodetectUploadPort, "Looking for upload port..."),
                      env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

elif upload_protocol.startswith("jlink"):

    def _jlink_cmd_script(env, source):
        build_dir = env.subst("$BUILD_DIR")
        if not isdir(build_dir):
            makedirs(build_dir)
        script_path = join(build_dir, "upload.jlink")
        commands = [ "h" ]
        if "DFUBOOTHEX" in env:
            commands.append("loadbin %s,%s" % (str(source).replace("_signature", ""),
                env.BoardConfig().get("upload.offset_address", "0x26000")))
            commands.append("loadbin %s,%s" % (source, env.get("BOOT_SETTING_ADDR")))
        else:
            commands.append("loadbin %s,%s" % (source, env.BoardConfig().get(
                "upload.offset_address", "0x0")))

        commands.append("r")
        commands.append("q")

        with open(script_path, "w") as fp:
            fp.write("\n".join(commands))
        return script_path

    env.Replace(
        __jlink_cmd_script=_jlink_cmd_script,
        UPLOADER="JLink.exe" if system() == "Windows" else "JLinkExe",
        UPLOADERFLAGS=[
            "-device", env.BoardConfig().get("debug", {}).get("jlink_device"),
            "-speed", "4000",
            "-if", ("jtag" if upload_protocol == "jlink-jtag" else "swd"),
            "-autoconnect", "1"
        ],
        UPLOADCMD='$UPLOADER $UPLOADERFLAGS -CommanderScript "${__jlink_cmd_script(__env__, SOURCE)}"'
    )
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

elif upload_protocol in debug_tools:
    openocd_args = [
        "-d%d" % (2 if int(ARGUMENTS.get("PIOVERBOSE", 0)) else 1)
    ]
    openocd_args.extend(
        debug_tools.get(upload_protocol).get("server").get("arguments", []))
    openocd_args.extend([
        "-c", "program {$SOURCE} %s verify reset; shutdown;" %
        board.get("upload.offset_address", "")
    ])
    openocd_args = [
        f.replace("$PACKAGE_DIR",
                  platform.get_package_dir("tool-openocd") or "")
        for f in openocd_args
    ]
    env.Replace(
        UPLOADER="openocd",
        UPLOADERFLAGS=openocd_args,
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS")
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

# custom upload tool
elif upload_protocol == "custom":
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

else:
    sys.stderr.write("Warning! Unknown upload protocol %s\n" % upload_protocol)

AlwaysBuild(env.Alias("upload", target_firm, upload_actions))


#
# Target: Erase Flash
#

AlwaysBuild(
    env.Alias("erase", None, env.VerboseAction("$ERASECMD",
                                               "Erasing...")))

#
# Default targets
#

Default([target_buildprog, target_size])
