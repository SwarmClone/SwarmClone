# SwarmCloneBackend
# Copyright (c) 2025 SwarmClone <github.com/SwarmClone> and contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from core.module_manager import Controller
import sys

from core.logger import log


def main():
    log.info("Starting SwarmCloneBackend...")
    controller = Controller()
    controller.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Program terminated by user")
        sys.exit(0)
    except Exception as e:
        log.error(f"Error: {e}")
        sys.exit(1)