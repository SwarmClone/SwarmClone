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

from core.application import Application
from core.logger import log


def create_app() -> Application:
    """
    Create and return the Application instance
    
    Returns:
        Application instance configured with lifespan
    """
    log.info("Creating application instance...")
    
    application = Application()
    application.create_fastapi_app()
    
    log.info("Application instance created successfully")
    return application


# The global application instance
application = create_app()

# Expose the FastAPI app for uvicorn
app = application.app