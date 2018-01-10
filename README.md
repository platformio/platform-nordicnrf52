# Nordic nRF52: development platform for [PlatformIO](http://platformio.org)
[![Build Status](https://travis-ci.org/platformio/platform-nordicnrf52.svg?branch=develop)](https://travis-ci.org/platformio/platform-nordicnrf52)
[![Build status](https://ci.appveyor.com/api/projects/status/9v5b92p4envtpmsk/branch/develop?svg=true)](https://ci.appveyor.com/project/ivankravets/platform-nordicnrf52/branch/develop)

The nRF52 Series are built for speed to carry out increasingly complex tasks in the shortest possible time and return to sleep, conserving precious battery power. They have a Cortex-M4F processor and are the most capable Bluetooth Smart SoCs on the market.

* [Home](http://platformio.org/platforms/nordicnrf52) (home page in PlatformIO Platform Registry)
* [Documentation](http://docs.platformio.org/page/platforms/nordicnrf52.html) (advanced usage, packages, boards, frameworks, etc.)

# Usage

1. [Install PlatformIO](http://platformio.org)
2. Create PlatformIO project and configure a platform option in [platformio.ini](http://docs.platformio.org/page/projectconf.html) file:

## Stable version

```ini
[env:stable]
platform = nordicnrf52
board = ...
...
```

## Development version

```ini
[env:development]
platform = https://github.com/platformio/platform-nordicnrf52.git
board = ...
...
```

# Configuration

Please navigate to [documentation](http://docs.platformio.org/page/platforms/nordicnrf52.html).
